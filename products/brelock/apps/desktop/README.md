# breLock desktop — backend Rust i konsola PoC

Docelowa struktura aplikacji jest w **[native/ — backend Rust](native/README.md)**.
Projekt Cargo kompiluje jeden natywny program dla macOS i Windows. Ma rdzeń
telemetrii, transport BLE, lokalną konfigurację, zapis oraz API stanu aplikacji.
Pierwszy [frontend Tauri/Svelte](native/ui/README.md) jest już dodany: małe granatowe okno, oddychający ON/OFF, trzy widoki i praca w tle. Natywny backend nadal działa w OBSERVE, bez blokowania systemu.

Poniżej pozostaje instrukcja referencyjnej konsoli Python do debugowania
urządzenia. Nowy backend Rust rozwijamy w `native/`.

`debug_console.py` to samodzielny odbiornik do debugowania jednej pary komputer–brelok Waveshare. Czyta reklamy BLE v2 z [firmware urządzenia](../firmware-esp32/README.md), wyświetla dane i opcjonalnie zapisuje lokalny ślad JSONL. Działa w trybie **OBSERVE**, bez wykonywania blokad systemu.

## Uruchomienie

Python **3.10+**, adapter Bluetooth LE i wgrany firmware `waveshare-s3-touch`. Jedyną zależnością konsoli jest Bleak; dla demo i dekodowania HEX wystarcza standardowy Python.

Z katalogu `products/brelock/apps/desktop`:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-console.txt
python debug_console.py
```

Na Windows: `python -m venv venv`, potem `venv\Scripts\activate`. Pozostałe polecenia są takie same.

Bez `--device-id` aplikacja skanuje przez 5 sekund od uruchomienia skanera i wybiera jedyny znaleziony brelok. Jeśli znajdzie kilka, wypisuje ID i kończy z prośbą o jawny wybór. Raz wybranego ID nie podmienia automatycznie. Wszystkie breloki mogą mieć tę samą nazwę `breLock`.

```bash
# Lista pełnych ID (domyślnie 10 s)
python debug_console.py --list

# Podstaw ID widoczne na ekranie urządzenia lub w --list
python debug_console.py --device-id A1B2C3D4E5F6

# Nagranie do nowego pliku; katalog powstanie automatycznie
python debug_console.py --device-id A1B2C3D4E5F6 --log logs/pomiary-01.jsonl

# Wolniejsze odświeżanie, kolejne wiersze, sesja 60 s
python debug_console.py --device-id A1B2C3D4E5F6 --plain --refresh 1 --duration 60

# Dane w formacie maszynowym na stdout
python debug_console.py --device-id A1B2C3D4E5F6 --json
```

`Ctrl+C` zatrzymuje skaner i zamyka log. W dużym terminalu ekran jest odświeżany; w małym, przez pipe i z `--plain` dane trafiają do kolejnych wierszy. Dla pełnego panelu powiększ terminal do około 120 kolumn i 35 wierszy. `--duration` obejmuje całą sesję, łącznie ze startem skanera i wykrywaniem ID.

## Wyświetlane dane

| Dane | Znaczenie |
| --- | --- |
| ID, nazwa, adres/UUID BLE, wersja | Dopasowanie następuje po 12 znakach sprzętowego ID z payloadu, także gdy nazwy jeszcze nie odebrano. Na macOS adres skanera jest UUID, nie MAC breloka. |
| RSSI surowy i filtrowany, dBm | Filtr: mediany przedziałów 250 ms, mediana 750 ms, EMA ze stałą czasu 0,8 s. Minimum dwa niepuste przedziały. |
| Dystans `~m` | Obliczenie z modelu RSSI; START `A=-59 dBm @1m`, `n=2,2`. To ustawienia do kalibracji, a nie dane katalogowe Waveshare. |
| Prędkość radialna `~m/s` | Tempo zmiany modelowego dystansu wyprowadzone z trendu RSSI; `+` oznacza oddalanie, `-` zbliżanie. To estymacja względna względem laptopa. |
| Trend dB/s, R², szum resztowy, pokrycie | Regresja filtrowanego RSSI w oknie 3 s: ≥6 punktów, rozpiętość ≥2,4 s, pokrycie ≥80%. Prędkość jest dostępna dopiero przy R²≥0,5. |
| Ruch/spoczynek/nieznany | Klasyfikacja wykonana przez firmware. Nieważne IMU lub stary pakiet daje `unknown`, nie spoczynek. |
| Przyspieszenie RMS, mg i m/s² | RMS dynamicznego przyspieszenia po odjęciu grawitacji przez firmware. To nie surowy wektor XYZ. |
| Obrót RMS, °/s | Przesłane `gyro_rms_deci_dps / 10`. Nie jest to prędkość przemieszczania. |
| Wiek ruchu i ruch w ostatnich 5 s | Wiek przesłany przez brelok + czas od odebrania nowego pakietu. `65535` oznacza nieznany; `65534` dolną granicę wieku, pokazywaną jako `>=`. |
| IMU/gyro valid i clipping | Stan czujników, niezależny od stanu radia. |
| Bateria, mV/V, niska bateria | Napięcie tylko przy ważnej fladze baterii. START niskiego napięcia to 3500 mV; bez procentów i prognozy czasu pracy. |
| TX nominalny, dBm | Pole nadajnika; nie jest zmierzonym RSSI przy 1 m ani parametrem `A`. |
| Boot, sequence, flags, payload HEX | Porównanie z USB i diagnostyka formatu v2. |
| Nowe podsumowania Hz i callbacki Hz | Częstotliwość po stronie laptopa, w oknie do 5 s; nie częstotliwość próbkowania IMU. |
| Duplikaty, pominięte seq, stare pakiety, konflikty, restarty | Liczniki odbioru; pominięte numery to niewidziane podsumowania, nie pomiar strat pakietów radiowych. |
| Wiek nowego pakietu i callbacku, błędy | Pokazują m.in. powtarzanie starej telemetrii mimo kolejnych wywołań callbacku. |

**Prędkość rzeczywista pozostaje `n/d`.** BLE v2 przesyła RMS oraz informację o ruchu, bez wektora przyspieszenia/orientacji i bez pomiaru prędkości. Z tych pól nie da się poprawnie zintegrować liniowej prędkości. Szum, pozycja ciała i zmiana orientacji anteny wpływają również na wynik RSSI; estymacja radialna może zmieniać się przy nieruchomym breloku. IMU jest osobną przesłanką, a nie korektą prędkości.

Model używany przez konsolę:

```text
d = 10 ** ((A - RSSI_filtrowany) / (10 * n))
v_rad = -ln(10) * d * slope_RSSI / (10 * n)
```

Wstępne dostrojenie modelu:

```bash
python debug_console.py --device-id A1B2C3D4E5F6 --reference-rssi -64 --path-loss 2.6
```

Są to przykładowe wartości; właściwe `A` trzeba zmierzyć w odległości 1 m dla konkretnej pary i sposobu noszenia urządzenia. Płaski albo niespójny trend daje prędkość `n/d`, zamiast nieuzasadnionej wartości 0.

## Świeżość i błędy

- `WAITING`: wybrany ID nie dostarczył jeszcze poprawnego pakietu.
- `LIVE`: nowy poprawny pakiet v2 ma wiek ≤1,5 s.
- `STALE`: wiek >1,5 s. Bieżące czujniki, dystans i prędkość są `n/d`.
- `LOST`: wiek ≥6 s. To status diagnostyczny w OBSERVE.
- `LEGACY`: v1, dostępne ID/RSSI, bez IMU, baterii i sprawdzania świeżości licznikiem.

Dla v2 duplikat nie odświeża wieku pakietu ani ruchu. Jego RSSI można wykorzystać jedynie w czasie świeżości oryginalnego podsumowania. Odrzucamy stare numery i duplikaty z inną treścią. Obsługujemy zawinięcie licznika uint32; nowy `boot_id` resetuje filtr i trend, a ostatnie stare boot ID są odrzucane. Przerwa ponad 1,5 s również resetuje historię przy powrocie. Liczniki nie stanowią uwierzytelnienia; 16-bitowy `boot_id` może się powtórzyć i w PoC wymagać restartu odbiornika.

Parser sprawdza dokładną długość, flagi, sentinele i zakres baterii zgodny z firmware. Zły payload nie odświeża telemetrii. Brak pomiaru RSSI również nie podtrzymuje poprzedniego sygnału jako bieżącego.

Błąd startu skanera jest wypisywany i zapisany w logu; kolejne próby mają odstępy od 0,5 s do 5 s. Konsola nadal odświeża status. Włącz Bluetooth oraz przyznaj używanemu terminalowi/aplikacji uprawnienia Bluetooth, jeśli system zgłosi ich brak. Na macOS 12.0–12.2 wymagany filtr UUID jest dodawany automatycznie; legacy v1 bez tego UUID może być wtedy niewidoczny. [Dokumentacja Bleak: skaner](https://bleak.readthedocs.io/en/latest/api/scanner.html), [macOS](https://bleak.readthedocs.io/en/latest/backends/macos.html).

Kody zakończenia: `0` normalny koniec/Ctrl+C, `2` błąd argumentów/pliku/skanera lub kilka ID przy automatycznym wyborze, `3` brak oczekiwanego breloka. Bez limitu czasu jawnie wybrany ID może pozostawać w `WAITING` do Ctrl+C.

## Próby bez urządzenia

```bash
python3 debug_console.py --demo
python3 debug_console.py --demo --duration 26 --refresh 1 --plain
python3 debug_console.py --decode-hex 0201123456789ABC3412EFCDAB89177B00C8011503A00FFD --rssi -65
```

Demo jest wyraźnie oznaczone jako **syntetyczne**. Cykl 32 s: spoczynek 0–5 s, oddalanie 5–14 s, zanik odbioru 14–22 s, powrót 22–32 s. Generuje prawdziwy format v2 i duplikaty, a potem korzysta z tego samego parsera i filtrów co BLE. ID demo to `A1B2C3D4E5F6`.

`--decode-hex` przyjmuje `payload_hex` z JSON USB firmware, **bez** dwubajtowego company ID. Jeden pakiet pozwala sprawdzić jednostki i pola; filtr dystansu oraz trend wymagają kolejnych próbek, więc w tym trybie pozostają `n/d`.

## Log i podział kodu

`--log` tworzy nowy plik JSONL i odmawia nadpisania istniejącego. Każda linia zawiera typ rekordu i UTC czasu zapisu. `t_s` to czas monotoniczny względem początku sesji; dla reklamy pochodzi z callbacku, także gdy kolejka zostanie opróżniona później.

Typy rekordów: `session` z aktywnymi parametrami, `advertisement` z surowym payloadem/RSSI oraz wynikiem dekodowania, `invalid_packet`, `scanner_error`, `selected`, `snapshot`, `end`. `--json` wypisuje na stdout sesję, wyniki i zdarzenia skanera; pełny ślad reklam trafia do pliku `--log`. Bieżące wartości przy starych danych są `null`; ostatni odebrany pakiet pozostaje osobno w `last_packet`, a jego HEX w `payload_hex`.

- `debug_console.py`: CLI, transport Bleak, kolejka callbacków, prezentacja, log oraz źródła demo/HEX.
- `telemetry_protocol.py`: niezależny decoder v1/v2 i walidacja ID.
- `telemetry_monitor.py`: filtrowanie według czasu, trend, model dystansu/prędkości i świeżość.
- `requirements-console.txt`: minimalne zależności tego trybu aplikacji.

Dotychczasowy `main.py` i GUI to starsza ścieżka z konfiguracją centralną i dekoderem v1. `debug_console.py` pozostaje narzędziem referencyjnym do pomiarów. Docelową aplikację rozwijamy w **`native/` (Rust + Tauri/Svelte)**. Pierwszy frontend jest dostępny; reguły blokowania pozostają kolejnym etapem [planu implementacji](../../ARCHITEKTURA_WAVESHARE_BRELOCK.md#8-kroki-implementacji).

## Weryfikacja

```bash
python3 -m unittest discover -s tests -v
```

Sprawdzone 1 października 2026: 52 testy desktopu, dekodowanie wzorcowego payloadu z testów C++, demo z oddalaniem/utratą/powrotem, zapis JSONL, błędy startu i ponawianie skanera, jego zatrzymanie i obce ID. Testy używają kontrolowanego czasu i skanera zastępczego. Odbiór fizycznej płytki oraz kalibracja pozostają do sprawdzenia: lokalna próba Bleak w środowisku wykonawczym zgłosiła `Bluetooth is unsupported / NO_BLUETOOTH`.

Podstawa ograniczeń modelu odległości: [Bluetooth SIG — Distance and RSSI](https://www.bluetooth.com/blog/proximity-and-rssi/). Parametry modelu i wzór pochodzą z planu PoC i istniejących ustawień projektu, a nie z pomiarów tego urządzenia.
