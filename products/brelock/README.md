# breLock

breLock rozwijamy jako PoC: **jedna lokalna aplikacja na komputerze i jeden
brelok Waveshare ESP32-S3-Touch-LCD-1.28**. Aplikacja łączy RSSI z informacją
o ruchu z IMU, żeby wykrywać odejście i blokować sesję systemu.

Status, wykresy, ustawienia i kalibracja są w tej samej aplikacji. Dane zapisujemy
lokalnie. Plan PoC nie obejmuje panelu administratora, serwera, kont ani strony.

> [Aktualny plan PoC: architektura, reguły blokowania i kroki implementacji](ARCHITEKTURA_WAVESHARE_BRELOCK.md)

> [Plan małej aplikacji: funkcje, układ okna, tray i praca w tle](PLAN_APLIKACJI_DESKTOPOWEJ.md)

> [Cztery ekrany breloka: gesty, kalibracja, dystans, status i zdalna blokada](DEVICE_UI.md)

> [Analiza istniejącego kodu i znaczenie ustaleń dla PoC](README_ANALIZA.md)

Pierwszy frontend działa w Tauri 2 + Svelte 5 + TypeScript + Vite + CSS:
granatowe okno, oddychający ON/OFF, Status, Diagnostyka i Ustawienia.
Host obsługuje ikonę na pasku oraz zamknięcie okna do tła z działającym backendem.
Ochrona OS i kalibracja są zaimplementowane; autostart oraz pełny sleep/wake pozostają kolejnymi etapami.
[Podgląd i uruchomienie aplikacji](apps/desktop/native/ui/README.md).

## Dwie części PoC

- `apps/desktop/native` — docelowy backend **Rust**, natywny build dla macOS
  i Windows: rdzeń telemetrii, BLE, konfiguracja, lokalny zapis i API aplikacji.
  Ma także host Tauri i frontend w `native/ui`.
- `apps/firmware-esp32` — firmware breloka; BLE/GATT, IMU, bateria i cztery ekrany przesuwane dotykiem.

Firmware Waveshare `0.5.0-poc` jest skompilowany i wgrany: profil S3,
IMU, bateria, ekran/dotyk, BLE v3 i dwukierunkowe GATT. Log sprzętu potwierdza
przesyłanie stanu komputera i przybliżonego dystansu. [Wgranie oraz test sprzętowy](apps/firmware-esp32/README.md)
opisuje README urządzenia. Fizyczne gesty i kalibracja w docelowej lokalizacji wymagają testu użytkownika.

Backend Rust ma parser v2/v3, filtry/świeżość, natywny skaner, kanał GATT, reguły
ochrony i adapter OS, kalibrację, konfigurację JSON, log i demo/decoder HEX. Jeden kod budujemy na obu systemach; CI przygotowuje
osobne artefakty. [Struktura, kompilacja i uruchomienie](apps/desktop/native/README.md).

`debug_console.py` pozostaje referencyjną konsolą Python/Bleak do pomiarów;
jej 52 testy przeszły. [Instrukcja konsoli Python](apps/desktop/README.md).

Stary `main.py`/GUI nadal używa konfiguracji centralnej i dekodera v1 i jest historyczną ścieżką projektu.

Historyczne `apps/control-plane`, `apps/website` oraz `variants/desktop-sm1go`
pozostają w repozytorium, ale nie są rozwijane ani wymagane przez plan PoC.

## Kolejność implementacji

1. Samodzielna aplikacja i lokalna konfiguracja.
2. Uruchomienie Waveshare: IMU, bateria, ekran i BLE.
3. Telemetria BLE i lokalny zapis pomiarów.
4. Silnik decyzji oraz tryb obserwacji.
5. Mały interfejs, tray, praca w tle, wykresy i kalibracja w jednym oknie.
6. Rzeczywista blokada OS, sleep/wake i obsługa błędów.
7. Demonstracja, porównanie RSSI z RSSI+IMU i korekta progów.

Szczegóły i kryteria odbioru są w [planie PoC](ARCHITEKTURA_WAVESHARE_BRELOCK.md#8-kroki-implementacji).

## Kompilacja i demo natywnego backendu

```bash
cd products/brelock/apps/desktop/native
cargo build --release --locked -p brelock-desktop
cargo run --locked -p brelock-desktop -- demo --duration 5
```

Polecenia są wspólne dla macOS i Windows po przygotowaniu Rust i natywnych
narzędzi kompilacji. Gotowy program nie wymaga Pythona. Konsola służy do
obserwacji pomiarów; ochronę i sterowanie z breloka obsługuje host Tauri.
