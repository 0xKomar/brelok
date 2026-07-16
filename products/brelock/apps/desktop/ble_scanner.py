import asyncio
import time
from bleak import BleakScanner

from ble_identity import decode_brelock_identity
from trend_detector import DepartureTrendDetector

class ProximityScanner:
    def __init__(self, target_name: str | None = None, rssi_threshold: float = -72,
                 timeout_seconds: float = 3, lock_callback=None,
                 dead_loop_callback=None, target_id: str | None = None,
                 observation_callback=None, watchdog_seconds: float = 6):
        self.target_name = target_name
        self.target_id = target_id.upper() if target_id else None
        self.rssi_threshold = rssi_threshold
        self.timeout_seconds = timeout_seconds
        self.lock_callback = lock_callback
        self.dead_loop_callback = dead_loop_callback
        self.observation_callback = observation_callback
        
        self.scanner = None
        self.is_running = False
        
        # Opcjonalne callbacki dla GUI
        self.on_rssi_update = None 
        
        self.ema_alpha = 0.3
        self.smoothed_rssi = None
        self.departure_detector = DepartureTrendDetector(timeout_seconds)
        
        self.last_seen = None
        self.weak_signal_start = None
        
        self.watchdog_threshold = float(watchdog_seconds)
        self.watchdog_task = None
        self._watchdog_fired = False  # jednorazowe wygaszenie

    def detection_callback(self, device, advertisement_data):
        identity = decode_brelock_identity(advertisement_data)
        current_rssi = advertisement_data.rssi
        if identity and self.observation_callback:
            display_name = (
                getattr(advertisement_data, "local_name", None)
                or device.name
                or f"breLock-{identity.device_id[-6:]}"
            )
            self.observation_callback(
                identity.device_id,
                display_name,
                current_rssi,
            )

        matches_id = self.target_id and identity and identity.device_id == self.target_id
        matches_legacy_name = not self.target_id and self.target_name and device.name == self.target_name
        if matches_id or matches_legacy_name:
            self.last_seen = time.time()
            
            # Reset flagi watchdoga — urządzenie wróciło
            self._watchdog_fired = False
            
            # 1. Wygładzanie EMA (Exponential Moving Average)
            if self.smoothed_rssi is None:
                self.smoothed_rssi = float(current_rssi)
            else:
                self.smoothed_rssi = (self.ema_alpha * current_rssi) + ((1 - self.ema_alpha) * self.smoothed_rssi)
                
            # Trend spadku RSSI oznacza konsekwentny wzrost odległości.
            departure_trend = self.departure_detector.add(self.smoothed_rssi)

            # Powiadom potencjalne GUI o nowej wartości i stanie trendu.
            if self.on_rssi_update:
                self.on_rssi_update(self.smoothed_rssi, current_rssi, departure_trend)

            if departure_trend.triggered:
                self.trigger_lock(
                    "Konsekwentne oddalanie "
                    f"({departure_trend.duration:.1f}s, "
                    f"spadek {departure_trend.rssi_drop:.1f} dB, "
                    f"trend {departure_trend.slope_db_per_second:.1f} dB/s)"
                )
                return
                
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
        self.departure_detector.reset()
        
        # Wywołaj faktyczną blokadę podaną w callbacku
        if self.lock_callback:
            self.lock_callback(reason)

    async def watchdog(self):
        """Zabezpieczenie: sprawdza całkowity brak urządzenia (np. wyłączone, zerwana komunikacja).
        Przy utracie sygnału wykonuje JEDNORAZOWE wyłączenie (dead loop) zamiast pętli blokad."""
        while self.is_running:
            await asyncio.sleep(1)
            # Upewniamy się, że cokolwiek złapaliśmy przed rozpoczęciem liczenia
            if self.last_seen is not None and not self._watchdog_fired:
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
        # Arm the watchdog only after the target has actually been observed.
        self.last_seen = None
        self.weak_signal_start = None
        self.smoothed_rssi = None
        self.departure_detector.reset()
        self._watchdog_fired = False
        
        self.scanner = BleakScanner(detection_callback=self.detection_callback)
        await self.scanner.start()
        
        self.watchdog_task = asyncio.create_task(self.watchdog())

    async def stop(self):
        self.is_running = False
        if self.watchdog_task:
            self.watchdog_task.cancel()
            self.watchdog_task = None
        if self.scanner:
            await self.scanner.stop()
            self.scanner = None
