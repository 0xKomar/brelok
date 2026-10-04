# breLock — okrągły ekran 240 × 240, firmware 0.6.0

Jeden brelok Waveshare ESP32-S3-Touch-LCD-1.28 i jedna aplikacja desktopowa.
Gest w lewo przechodzi do następnego ekranu, w prawo do poprzedniego.
Po ostatnim ekranie wraca pierwszy. Kropki u dołu pokazują aktualną stronę.

## Wygląd i znalezione przykłady

Granatowe tło, jasna typografia, pierścienie i ikony tarczy, celu oraz kłódki.
Zielony oznacza aktywną ochronę, czerwony wyłączoną ochronę i akcję blokady,
bursztynowy oczekiwanie na powrót, szary brak danych z komputera.

Źródła inspiracji, bez kopiowania aplikacji demonstracyjnych:

- [Oficjalne demo Waveshare dla tej płytki](https://www.waveshare.com/wiki/ESP32-S3-Touch-LCD-1.28): LVGL_Arduino, benchmark i music.
- [LVGL: okrągłe wskaźniki](https://lvgl.io/docs/open/examples/widgets/scale): centralna wartość i łuk.
- [LVGL Tileview](https://lvgl.io/docs/open/widgets/tileview): przechodzenie gestem między ekranami.
- [GC9A01 + ESP32-S3 — przykład autora interfejsu](https://github.com/UsefulElectronics/esp32s3-gc9a01-lvgl).
- [Waveshare: rejestry CST816S](https://files.waveshare.com/upload/c/c2/CST816S_register_declaration.pdf): współrzędne, gesty, ciągłe IRQ i standby.

Firmware wykorzystuje istniejący Adafruit GFX, zachowując sprawdzone piny LCD
i obsługę sensorów. Nie wymaga instalacji LVGL. Dwa bufory RGB565 w PSRAM
zajmują 230 400 bajtów. Rysowanie odbywa się w pamięci, a LCD otrzymuje
jedynie zmienione prostokąty. Animacja przytrzymania aktualizuje się co 50 ms;
cały fizyczny panel nie jest czyszczony przy odświeżaniu.

## Ekrany

| Ekran | Zawartość | Obsługa |
| --- | --- | --- |
| Ochrona | Stan z aplikacji: aktywna, wyłączona, oczekiwanie na powrót lub brak PC | Gest przełącza stronę |
| Dystans | Przybliżone metry z RSSI, RSSI i ruch; brak wartości po utracie danych | Gest przełącza stronę |
| Kalibracja | START, punkt 1/2/3 m, odliczanie 2 s, niebieski pierścień i wynik | Przytrzymaj START przez 3 s; w każdym punkcie potwierdź pozycję, przytrzymując POMIAR przez 3 s; zapis po całej serii |
| Blokada | Kłódka i pierścień wypełniany przez 3 s | Przytrzymanie środka; puszczenie, ruch lub utrata PC anuluje |

Tap na wygaszonym ekranie tylko go budzi. Kolejny tap/gest wykonuje akcję.
Dotknięcia na ekranach Ochrona i Dystans nie zmieniają progu.
START wyłącza automatyczną ochronę na czas kalibracji; po zapisaniu trzeba
włączyć ją osobno w aplikacji. Ręczna blokada działa także przy ochronie OFF,
o ile system pozwala na blokadę sesji.

Brelok pokazuje wynik otrzymany z aplikacji. „ZADANIE WYSLANE” oznacza wysłanie
żądania do systemu, nie potwierdzenie ekranu logowania. Przy braku uprawnienia
Dostępność na macOS ekran Blokada pokazuje „BRAK UPRAWNIEN”.

## Komunikacja z komputerem

Reklamy BLE v3 pozostają kompatybilne z konsolą diagnostyczną.
Trzy nowe charakterystyki GATT mają sufiks 6f7f-4d8a-9c21-4b52454c4f43:

| Początek UUID | Kierunek | Zawartość |
| --- | --- | --- |
| 9e20a101 | Brelok → PC, READ | Telemetria v3, 24 bajty |
| 9e20a102 | PC → brelok, WRITE | Ochrona, możliwości OS, kalibracja, punkt, odliczanie, RSSI, dystans, ACK i sesja; 20 bajtów |
| 9e20a103 | Brelok → PC, READ | Ostatnia akcja, licznik i sesja; 12 bajtów |

Host łączy się tylko z wybranym ID i sprawdza je również w telemetrii GATT.
Czyta bieżącą telemetrię co 200 ms, a stan ekranu zapisuje co 400 ms.
Na macOS read_rssi() odczytuje sygnał aktywnego połączenia niezależnie od
GATT: jedna oczekująca operacja RSSI nie blokuje telemetrii ani statusu.
Na Windows RSSI pochodzi wyłącznie z rzeczywistych reklam. Polling GATT
nie wytwarza świeżej próbki RSSI przez odczyt cache'u. Firmware kontynuuje
niepołączeniowe reklamy także przy aktywnym GATT.

Stan PC traci ważność po 2,5 s bez zapisu: ekran nie pokazuje starego ON
ani dystansu. Licznik, ACK i identyfikator sesji zapobiegają wielokrotnemu
wykonaniu komendy i przeniesieniu jej między uruchomieniami aplikacji.
Po reconnectcie sesja się zmienia, więc reset licznika po stronie breloka
nie blokuje następnych akcji, a wcześniejsze żądania tracą ważność.
Ten mechanizm PoC nie zastępuje szyfrowanego parowania/bondingu.
Status GATT v2 zachowuje 20 bajtów: dolny nibble bajtu 7 oznacza punkt 1–3,
górny nibble odliczanie 0–2 s. `calibration=5` oznacza przejście do punktu,
`4` zbieranie, `1` oczekiwanie na potwierdzenie, `2` ukończoną serię,
`3` ponowienie bieżącego punktu. Firmware przyjmuje także dawny status v1
z zerowym bajtem 7; format komend pozostaje bez zmian.

Kalibracja zbiera RSSI **po** oznaczeniu każdego miejsca przyciskiem POMIAR.
Pierwsze 2 s ignoruje ruch ręki po dotknięciu. Zbieranie trwa minimum 10 s,
minimum 8 rzeczywistych odczytów obejmujących 8 s; przy wolniejszym odbiorze
pomiar wydłuża się automatycznie do 35 s. Okno jakości obejmuje maksymalnie
ostatnie 20 s. Nie liczymy powielonych przez timer wartości, nieważnego RSSI
ani serii duplikatów. Ostatni odczyt ma najwyżej 2,5 s; przerwy >3,5 s i dryf
median początku/końca >8 dB opóźniają zapis. MAD i połowa IQR muszą być ≤8 dB.
Margines wynosi 3–6 dB, zależnie od dyspersji; próg to mediana z punktu 3 m
minus margines. Punkty 1 i 2 m mogą mieć silniejszy sygnał niż dozwolony
próg odejścia, ponieważ służą dopasowaniu modelu.
To parametry PoC do dalszej kalibracji w miejscu noszenia, nie gwarancja odległości.

START wyłącza ochronę i otwiera serię 1 → 2 → 3 m. Przed każdym punktem jest
odliczanie 2 s i oczekiwanie na potwierdzenie fizycznej pozycji. Sam timer
nie uruchamia pomiaru: użytkownik może potrzebować więcej czasu na przejście.
POMIAR uruchamia zbieranie w bieżącym punkcie. Po poprawnym odczycie aplikacja
prosi o cofnięcie o kolejny metr, a po punkcie 3 m dopasowuje i zapisuje model.
START i POMIAR wymagają ciągłego przytrzymania przez 3 s;
niebieskie kółko i odliczanie działają tak samo jak czerwona animacja blokady.
Puszczenie, przesunięcie, zmiana sesji/statusu lub utrata PC anulują gest.
Kalibracja nie wymaga uprawnienia OS do blokady. Jedno przytrzymanie wysyła
jedną akcję. Status GATT `calibration=4` oznacza pomiar w toku i blokuje
kolejne próby uruchomienia. Postęp nie cofa się.
Zanik GATT lub timeout wymagają ponowienia bieżącego punktu. Restart breloka,
błąd dopasowania lub zapisu wymagają całej serii od 1 m. Wszystkie te sytuacje
oraz anulowanie zachowują poprzednie ustawienia. Kreator można anulować na PC.
Przycisk „Jestem na … m — rozpocznij pomiar” korzysta z tej samej logiki.
START/POMIAR z breloka automatycznie otwiera kreator na komputerze.

### Dopasowanie modelu z trzech punktów

Wyznacz fizycznie 1, 2 i 3 m **od laptopa ustawionego na stole**, a nie z
odczytu breloka. Zachowaj tę samą pozycję noszenia w każdym punkcie. Dwie
sekundy odliczania służą zmianie miejsca; właściwy pomiar trwa 12–35 s na punkt.
Brelok pokazuje cel, etap i odliczanie, sam przechodzi na ekran kalibracji
przy nowym punkcie i go wybudza. Nie może zweryfikować fizycznej odległości.

Model pozostaje `d = 10^((A - RSSI)/(10n))`. Z median dla 1, 2 i 3 m
dopasowujemy prostą `RSSI = A - 10n * log10(d)`, wyznaczając **A oraz n**.
Każdy punkt ma równą wagę, niezależnie od liczby callbacków. Progi jakości:

- RSSI między 1 i 3 m musi spaść o co najmniej 3 dB; wzrost między sąsiednimi
  punktami nie może przekraczać 2 dB.
- Dopasowane `n` musi należeć do 0,5–6; nie przycinamy złego wyniku do granicy.
- Błąd dopasowania RMSE ≤3 dB i R² ≥0,75. To założenia PoC, do sprawdzenia
  w fizycznych seriach z docelową obudową i pozycją noszenia.

Wyniki punktów pozostają w pamięci do końca serii. Dopiero poprawny komplet
zapisuje atomowo A, n, odległość granicy 3 m oraz próg z ostatniego punktu.
GUI pokazuje medianę, wahanie i liczbę próbek dla każdego punktu, A, n i RMSE.
Po zmianie modelu backend odbudowuje filtr z nowych pakietów. Blokada nadal
korzysta z RSSI, czasu, ruchu i histerezy: punkt 3 m nie gwarantuje natychmiastowej
blokady dokładnie przy 3 m. Zasłonięcie, orientacja i odbicia wpływają na metry.

Firmware 0.5.2 poprawia dekoder statusu GATT: przyjmuje również `calibration=4`.
W 0.5.1 stan zbierania był odrzucany przez walidację ograniczoną do 0–3.
Format i długość wiadomości pozostają zgodne.

## Weryfikacja

- python3 tools/run_host_tests.py: protokół, ruch, gesty, anulowanie przytrzymania, pojedyncze wykonanie i utrata hosta.
- python3 tools/render_ui_preview.py: uruchamia prawdziwy renderer firmware na komputerze i zapisuje arkusz podglądu.
- pio run -e waveshare-s3-touch: kompilacja dla płytki.
- Testy Rust sprawdzają format wiadomości, sesje i deduplikację.
- USB s pokazuje gatt_connected, host_fresh, stan ochrony, dystans, kalibrację, wynik akcji i ACK.

Fizyczny gest/przytrzymanie oraz przejście macOS do blokady wymagają
testu palcem i odpowiedniego uprawnienia systemowego.

Sprawdzenie na żywo 3 października 2026: firmware 0.5.1 wgrany, nowa aplikacja
macOS uruchomiona. 43 rekordy USB, po nawiązaniu połączenia 32 rekordy ze
świeżym stanem PC; brak błędów BLE i dotyku. Brelok otrzymał stan kalibracji
WAITING uruchomionej w aplikacji. Kreator pokazał 14 rzeczywistych próbek
z ostatnich 5 s przy wymaganych 12. Próbę anulowano bez zmiany progu.
Log: apps/firmware-esp32/output/control-live.jsonl.
Testy: 35 Rust, 82 sprawdzenia firmware, 4 frontend — PASS; Clippy i rustfmt — PASS.
macOS nadal zgłasza brak uprawnienia Dostępność, więc blokady OS nie wywoływano.

## Poprawka kalibracji — 3 października 2026

Powód: logi GUI pokazały wielokrotne odrzucenie „za mało świeżych próbek”
i „sygnał mocno się waha”. Wymóg 12 odczytów / 5 s zależał od chwilowej
częstotliwości callbacków; okno sprzed dotknięcia obejmowało również podejście
i zmianę pozycji ręki. Nowy pomiar rozpoczyna się po oznaczeniu granicy.

- Firmware `0.5.1-poc` wgrano na `142D6F020F3C`, esptool potwierdził hashe.
- Build: RAM 48 256 B, Flash 996 793 B.
- USB potwierdziło wersję, BLE healthy, brak błędów BLE/IMU/dotyku.
- Odczyt techniczny prawdziwego RSSI: **16 próbek / 12,1 s**, mediana
  −46,5 dBm, MAD 2,5 dB, margines 4,5 dB. Ten odczyt nie zapisywał konfiguracji.
- W GUI potwierdzono przejście WAITING → COLLECTING → COMPLETE i zapis
  mediany −41 dBm, progu −45,5 dBm z marginesem 4,5 dB. To pomiar w aktualnym
  miejscu breloka; docelową granicę użytkownik powinien ustawić kolejnym pomiarem.
- Testy: **42 Rust**, **84 sprawdzenia firmware**, **5 frontend** — PASS.
  Clippy z `-D warnings`, rustfmt i build GUI — PASS.
- Testy obejmują odbiór 0,5–1 Hz, brak próbek, błędne/duplikowane odczyty,
  dryf, stabilizację po dotknięciu, outliery, timeout i ponowne tapy podczas pomiaru.

Surowy zapis techniczny:
`apps/desktop/native/logs/2026-10-03-calibration-probe-live.jsonl`.
USB: `apps/firmware-esp32/output/calibration-live-0.5.1.jsonl`.
Tester używa tego samego transportu GATT i algorytmu co aplikacja.
Wartości progów jakości pozostają założeniami PoC; test w jednej pozycji
nie weryfikuje działania dla wszystkich orientacji, kieszeni i pomieszczeń.

## Weryfikacja skali i animacji 0.5.2 — 3 października 2026

- **45 testów Rust**, **95 sprawdzeń firmware**, **5 testów frontend** — PASS.
- Test regresji: dotychczasowy odczyt 1 m przy RSSI −59 dBm dopasowuje się
  do 4 m po pomiarze ze znaną odległością. Sprawdzono też zakres 0,5–20 m,
  serializację oraz wynik w snapshotach wybranego urządzenia po zmianie modelu.
- Dekoder firmware przyjmuje stan pomiaru 4 i odrzuca nieważny stan 5.
- Testy przytrzymania: 50% po 1,5 s, brak akcji przed 3 s, pojedyncza akcja,
  krótki tap i zwolnienie palca, swipe, zerwanie sesji, brak hosta, blokada
  ponownego pomiaru w toku. Kalibracja działa bez uprawnienia OS do blokady.
- Clippy całego workspace z `-D warnings`, formatowanie i build UI — PASS.
- Backend Windows: `cargo check` dla `x86_64-pc-windows-msvc` — PASS.
- Nowy pakiet macOS zbudowano, zweryfikowano podpis i uruchomiono. W GUI
  potwierdzono nowe pole „Odległość kalibracji”: 4 m. Poprzedni próg i RSSI
  przy 1 m pozostawiono bez zmiany; dopasowanie nastąpi po nowym pomiarze.
- Firmware 0.5.2 skompilowano; podgląd jest renderowany z prawdziwego kodu
  urządzenia w `apps/firmware-esp32/output/device-ui/device-ui.png`.
- **Upload 0.5.2 i fizyczny test przy 4 m pozostają do wykonania**:
  urządzenie nie było dostępne przez USB ani BLE podczas końcowej weryfikacji.
  Ostatnia potwierdzona wersja na płytce to 0.5.1. Nie zapisywano fikcyjnego
  pomiaru 4 m w konfiguracji użytkownika.


## Wgranie i poprawka startu 0.5.3 — 3 października 2026

Wgrywanie 0.5.2 zakończyło się poprawnym zapisem flashu, lecz kontrola startu
ujawniła powtarzany `Stack canary watchpoint triggered (ipc1)` przed zakończeniem
inicjalizacji. W 30-sekundowym zapisie USB wystąpiło 20 awarii i nie otrzymano
statusu aplikacji. Log: `apps/firmware-esp32/output/upload-stability-0.5.2-2026-10-03-boot.log`.

Ślad jest zgodny z opisywaną awarią podczas `attachInterrupt()` na ESP32-S3:
[zgłoszenie w Arduino ESP32](https://github.com/espressif/arduino-esp32/issues/10528).
W tej wersji bibliotek rozmiar stosu IPC wynosi 1024 B. Zamiast instalacji
przerwania GPIO dotyku czytamy stan CST816S co 20 ms w głównej pętli. Zachowano
odczyt kontaktu, obsługę gestów, wybudzanie, anulowanie i przytrzymanie 3 s.
To obejście konkretnej ścieżki inicjalizacji; pobór prądu i gesty wymagają
osobnego testu na docelowym urządzeniu.

- Firmware **0.5.3-poc** skompilowano i wgrano na **142D6F020F3C**; esptool
  potwierdził wszystkie hashe. RAM: 47 664 B; Flash: 994 893 B.
- **95 sprawdzeń firmware** — PASS.
- Po ponownym podłączeniu wykonano **trzy sprzętowe restarty i test ciągłości
  pracy**. Zebrano 34 statusy z czterech uruchomień; w fazie ciągłej boot ID
  pozostał bez zmian. Wszystkie odczyty zgłosiły wersję 0.5.3, IMU około
  56 próbek/s, gotowy dotyk i BLE, bez błędów sensorów i bez panic.
- Tester: `apps/firmware-esp32/output/verify_boot_0.5.3.py`.
  Wyniki: `apps/firmware-esp32/output/startup-verify-0.5.3.jsonl` oraz
  `apps/firmware-esp32/output/startup-verify-0.5.3-boot.log`.
- Podczas testu restartów Bluetooth na Macu był wyłączony (`PoweredOff`),
  więc GATT nie było połączone. Nie jest to test dwukierunkowej komunikacji.
  Kreator na komputerze ma ustawione 4 m; fizyczny pomiar ze znaną odległością
  pozostaje do wykonania przez użytkownika. Nie uruchamiano pomiaru na biurku.

## Kalibracja 1 → 2 → 3 m, wersja 0.6.0 — 3 października 2026

- Wdrożono sesję trzech potwierdzanych punktów, odliczanie 2 s, pomiar
  12–35 s w każdym punkcie oraz wspólne dopasowanie A i n z median.
- **53 testy Rust**, **107 sprawdzeń firmware**, **5 testów frontend** — PASS.
  Clippy całego workspace z `-D warnings`, Svelte bez błędów/ostrzeżeń
  i build pakietu macOS — PASS. Backend Windows: `cargo check` dla
  `x86_64-pc-windows-msvc` — PASS; nie jest to build instalatora Windows.
- Testy obejmują odzyskanie A i n, silny sygnał w punkcie 1 m, brak lub
  wzrost sygnału między punktami, zły model, timeout, ponowienie punktu,
  restart całej serii, próbki z przejścia, powtórzone kliknięcia oraz format
  GATT v2 i anulowanie przytrzymania przy zmianie punktu.
- Firmware **0.6.0-poc** wgrano na **142D6F020F3C** i zweryfikowano hashe.
  RAM: 47 680 B; Flash: 995 517 B.
- Osiem statusów USB z jednego uruchomienia potwierdziło wersję, IMU
  około 52 próbek/s, gotowy dotyk, zero błędów i połączenie GATT z GUI.
  Nowy status v2 dociera do breloka: ochrona OFF, kalibracja 1, krok 1,
  oczekiwanie na potwierdzenie fizycznej pozycji. Ślad:
  `apps/firmware-esp32/output/guided-calibration-0.6.0-live.jsonl`.
- W GUI potwierdzono odliczanie 2 s i przejście do „Jestem na 1 m”.
  **Nie wykonywano fizycznej serii 1/2/3 m ani nie zapisywano pomiaru z biurka.**
  Wskazania metrów i powtarzalność blokady wymagają testu z użytkownikiem.
- Przed aktualizacją stara aplikacja miała aktywną ochronę. Przerwa przy
  uploadzie wyzwoliła L1 i żądanie blokady. Kolejne uploady należy poprzedzać
  ustawieniem OFF. Nową aplikację uruchomiono wyłączoną i przygotowano kreator.
