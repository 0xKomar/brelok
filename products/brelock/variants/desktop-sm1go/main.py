import threading
import asyncio
import json
import os
import pystray
import queue
from PIL import Image, ImageDraw
import customtkinter as ctk
from bleak import BleakScanner

from gui import ProximityGUI
from ble_scanner import ProximityScanner
from system_controller import lock_system

CONFIG_FILE = "config.json"

# --- Zmienne Globalne ---
app_gui = None
scanner = None
async_loop = None
scanner_thread = None
tray_icon = None

# Zabezpieczenie procesów przed kolizjami wątków (szczególnie macOS AppKit / GIL)
gui_queue = queue.Queue()

# --- Zarządzanie Konfiguracją ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Błąd czytania configu: {e}")
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

# --- Obsługa Wątków i asyncio ---
def start_async_loop():
    global async_loop
    async_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(async_loop)
    async_loop.run_forever()

def run_coroutine(coro):
    if async_loop:
        asyncio.run_coroutine_threadsafe(coro, async_loop)

# --- BEZPIECZNA KOLEJKA GUI ---
def process_gui_queue():
    """Funkcja cykliczna odpalana w głównym wątku Tkinter. Zdejmuje zadania bez naruszania GIL."""
    if not app_gui:
        return
    try:
        while True:
            msg, args = gui_queue.get_nowait()
            if msg == "deiconify":
                app_gui.deiconify()
                # Wymuszenie okna nad inne na macOS po przywróceniu
                app_gui.lift()
                app_gui.attributes('-topmost', True)
                app_gui.after(100, lambda: app_gui.attributes('-topmost', False))
            elif msg == "update_devices":
                app_gui.update_devices_list(args)
            elif msg == "update_live_status":
                smoothed, current, locked = args
                app_gui.update_live_status(smoothed, current, locked)
            elif msg == "toggle_protection":
                app_gui._toggle_protection()
            elif msg == "calibration_done":
                success, new_threshold, text = args
                app_gui.finish_calibration(success, new_threshold, text)
            elif msg == "force_close":
                app_gui.force_close()
    except queue.Empty:
        pass
    finally:
        app_gui.after(100, process_gui_queue)

# --- Callbacki dla GUI ---
def on_start_protection(target_name, threshold, timeout):
    global scanner
    config = {"target": target_name, "threshold": threshold, "timeout": timeout}
    save_config(config)
    
    async def _start():
        global scanner
        try:
            if scanner is not None:
                await scanner.stop()
                
            scanner = ProximityScanner(
                target_name=target_name, 
                rssi_threshold=threshold, 
                timeout_seconds=timeout, 
                lock_callback=on_lock_triggered,
                dead_loop_callback=on_dead_loop_triggered
            )
            scanner.on_rssi_update = on_rssi_update_gui
            
            await scanner.start()
            print(f"[Core] Ochrona aktywna dla: {target_name}")
        except Exception as e:
            print(f"[Core] Błąd startu ochrony: {e}")
            import traceback
            traceback.print_exc()
            gui_queue.put(("update_live_status", (0, 0, False)))
    
    run_coroutine(_start())

def on_stop_protection():
    global scanner
    if scanner is not None:
        run_coroutine(scanner.stop())
        scanner = None

def on_scan_requested():
    async def _scan():
        try:
            print("[Core] Rozpoczynam skanowanie BLE...")
            devices = await BleakScanner.discover(timeout=5.0)
            device_names = list(set([d.name for d in devices if d.name]))
            device_names.sort()
            print(f"[Core] Znaleziono {len(device_names)} urządzeń: {device_names}")
            gui_queue.put(("update_devices", device_names))
        except Exception as e:
            print(f"[Core] Scan error: {e}")
            import traceback
            traceback.print_exc()
            gui_queue.put(("update_devices", []))
            
    run_coroutine(_scan())

def on_start_calibration(target_name):
    async def _run_calibration():
        global scanner
        # Jeśli działa ochrona - zatrzymujemy na czas procedury
        was_running = False
        if scanner is not None and scanner.is_running:
            was_running = True
            await scanner.stop()
            
        print(f"[Core] Rozpoczynamy kalibracje dla: {target_name}")
        rssi_samples = []
        
        def calib_detect(device, adv_data):
            if device.name == target_name:
                rssi_samples.append(adv_data.rssi)
                
        calib_scanner = BleakScanner(detection_callback=calib_detect)
        try:
            await calib_scanner.start()
            await asyncio.sleep(5.0)
            await calib_scanner.stop()
            
            if len(rssi_samples) > 0:
                avg = sum(rssi_samples) / len(rssi_samples)
                new_threshold = int(avg) - 10
                new_threshold = max(-90, min(-40, new_threshold)) # Zabezpieczenie przed skrajnościami
                print(f"[Core] Kalibracja gotowa. Próbki: {len(rssi_samples)}, Średnia: {avg:.1f}, Nowy próg: {new_threshold}")
                gui_queue.put(("calibration_done", (True, new_threshold, "")))
            else:
                gui_queue.put(("calibration_done", (False, None, "Zbyt słaby sygnał/Brak urządzenia")))
        except Exception as e:
            print(f"Błąd kalibracji: {e}")
            gui_queue.put(("calibration_done", (False, None, "Błąd z Bleak_scanner!")))
            
        # Potencjalnie moglibyśmy tu wracać do ochrony, ale bezpieczniej niech użykownik kliknie Aktywuj!
            
    run_coroutine(_run_calibration())

def on_lock_triggered(reason):
    print(f"[Core] Blokada natywna z powodu: {reason}")
    lock_system()
    gui_queue.put(("update_live_status", (0, 0, True)))

def on_dead_loop_triggered(reason):
    """Dead loop — blokada ekranu przy całkowitej utracie urządzenia (brak pakietów)."""
    print(f"[Core] DEAD LOOP (lock) z powodu: {reason}")
    lock_system()
    gui_queue.put(("update_live_status", (0, 0, True)))

def on_rssi_update_gui(smoothed, current):
    gui_queue.put(("update_live_status", (smoothed, current, False)))

# --- System Tray (Ikona) ---
def create_tray_image():
    # Sprawdź, czy istnieje główny obraz "logo.png"
    icon_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except Exception as e:
            print(f"Błąd przy wczytywaniu ikony tray: {e}")
            
    # Zapasowe zastępcze logo (Niebieska tarcza) w razie braku pliku
    image = Image.new('RGB', (64, 64), color=(0, 0, 0))
    d = ImageDraw.Draw(image)
    d.ellipse((16, 16, 48, 48), fill=(0, 150, 255))
    return image

def on_tray_show(icon, item):
    gui_queue.put(("deiconify", None))

def on_tray_stop(icon, item):
    if app_gui and app_gui.is_active:
        gui_queue.put(("toggle_protection", None))
    else:
        on_stop_protection()
    
def on_tray_exit(icon, item):
    icon.stop()
    on_stop_protection()
    if async_loop:
        async_loop.call_soon_threadsafe(async_loop.stop)
    gui_queue.put(("force_close", None))

def setup_tray():
    global tray_icon
    image = create_tray_image()
    menu = pystray.Menu(
        pystray.MenuItem('Pokaż panel', on_tray_show, default=True),
        pystray.MenuItem('Zatrzymaj ochronę', on_tray_stop),
        pystray.MenuItem('Wyjdź', on_tray_exit)
    )
    tray_icon = pystray.Icon("BLE Proximity", image, "BLE Proximity", menu)
    
    try:
        tray_icon.run_detached()
    except Exception as e:
        print(f"Tray creation failed: {e}")

def hide_window_to_tray():
    if app_gui:
        app_gui.withdraw()

def main():
    global app_gui, scanner_thread
    
    # 1. Start tła dla biblioteki asynchronicznej skanera
    scanner_thread = threading.Thread(target=start_async_loop, daemon=True)
    scanner_thread.start()
    
    # 2. GUI setup
    app_gui = ProximityGUI(
        start_callback=on_start_protection,
        stop_callback=on_stop_protection,
        scan_callback=on_scan_requested,
        calibrate_callback=on_start_calibration
    )

    app_gui.after(100, process_gui_queue)
    
    # 3. Wczytanie konfiguracji
    config = load_config()
    app_gui.apply_settings(config)
    
    # 4. Inicjacja zasobnika systemowego
    app_gui.on_hide_callback = hide_window_to_tray
    setup_tray()
    
    print("-> System włączony. Konfiguracja poprzez aplikacje okienkową.")
    app_gui.mainloop()

if __name__ == "__main__":
    main()