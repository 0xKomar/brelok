# breLock — firmware Waveshare PoC

Firmware `0.6.0-poc` dla **Waveshare ESP32-S3-Touch-LCD-1.28**. Cztery ekrany przesuwane w lewo/prawo pokazują ochronę, dystans, kalibrację i ręczną blokadę. START, POMIAR i blokada wymagają ciągłego przytrzymania przez 3 s z animacją pierścienia. Kalibracja prowadzi przez 1, 2 i 3 m: odliczanie 2 s, potwierdzenie pozycji i 12–35 s pomiaru na punkt. PC dopasowuje A oraz n i zapisuje ustawienia po poprawnej całej serii. Nie używamy BOOT/RESET jako przycisków aplikacji ([opis płytki Waveshare](https://docs.waveshare.com/ESP32-S3-Touch-LCD-1.28)). Decyzja o blokadzie pozostaje w jednej aplikacji na komputerze. [Ekrany, źródła UI i protokół GATT](../../DEVICE_UI.md).

Wersję 0.6.0 skompilowano i wgrano na 142D6F020F3C; esptool zweryfikował zapis. Osiem statusów USB potwierdziło gotowy dotyk, IMU, zero błędów i dwukierunkowe GATT z nową aplikacją: ochrona OFF, kreator czeka na punkt 1 m. Wyniki są w `output/guided-calibration-0.6.0-live.jsonl`. Testy hostowe: 107 sprawdzeń firmware. Fizyczna seria 1/2/3 m, gesty i pobór prądu wymagają testu na płytce. Parametry ruchu pozostają wartościami START.

## Co działa w kodzie

- Profil S3: 16 MB Flash, 2 MB QSPI PSRAM, UART przez CH343P.
- QMI8658: wykrywanie adresu `0x6A`/`0x6B`, WHO_AM_I i rewizji, kontrola konfiguracji.
- Akcelerometr ±4 g i żyroskop ±512°/s, ODR 62,5 Hz.
- Usunięcie wolnej składowej przyspieszenia, filtr 8 Hz, RMS z okna 1 s.
- Potwierdzenie ruchu z histerezą i wiek ostatniej aktywności; sama wartość żyroskopu nie ustawia ruchu.
- Pomiar ADC baterii w mV, filtrowanie i lokalne ostrzeżenie o niskim napięciu.
- BLE: ID, boot ID, licznik, ruch, RMS, bateria i flagi ważności; podsumowanie co 200 ms.
- LCD GC9A01A: cztery ekrany, rzeczywisty stan ochrony z PC, przybliżony dystans, kalibracja i blokada. Bufory w PSRAM oraz aktualizacja zmienionych obszarów ograniczają miganie. Profil debug wygasza ekran po 60 s; pierwszy dotyk CST816S tylko go wybudza.
- Dotyk jest odczytywany co 20 ms bez instalacji przerwania GPIO; omija to obserwowaną pętlę restartów IPC podczas inicjalizacji.
- GATT: bieżąca telemetria, stan wysyłany przez komputer oraz komendy z numerem, ACK i identyfikatorem sesji. Puszczenie palca, przesunięcie i utrata hosta anulują przytrzymanie.
- Diagnostyka USB: status JSON, payload hex, liczba próbek/s i opcjonalny surowy CSV.
- Limit czasu operacji I2C i ponawianie inicjalizacji IMU co 2 s. Awaria sensora nie zatrzymuje BLE; nowe pakiety jawnie oznaczają IMU jako nieważne.

Wi-Fi jest wyłączone. GATT działa z wybranym brelokiem, reklamy BLE pozostają aktywne. Ekran pokazuje wynik żądania OS, ale nie potwierdza pojawienia się ekranu logowania.

## Zgodność z aplikacją

**Natywny backend desktopowy Rust obsługuje BLE v2 i v3 na macOS i Windows.** Interfejs wymaga aktualnej aplikacji z kanałem GATT; sama konsola czyta reklamy, ale nie przesyła stanu ochrony ani nie obsługuje zdalnych akcji. Kreator mierzy prawdziwe RSSI w punktach 1, 2 i 3 m i dopasowuje RSSI odniesienia oraz współczynnik n. Próg pochodzi z ostatniego punktu, z marginesem 3–6 dB. Firmware 0.6.0 przyjmuje status GATT v1 i v2; kreator punktów wymaga v2. Stary licznik dotknięć v3 pozostaje w protokole dla zgodności; nowe przyciski wysyłają jawne akcje GATT. Konsola Python `debug_console.py` obsługuje v1/v2/v3; [instrukcja](../desktop/README.md).

Stary beacon v1 jest zachowany w `src/legacy_main.cpp` i ma osobny build `esp32dev`. Domyślnym środowiskiem jest teraz `waveshare-s3-touch`.

## Kompilacja i wgranie

Potrzebne są PlatformIO oraz przewód USB do transmisji danych. Uruchamiaj polecenia z katalogu firmware:

Przed uploadem ustaw ochronę OFF w aplikacji. Reset ESP przerywa telemetrię
i przy aktywnej ochronie może wyzwolić regułę utraty sygnału L1.

```bash
cd products/brelock/apps/firmware-esp32
pio run -e waveshare-s3-touch
pio device list
pio run -e waveshare-s3-touch -t upload
pio device monitor -e waveshare-s3-touch -b 115200 --echo
```

Jeśli podłączonych jest kilka urządzeń, podaj konkretny port przez `--upload-port` przy uploadzie i `--port` przy monitorze. Wybierz port CH343P tej płytki. Profil celowo używa UART0 GPIO43/44, a nie native USB CDC. Gdy automatyczne wejście w bootloader nie zadziała, przytrzymaj BOOT podczas resetu i ponów upload.

Binaria powstają w `.pio/build/waveshare-s3-touch/`. Przy uploadzie PlatformIO wykorzystuje także bootloader i tablicę partycji; nie wgrywaj samego `firmware.bin` pod adres 0.

Stary beacon:

```bash
pio run -e esp32dev
```

## Piny i biblioteki

| Element | Piny / adres |
| --- | --- |
| I2C wspólne dla IMU i dotyku | SDA 6, SCL 7, 400 kHz |
| QMI8658 | `0x6A` lub `0x6B`, oczekiwane WHO_AM_I `0x05` |
| Dotyk CST816S | `0x15`, IRQ 5, reset 13 |
| LCD GC9A01A | DC 8, CS 9, SCLK 10, MOSI 11, MISO 12, reset 14 |
| Podświetlenie | GPIO2; nie jest migającą diodą |
| Bateria | ADC GPIO1, dzielnik 200 kΩ / 100 kΩ, mnożnik 3 |

Piny są zebrane w `include/board_pins.h`. Profil dotyczy wersji **Touch**. Oznaczenie fizycznego sensora i rewizję płytki trzeba sprawdzić na egzemplarzu; WHO_AM_I nie rozstrzyga samodzielnie wariantu A/C.

Przypięte zależności: Espressif32 7.0.1 / Arduino 2.0.17, Adafruit GC9A01A 1.1.0, GFX 1.12.6, BusIO 1.17.4. Podstawą profilu PlatformIO jest DevKitC-1 z nadpisaną pamięcią Waveshare; jego ogólna nazwa w logu kompilacji nie oznacza braku ustawionego PSRAM.

## Telemetria BLE v3

Reklamy mają interwał START 100 ms i nominalną moc +3 dBm. Podsumowanie oraz `sequence` zmieniają się co 200 ms. Dane są aktualizowane asynchronicznie; kod nie przerywa reklamowania przy każdej nowej próbce. `published_sequence` w logu oznacza potwierdzenie konfiguracji przez stos BLE, nie potwierdzenie odbioru przez laptop.

Podstawowy pakiet: Flags 3 B + struktura manufacturer 4 B + dane 24 B = **31 B**. Manufacturer company ID `0xFFFF` jest testowy. Scan response **27 B** zawiera UUID `9e20a100-6f7f-4d8a-9c21-4b52454c4f43` i nazwę `breLock`. Pełne ID jest w podstawowej reklamie, niezależnie od nazwy.

Offsety poniżej liczymy w danych manufacturer **po company ID**, czyli w 24-bajtowym payloadzie przekazanym przez btleplug/Bleak:

| Offset | Pole i jednostka |
| --- | --- |
| 0 | Wersja `3` (odbiornik desktopowy nadal akceptuje v2) |
| 1 | Typ brelok `1` |
| 2–7 | Pełny 6-bajtowy ID, taki jak w starym firmware |
| 8–9 | Losowy 16-bitowy boot ID |
| 10–13 | 32-bitowy licznik podsumowań |
| 14 | Flagi: bit 0 ruch, 1 IMU valid, 2 gyro valid, 3 clipping, 4 bateria valid, 5 dotknięcie w ostatnich 3 s |
| 15–16 | RMS dynamicznego przyspieszenia, mg |
| 17–18 | RMS żyroskopu, 0,1°/s |
| 19–20 | Wiek aktywności, ms; `65535` = brak/nieznany, `65534` = nasycenie wieku |
| 21–22 | Napięcie, mV, interpretowane wyłącznie z flagą valid |
| 23 | Licznik dotknięć modulo 256; v2 używało tu nominalnego TX signed int8 dBm |

Wielobajtowe liczby są little-endian. Zawinięcie `sequence` jest naturalne dla uint32. Boot ID jest losowy, może mieć kolizję; identyfikator i liczniki nie stanowią uwierzytelnienia ani ochrony przed podszyciem/replay.

Brak świeżych próbek, błąd odczytu, nasycenie lub niepełne okno oznacza IMU unknown. Wtedy encoder czyści motion/IMU/gyro valid, zeruje RMS i nadaje nieznany wiek. Powrót danych wymaga zbudowania nowego okna. Niedostępny żyroskop nie unieważnia prawidłowego akcelerometru.

## Log USB i kalibracja

Po resecie log pokazuje ID, adres/WHO_AM_I/rewizję IMU, rozmiar Flash/PSRAM oraz parametry BLE. Wiersz `[LCD]` zawiera przypisanie pinów, wykrycie dotyku i czas wygaszania (`0` = wyłączone). W `0.3.1-poc` poprawiono kolejność DC/CS w konstruktorze Adafruit przyjmującym `SPIClass*`. Gdy używasz monitora, naciśnij RESET, aby zobaczyć pełny start.

| Znak wpisany w monitorze | Działanie |
| --- | --- |
| `r` | Włącza/wyłącza surowy CSV, domyślnie wyłączony |
| `s` | Wypisuje bieżący status JSON |
| `w` | Wybudza ekran także bez działającego dotyku |

Status JSON pojawia się co sekundę przy `BRELOCK_DEBUG=1`. `imu_hz` opisuje nowe próbki odebrane przez firmware w ostatnim interwale pomiarowym, nie samą deklarację ODR. `payload_hex` jest podsumowaniem wskazanym przez `sequence`; `published_sequence` może być chwilowo wcześniejszy. Status wywołany ręcznie przez `s` pokazuje ostatnią wyliczoną częstotliwość.

Pola `gatt_connected`, `host_fresh`, `host_protection`, `host_distance_cm`, `host_rssi_dbm`, `host_calibration`, `host_feedback` i `host_ack` pokazują stan kanału sterowania. Dystans `65535` i RSSI `-128` oznaczają brak bieżącego pomiaru. Stan PC wygasa po 2,5 s bez aktualizacji.

CSV zawiera: `raw,ms,sensor_counter,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,gyro_valid,clipped`. Kolumny przyspieszenia są w g, a wartości payloadu są w mg. Licznik sensora jest 24-bitowy. Firmware pomija duplikaty oraz ogranicza zapis USB; przepełnienie bufora zwiększa `usb_dropped` i nie blokuje pętli odczytów.

Aby zapisać przebieg z monitora:

```bash
pio device monitor -e waveshare-s3-touch -b 115200 --echo --filter log2file
```

Ustawienia START są w `include/config.h`: wejście w ruch 60 mg przez 200 ms, wyjście 35 mg przez 1,5 s, okno RMS 1 s. To hipotezy, nie pomiary ani progi producenta. Walidacja wymaga co najmniej 40 nowych próbek obejmujących 840 ms; próg dobrano po pomiarze około 46 próbek/s na tej płytce. Przerwa ponad 100 ms wymaga ponownego zbudowania okna. Żyroskop jest na razie aktywny stale; oszczędzanie energii oceniamy po nagraniach.

Napięcie mierzymy `analogReadMilliVolts` i mnożymy przez dzielnik, z możliwością korekty gain/offset. Sprawdź je miernikiem. Ostrzeżenie LOW ma próg START 3,5 V, a prawdopodobny zakres 2,5–4,5 V. Wartość nie jest procentem baterii ani pewną detekcją podłączenia ogniwa; USB i ładowarka mogą wpływać na pomiar. Pobór całej płytki trzeba zmierzyć z baterii w docelowej obudowie.

## Sprawdzenia przed testem sprzętu

```bash
python3 tools/run_host_tests.py
pio run -e waveshare-s3-touch
pio run -e esp32dev
```

Build firmware `0.5.0-poc` z 3 października 2026: sukces; RAM statyczny 48 256 B, Flash aplikacji 996 481 B. Dwa bufory LCD zajmują dodatkowo 230 400 B w PSRAM. Testy hostowe: 50 sprawdzeń protokołu/ruchu i 32 gestów/przytrzymania/GATT — PASS. Po uploadzie log potwierdził BLE v3, działający IMU (`motion_valid=true`, około 56 próbek/s), CST816S bez błędów I²C oraz `gatt_connected=true`, `host_fresh=true` i przesyłanie RSSI/dystansu. Nie wykonano jeszcze fizycznego dotknięcia ekranu ani blokady OS.

Sprawdzone 1 października 2026:

- Build Waveshare: sukces; RAM statyczny 48 104 B, kod/dane aplikacji 962 753 B (plik obrazu 963 120 B).
- Build starego `esp32dev`: sukces; zachowany beacon v1.
- 48 sprawdzeń kodu protokołu/ruchu: wzorcowy pakiet, endian, AD lengths, jednostki, flags, warmup, spoczynek, aktywność, szum, wiek, clipping, awaria/odzyskanie, duplikaty, brak gyro i wrap timerów.

Testy hostowe kompilują rzeczywiste `motion.cpp`, `telemetry.cpp`, `control.cpp` i `device_ui.cpp`, bez atrap Arduino. Nie potwierdzają fizycznego działania I2C, LCD, radia ani blokady komputera. `python3 tools/render_ui_preview.py` kompiluje prawdziwy renderer Adafruit GFX i zapisuje podgląd w `output/device-ui/device-ui.png`.

## Pierwszy test na Waveshare

1. Sprawdź boot log: Flash 16 MB, PSRAM 2 MB, adres sensora, WHO_AM_I i rewizję.
2. W spoczynku sprawdź surowe przyspieszenie o normie około 1 g i odbiór około 62,5 nowych próbek/s. RMS po warmup ma być niewielki, bez stale aktywnego clipping.
3. Poruszaj brelokiem, odłóż go i sprawdź potwierdzenie/wygaśnięcie ruchu oraz wiek. Zapisz przebieg przez `r`.
4. Porównaj napięcie z miernikiem i zobacz ostrzeżenie przy błędnym odczycie.
5. Sprawdź wygaszenie po 60 s i wybudzenie dotykiem; nadal mają napływać nowe pakiety BLE.
6. W katalogu `apps/desktop/native` uruchom `cargo run --locked -p brelock-desktop -- scan --duration 10`, następnie `monitor --device-id TWOJE_ID --duration 60 --log logs/walk-01.jsonl` przez ten sam program. Porównaj `sequence`, HEX, RMS i napięcie z logiem USB; `decode --hex PAYLOAD` pozwala porównać pojedynczy payload bez BLE. Alternatywnie użyj referencyjnej konsoli Python opisanej wyżej.
7. Na breloku otwórz Kalibrację i przytrzymaj START przez 3 s. Na PC ustaw rzeczywistą odległość, np. 4 m, i zatwierdź zmianę. Odejdź na tę odległość, przytrzymaj POMIAR przez 3 s, następnie pozostań w miejscu przez 12–35 s. Sprawdź zapis progu oraz dopasowanie metrów. Ochronę włącz osobno po powrocie do komputera.
8. Na ekranie Blokada puść palec przed 3 s i sprawdź anulowanie; następnie świadomie sprawdź pełne przytrzymanie oraz pojedynczą blokadę. Na macOS aplikacja wymaga uprawnienia Dostępność.
9. Sprawdź błędy/odzyskanie sensora i nadawanie bez IMU, a następnie pobór prądu z wygaszonym ekranem.

## Źródła

- [Waveshare — sprzęt i interfejsy](https://docs.waveshare.com/ESP32-S3-Touch-LCD-1.28).
- [Waveshare — oficjalne przykłady i schematy](https://docs.waveshare.com/ESP32-S3-Touch-LCD-1.28/Resources-And-Documents).
- [QMI8658C — dokumentacja rejestrów](https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-1.28/QMI8658C.pdf); wariant fizyczny do potwierdzenia.
- [Espressif — GAP API dla stosu używanego przez Arduino 2.x](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32s3/api-reference/bluetooth/esp_gap_ble.html).
- [Adafruit — GC9A01A](https://github.com/adafruit/Adafruit_GC9A01A).
