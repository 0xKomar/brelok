# Pierwsze uruchomienie breLock — 3 października 2026

- Wgrano firmware `0.3.0-poc`, profil PlatformIO `waveshare-s3-touch`.
- Port: `/dev/cu.usbmodem5B910447981`, USB VID/PID `1A86:55D3`.
- Esptool potwierdził ESP32-S3, rewizję `v0.2` i wbudowane 2 MB PSRAM. Zapis bootloadera, partycji i aplikacji zakończył się poprawną weryfikacją hashów.
- Boot log: Flash `16777216 B`, dostępne PSRAM `2095071 B`.
- ID używane przez aplikację i payload: **`142D6F020F3C`**. MAC raportowany przez esptool: `3C:0F:02:6F:2D:14`; identyfikator w payloadzie używa dotychczasowej kolejności firmware.
- IMU: adres `0x6B`, WHO_AM_I `0x05`, rewizja `0x7C`. Konfiguracja: ±4 g, ±512°/s, zadane ODR 62,5 Hz.
- Uruchomiono istniejącą aplikację natywną `native/target/release/bundle/macos/breLock.app` i wybrano ID płytki w ustawieniach.
- W GUI potwierdzono aktualne dane z BLE: RSSI surowe/filtrowane, RMS przyspieszenia, RMS żyroskopu, napięcie i wiek pakietu około 0,2 s. Przykładowy odczyt blisko laptopa: −44 dBm i 4,11 V.

## Zapisane dane

- `apps/desktop/native/logs/2026-10-03-usb-check-1791021550814495000.log` — boot, identyfikacja i statusy USB.
- `apps/desktop/native/logs/2026-10-03-imu-baseline-1791021765716071000.log` — boot, statusy i **375 surowych próbek IMU**.
- W drugiej sesji włączono CSV po rozruchu, a następnie potwierdzono jego wyłączenie. Port monitora USB został zamknięty.
- W ostatnim statusie: `ble_ok=true`, `ble_errors=0`, `imu_errors=0`, `usb_dropped=0`, `sequence=published_sequence=54`, IMU i gyro valid.
- Otrzymane próbki obejmują 6,951 s: średnio **53,81 Hz**, największa przerwa 63 ms. To częstotliwość rzeczywistego odbioru przez firmware, niższa od zadanego ODR 62,5 Hz; przyczyna wymaga dalszego sprawdzenia.
- Brak próbek oznaczonych jako clipped.
- Średnia norma przyspieszenia: **1,0527 g**. Średnie osie: `[0,06334; 0,32330; −0,99980] g`.
- Średnie osie żyroskopu: `[0,288; 2,453; −0,171] °/s`. Nie zastosowano korekty offsetów; pomiar należy powtórzyć na nieruchomej płytce przed wyznaczeniem biasu.
- Napięcie ADC około 4,11 V zostało odczytane przy podłączonym USB. Nie zostało porównane z multimetrem i nie jest procentem baterii.

## Jak zacząć testować

- W **Diagnostyce** obserwować RSSI, RMS i ważność IMU. Sprawdzić reakcję na poruszenie brelokiem i jego odłożenie.
- Wykonać około 60 s zwykłej pracy przy laptopie w docelowym miejscu noszenia breloka.
- Ustawić brelok w znanej odległości 1 m od laptopa, odczekać na stabilizację filtra i przez około 60 s obserwować filtrowane RSSI. Typowy poziom jest pierwszym przybliżeniem parametru **RSSI przy 1 m** w Ustawieniach.
- Powtórzyć próby przy większych znanych odległościach, w kieszeni i podczas odejścia/powrotu. Parametr `n=2,2` pozostaje startowy, dopóki nie dopasujemy go do nagrań.
- Przycisk kopiowania w Diagnostyce eksportuje bieżący raport JSON. GUI nie nagrywa jeszcze pełnej sesji do JSONL; zapis długich sesji jest dostępny w konsoli opisanej w `apps/desktop/native/README.md`. Przy takiej próbie zakończyć GUI z menu breLock, aby używać jednego skanera.

## Zakres potwierdzenia

- To test uruchomienia urządzenia i odbioru na tym Macu, nie zakończona kalibracja.
- Aplikacja działa w **OBSERVE**. ON/OFF pozostaje nieaktywny, ponieważ reguły decyzji i rzeczywista blokada systemu są jeszcze do wdrożenia.
- Dystans i zmiana dystansu są estymacjami RSSI. Parametry `A=−59`, `n=2,2` pozostają wartościami START.
- Dotyk, pobór prądu, dokładność ADC, działanie na baterii, docelowa obudowa i Windows wymagają osobnych testów. Problemy transportu wskazane w audycie pozostają otwarte; firmware i kod aplikacji nie były zmieniane w tej sesji.

## Poprawka LCD po zgłoszeniu braku obrazu

- W konstruktorze `Adafruit_GC9A01A(SPIClass*, dc, cs, rst)` firmware przekazywało CS przed DC. Poprawiono kolejność na DC GPIO8, CS GPIO9. Pozostałe piny nie były zmieniane.
- Wgrano `0.3.1-poc`, a esptool potwierdził poprawne hashe zapisu. Przeszło 48 hostowych sprawdzeń protokołu i ruchu oraz build Waveshare.
- Profil debug do kalibracji ma wyłączone automatyczne wygaszanie. Profil bez debug zachowuje 10 s. Zerowy czas jest jawnie obsługiwany jako brak wygaszania.
- Dodano diagnostykę startu `[LCD]`: `dc=8 cs=9 rst=14 sclk=10 mosi=11 bl=2 touch_ready=1 touch_id=0xB5 auto_sleep_ms=0`.
- Log po poprawce: `apps/desktop/native/logs/2026-10-03-lcd-fix-1791022867171990000.log`.
- Ostatni status po 14,559 s: firmware `0.3.1-poc`, `ble_ok=true`, `ble_errors=0`, `imu_errors=0`, `usb_dropped=0`, IMU/gyro valid. Licznik wygenerowany i opublikowany wynosi 64.
- Log USB potwierdza działanie poprawionego firmware i wykrycie kontrolera dotyku; wygląd obrazu na fizycznym LCD wymaga potwierdzenia przez użytkownika.
