from __future__ import annotations

import asyncio
import queue
import threading
import webbrowser

import pystray
from PIL import Image, ImageDraw

from ble_scanner import ProximityScanner
from control_plane import ControlPlaneClient, ControlPlaneError
from gui import ProximityGUI
from system_controller import lock_system


app_gui = None
scanner = None
async_loop = None
scanner_thread = None
tray_icon = None
control_client = None
sync_event = None
current_config = None
current_scanner_key = None
observations: dict[str, dict] = {}
gui_queue = queue.Queue()
loop_ready = threading.Event()


def start_async_loop():
    global async_loop, sync_event
    async_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(async_loop)
    sync_event = asyncio.Event()
    loop_ready.set()
    async_loop.run_forever()


def run_coroutine(coroutine):
    if not loop_ready.wait(timeout=5) or async_loop is None:
        raise RuntimeError("Nie udało się uruchomić pętli komunikacji")
    return asyncio.run_coroutine_threadsafe(coroutine, async_loop)


def push_status(state, title, message, brelock_name=None):
    gui_queue.put(
        (
            "status",
            {
                "state": state,
                "title": title,
                "message": message,
                "brelock_name": brelock_name,
            },
        )
    )


def process_gui_queue():
    if not app_gui:
        return
    try:
        while True:
            message, payload = gui_queue.get_nowait()
            if message == "status":
                app_gui.update_status(**payload)
            elif message == "deiconify":
                app_gui.deiconify()
                app_gui.lift()
                app_gui.attributes("-topmost", True)
                app_gui.after(120, lambda: app_gui.attributes("-topmost", False))
            elif message == "force_close":
                app_gui.force_close()
    except queue.Empty:
        pass
    finally:
        app_gui.after(100, process_gui_queue)


def on_observation(device_id: str, display_name: str, rssi: int):
    observations[device_id] = {
        "brelock_id": device_id,
        "display_name": display_name,
        "rssi": int(rssi),
    }


def on_rssi_update(smoothed, current, departure_trend):
    config = current_config or {}
    name = config.get("display_name", f"breLock-{config.get('brelock_id', '')[-6:]}")
    trend_text = ""
    if departure_trend and departure_trend.confidence >= 0.35:
        trend_text = " Analizuję, czy użytkownik konsekwentnie się oddala."
    push_status(
        "protected",
        "Twój laptop jest chroniony",
        "Przypisany breLock jest w zasięgu." + trend_text,
        name,
    )


def on_lock_triggered(reason: str):
    print(f"[protection] blokada: {reason}", flush=True)
    lock_system()
    config = current_config or {}
    push_status(
        "locked",
        "Laptop został zablokowany",
        "breLock opuścił bezpieczną strefę. Ochrona nadal działa w tle.",
        config.get("display_name"),
    )


async def configure_scanner(config: dict | None):
    global scanner, current_config, current_scanner_key
    config = config or {"assigned": False}
    assigned = bool(config.get("assigned"))
    enabled = bool(config.get("enabled", True))
    target_id = config.get("brelock_id") if assigned and enabled else None
    key = (
        target_id,
        config.get("rssi_threshold", -72),
        config.get("reaction_seconds", 3),
        config.get("watchdog_seconds", 6),
    )
    current_config = config
    if key == current_scanner_key and scanner is not None:
        return
    current_scanner_key = key

    if scanner is not None:
        await scanner.stop()

    scanner = ProximityScanner(
        target_id=target_id,
        rssi_threshold=float(config.get("rssi_threshold", -72)),
        timeout_seconds=float(config.get("reaction_seconds", 3)),
        watchdog_seconds=float(config.get("watchdog_seconds", 6)),
        lock_callback=on_lock_triggered,
        dead_loop_callback=on_lock_triggered,
        observation_callback=on_observation,
    )
    scanner.on_rssi_update = on_rssi_update
    await scanner.start()

    if not assigned:
        push_status(
            "unassigned",
            "Czekam na przypisanie",
            "Laptop jest już widoczny w panelu firmy. Administrator przypisze do niego breLock.",
        )
    elif not enabled:
        push_status(
            "disabled",
            "Ochrona wyłączona przez administratora",
            "Aplikacja działa i czeka na zmianę polityki firmy.",
            config.get("display_name"),
        )
    else:
        push_status(
            "searching",
            "Szukam przypisanego breLocka",
            "Ochrona włączy się automatycznie, gdy urządzenie znajdzie się w zasięgu.",
            config.get("display_name"),
        )


async def control_loop():
    await configure_scanner(control_client.cached_config())
    while True:
        poll_seconds = 15
        try:
            await asyncio.to_thread(control_client.ensure_registered)
            config = await asyncio.to_thread(control_client.fetch_config)
            poll_seconds = int(config.get("poll_seconds", 15))
            await configure_scanner(config)
            snapshot = list(observations.values())
            observations.clear()
            await asyncio.to_thread(control_client.heartbeat, snapshot)
        except ControlPlaneError as exc:
            cached = control_client.cached_config()
            if cached and cached.get("assigned") and cached.get("enabled", True):
                await configure_scanner(cached)
                push_status(
                    "offline",
                    "Panel firmy jest chwilowo offline",
                    "Ochrona działa dalej z ostatnią zapisaną polityką.",
                    cached.get("display_name"),
                )
            else:
                push_status("error", "Nie można uruchomić ochrony", str(exc))
        except Exception as exc:
            print(f"[control-plane] {exc}", flush=True)
            push_status("error", "Wystąpił błąd aplikacji", str(exc))

        try:
            await asyncio.wait_for(sync_event.wait(), timeout=max(5, poll_seconds))
            sync_event.clear()
        except asyncio.TimeoutError:
            pass


def request_sync():
    if async_loop and sync_event:
        async_loop.call_soon_threadsafe(sync_event.set)


def open_admin_panel():
    if control_client:
        webbrowser.open(control_client.control_url)


def create_tray_image():
    try:
        return Image.open(__import__("pathlib").Path(__file__).with_name("logo.png"))
    except Exception:
        image = Image.new("RGB", (64, 64), color=(7, 17, 13))
        draw = ImageDraw.Draw(image)
        draw.ellipse((12, 12, 52, 52), fill=(55, 214, 122))
        return image


def setup_tray():
    global tray_icon
    menu = pystray.Menu(
        pystray.MenuItem("Pokaż status", lambda _icon, _item: gui_queue.put(("deiconify", None)), default=True),
        pystray.MenuItem("Synchronizuj", lambda _icon, _item: request_sync()),
        pystray.MenuItem("Panel administratora", lambda _icon, _item: open_admin_panel()),
        pystray.MenuItem("Wyjdź", on_tray_exit),
    )
    tray_icon = pystray.Icon("breLock", create_tray_image(), "breLock", menu)
    try:
        tray_icon.run_detached()
    except Exception as exc:
        print(f"[tray] {exc}", flush=True)


def on_tray_exit(icon, _item):
    icon.stop()
    if scanner and async_loop:
        asyncio.run_coroutine_threadsafe(scanner.stop(), async_loop)
    if async_loop:
        async_loop.call_soon_threadsafe(async_loop.stop)
    gui_queue.put(("force_close", None))


def hide_window_to_tray():
    if app_gui:
        app_gui.withdraw()


def main():
    global app_gui, scanner_thread, control_client
    control_client = ControlPlaneClient()
    scanner_thread = threading.Thread(target=start_async_loop, daemon=True)
    scanner_thread.start()
    loop_ready.wait(timeout=5)

    app_gui = ProximityGUI(
        sync_callback=request_sync,
        open_admin_callback=open_admin_panel,
    )
    app_gui.set_installation_id(control_client.installation_id)
    app_gui.on_hide_callback = hide_window_to_tray
    app_gui.after(100, process_gui_queue)
    setup_tray()
    run_coroutine(control_loop())
    app_gui.mainloop()


if __name__ == "__main__":
    main()
