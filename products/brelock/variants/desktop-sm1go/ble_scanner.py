import asyncio
import time
from bleak import BleakScanner

class ProximityScanner:
    def __init__(self, target_name: str, rssi_threshold: float, timeout_seconds: float, lock_callback, dead_loop_callback=None):
        self.target_name = target_name
        self.rssi_threshold = rssi_threshold
        self.timeout_seconds = timeout_seconds
        self.lock_callback = lock_callback
        self.dead_loop_callback = dead_loop_callback
        
        self.scanner = None
        self.is_running = False
        
        # Opcjonalne callbacki dla GUI
        self.on_rssi_update = None 
        
        self.ema_alpha = 0.3
        self.smoothed_rssi = None
        
        self.last_seen = 0.0
        self.weak_signal_start = None
        
        self.watchdog_threshold = 6.0
        self.watchdog_task = None
        self._watchdog_fired = False  # jednorazowe wygaszenie

    def detection_callback(self, device, advertisement_data):
        # Skanujemy tylko urządzenie docelowe
        if self.target_name and device.name == self.target_name:
            current_rssi = advertisement_data.rssi
            self.last_seen = time.time()
            
            # Reset flagi watchdoga — urządzenie wróciło
            self._watchdog_fired = False
            
            # 1. Wygładzanie EMA (Exponential Moving Average)
            if self.smoothed_rssi is None:
                self.smoothed_rssi = float(current_rssi)
            else:
                self.smoothed_rssi = (self.ema_alpha * current_rssi) + ((1 - self.ema_alpha) * self.smoothed_rssi)
                
            # Powiadom potencjalne GUI o nowej wartości
            if self.on_rssi_update:
                self.on_rssi_update(self.smoothed_rssi, current_rssi)
                
            # 2. Logika blokady oparta na wygładzonym RSSI (EMA)
            if self.smoothed_rssi < self.rssi_threshold:
                if self.weak_signal_start is None:
                    self.weak_signal_start = time.time()
                else:
                    elapsed = time.time() - self.weak_signal_start
                    if elapsed >= self.timeout_seconds:
                        self.trigger_lock(f"Niski sygnał (EMA RSSI: {self.smoothed_rssi:.1f}) przez {elapsed:.1f}s")
            else:
                self.weak_signal_start = None

    def trigger_lock(self, reason: str):
        # Reset trackera zliczanego czasu
        self.weak_signal_start = None
        
        # Wywołaj faktyczną blokadę podaną w callbacku
        if self.lock_callback:
            self.lock_callback(reason)

    async def watchdog(self):
        """Zabezpieczenie: sprawdza całkowity brak urządzenia (np. wyłączone, zerwana komunikacja).
        Przy utracie sygnału wykonuje JEDNORAZOWE wyłączenie (dead loop) zamiast pętli blokad."""
        while self.is_running:
            await asyncio.sleep(1)
            # Upewniamy się, że cokolwiek złapaliśmy przed rozpoczęciem liczenia
            if self.last_seen > 0 and not self._watchdog_fired:
                elapsed = time.time() - self.last_seen
                if elapsed > self.watchdog_threshold:
                    self._watchdog_fired = True  # jednorazowo
                    print(f"[Watchdog] DEAD LOOP — urządzenie utracone ({elapsed:.1f}s > {self.watchdog_threshold}s)")
                    
                    if self.dead_loop_callback:
                        # Całkowita utrata → wyłączenie systemu (dead loop)
                        self.dead_loop_callback(f"Utrata sygnału (Watchdog {elapsed:.1f}s > {self.watchdog_threshold}s)")
                    elif self.lock_callback:
                        # Fallback: jeśli brak dead_loop_callback, blokuj jak wcześniej
                        self.lock_callback(f"Utrata sygnału (Watchdog {elapsed:.1f}s > {self.watchdog_threshold}s)")

    async def start(self):
        self.is_running = True
        self.last_seen = time.time()  # Unikamy triggera watchdoga od razu po starcie
        self.weak_signal_start = None
        self.smoothed_rssi = None
        self._watchdog_fired = False
        
        self.scanner = BleakScanner(detection_callback=self.detection_callback)
        await self.scanner.start()
        
        self.watchdog_task = asyncio.create_task(self.watchdog())

    async def stop(self):
        self.is_running = False
        if self.watchdog_task:
            self.watchdog_task.cancel()
        if self.scanner:
            await self.scanner.stop()
