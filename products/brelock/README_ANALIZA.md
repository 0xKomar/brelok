# breLock — analiza istniejącego kodu pod PoC

**Data audytu:** 2026-10-01.  
**Aktualny zakres:** jedna aplikacja na komputerze i jeden brelok Waveshare.

Ten dokument zachowuje ustalenia wcześniejszego audytu źródeł, buildów i instalatorów. Każdemu problemowi przypisuje jego znaczenie dla nowego PoC. Zastępuje poprzedni plan produkcyjny i firmowy.

**Obowiązującym planem implementacji jest [architektura PoC](ARCHITEKTURA_WAVESHARE_BRELOCK.md).** Nie rozwijamy panelu, backendu, kont, strony ani infrastruktury wdrożeniowej. Historyczny kod tych części pozostaje w repozytorium; nie jest wymagany przez docelowy PoC.

## Co trzeba zrobić dla PoC

Obecny klient i firmware są bazą. Klient nadal korzysta z centralnej konfiguracji; docelowo startuje samodzielnie z lokalnym wyborem ID i progami. Firmware potrzebuje profilu Waveshare S3 oraz odczytu IMU i baterii. Skaner wymaga obsługi błędów i wznowienia, a decyzje — normalizacji czasu, histerezy i lokalnych logów.

1. Odpinamy konfigurację i heartbeat HTTP; używamy jednej lokalnej aplikacji.
2. Dodajemy profil Waveshare i podsumowania ruchu/baterii do BLE.
3. Wyodrębniamy silnik L1–L4, tryb obserwacji oraz świadome uzbrojenie.
4. Dodajemy wykresy i kalibrację w tym samym oknie.
5. Sprawdzamy rzeczywistą blokadę OS i obsługę sleep/wake.
6. Porównujemy RSSI-only oraz RSSI+IMU na pomiarach jednej pary urządzeń.

Dotychczasowe oznaczenia P0/P1/P2 pozostają identyfikatorami ustaleń audytu. Nie oznaczają już wymogu naprawienia wszystkich historycznych części przed demonstracją. Wymagania PoC określają poniższe opisy oraz aktualny plan.

## Baza, którą wykorzystujemy

- Główny klient Python/Bleak/CustomTkinter w `apps/desktop`.
- Firmware Arduino/PlatformIO w `apps/firmware-esp32`.
- Pełny 48-bitowy ID urządzenia, bez polegania na nazwie albo adresie MAC widzianym przez system.
- Detektor trendu oraz dotychczasowe testy stabilnego szumu, spadku i powrotu.
- Istniejące adaptery blokady OS po sprawdzeniu wyniku i uprawnień.

Audyt nie potwierdza działania na fizycznym Waveshare ani na pełnej macierzy komputerów. PoC najpierw sprawdzamy na laptopie demonstracyjnym.

## Zachowane wyniki wcześniejszego audytu

To zapis sprawdzeń wykonanych podczas audytu 1 października 2026, przed przebudową planu. Nie są to wyniki nowych testów PoC. Sprawdzenia serwera i strony opisują historyczny kod i nie są kryteriami odbioru PoC. Kompilacja `esp32dev` nie potwierdza działania na Waveshare S3.

### Kontrole zakończone powodzeniem

- 13/13 testów jednostkowych klienta desktopowego przeszło.
- 7/7 testów API i bazy control-plane przeszło.
- TypeScript strony przechodzi kontrolę tsc --noEmit.
- Produkcyjny build Next.js przechodzi, gdy środowisko ma dostęp do Google
  Fonts.
- Firmware PlatformIO dla esp32dev buduje się poprawnie:
  - RAM: 39 092 B z 327 680 B, około 11,9%;
  - flash: 1 133 193 B z 1 310 720 B, około 86,5%.
- Suma kontrolna publicznego DMG jest poprawna; sam obraz nie jest uszkodzony.

### Kontrole zakończone problemem

- ESLint strony zgłasza 6 błędów.
- Build strony bez dostępu do internetu nie przechodzi, ponieważ next/font
  pobiera Inter i Playfair Display z Google Fonts podczas kompilacji.
- Publiczny DMG:
  - zawiera aplikację tylko arm64;
  - ma wersję pakietu 0.0.0;
  - jest podpisany ad-hoc, bez TeamIdentifier;
  - nie zawiera NSBluetoothAlwaysUsageDescription ani
    NSBluetoothPeripheralUsageDescription;
  - nie zawiera deployment.json ani config.json;
  - nie zawiera aktualnych modułów centralnego klienta.
- Publiczne pliki EXE/DMG są starsze niż aktualny kod i nie są generowane przez
  widoczny w repozytorium automatyczny proces wydawniczy.

### Czego audyt nie potwierdził

- Rzeczywistego rozkładu RSSI na różnych laptopach i adapterach.
- Zachowania po sleep/wake na Windows i macOS.
- Skuteczności natywnej blokady na świeżych instalacjach systemu.
- Zachowania przy wyłączaniu i ponownym włączaniu Bluetooth.
- Odporności na zakłócenia, ciało użytkownika, zatłoczone 2,4 GHz i wiele
  breLocków w jednym biurze.
- Czasu pracy z docelowym zasilaniem bateryjnym.

## Dlaczego breLock nie zawsze działał

Poniższa tabela opisuje wcześniejszą implementację. Nie jest listą nowych wymagań. W PoC świadomy start w obserwacji, lokalne zakończenie aplikacji oraz jedno żądanie blokady na epizod są zamierzonym zachowaniem; nie wdrażamy firmowego wymuszania ochrony. Pomiary sprzętowe nadal wymagają wykonania.

| Objaw | Potwierdzona lub bardzo prawdopodobna przyczyna | Gdzie |
| --- | --- | --- |
| Aplikacja ze strony nie pojawia się w panelu | Publiczny build jest starszy niż control-plane i nie zawiera aktualnego klienta | apps/website/public, metadane PyInstaller |
| Aplikacja nie może się zarejestrować | Brak deployment.json w instalatorze; lokalna konfiguracja wskazuje na 127.0.0.1:8100 | installer.iss, control_plane.py |
| Po restarcie komputera ochrona znika | Autostart Windows jest opcjonalny, na macOS go nie ma | installer.iss, build.sh |
| Bluetooth był wyłączony przy starcie i aplikacja już nie wróciła | Pierwszy start skanera może zakończyć całą coroutine; kolejne próby mogą uznać niedziałający skaner za skonfigurowany | main.py |
| Urządzenie jest widoczne czasami, a czasami nie | Tożsamość znajduje się w scan response, którego odbiór zależy od aktywnego skanowania i zachowania systemu | firmware src/main.cpp, ble_identity.py |
| Komputer nie blokuje się, gdy breLock był nieobecny już przy starcie | Watchdog uzbraja się dopiero po pierwszej obserwacji urządzenia | ble_scanner.py |
| Po pierwszej blokadzie można odblokować komputer bez breLocka | Watchdog ma flagę jednorazowego wyzwolenia | ble_scanner.py |
| GUI mówi, że komputer został zablokowany, ale system pozostał odblokowany | Wynik LockWorkStation lub os.system nie jest sprawdzany; macOS wymaga zgody na sterowanie System Events | system_controller.py, main.py |
| Blokada następuje za wcześnie albo za późno | EMA ma stałą wagę na próbkę, częstotliwość callbacków BLE różni się między platformami | ble_scanner.py |
| Stabilny sygnał blisko granicy nigdy nie spełnia czasu reakcji | Każda próbka powyżej progu zeruje cały czas słabego sygnału; brak histerezy | ble_scanner.py |
| Po sleep/wake występuje natychmiastowa blokada lub brak dalszych zdarzeń | Brak obsługi uśpienia, wznowienia i restartu adaptera; używany jest czas ścienny | ble_scanner.py, main.py |
| Konfiguracja administratora wydaje się nie działać | Plik config.json jest reliktem i nie jest używany przez aktualny klient; polityka pochodzi z API | apps/desktop/config.json |
| Zmiana hasła lub tokenu w .env nie daje efektu | Bootstrap tworzy rekordy tylko, gdy nie istnieją; nie aktualizuje istniejących sekretów | control-plane/db.py |
| Serwer uruchamia „inną” pustą bazę | Ścieżka BRELOCK_DATABASE może być względna wobec bieżącego katalogu procesu | control-plane/db.py |
| Na Macu Intel instalator nie startuje | Strona obiecuje Intel, ale publiczny DMG ma wyłącznie Mach-O arm64 | strona pobierania, publiczny DMG |

## Szczegółowe problemy

### P0-01 — publikowana aplikacja nie odpowiada aktualnemu kodowi

**Dowody**

- Publiczne instalatory mają datę 2026-04-12.
- Aktualne pliki main.py, control_plane.py, ble_identity.py i
  trend_detector.py mają zmiany z 2026-07-16.
- Metadane macOS-owego buildu PyInstaller wymieniają tylko main,
  ble_scanner, gui i system_controller.
- W publicznym buildzie nie ma control_plane, ble_identity ani
  trend_detector.
- Windowsowy plik wykonywalny w głównym kliencie i w starym wariancie ma ten
  sam hash SHA-256, mimo że źródła tych klientów są obecnie różne.

**Skutek**

Osoba pobierająca program ze strony nie testuje produktu opisanego w aktualnym
README. Wyniki testów źródła nie mówią nic o zachowaniu wydanego instalatora.

**Znaczenie dla PoC**

PoC uruchamiamy z bieżących źródeł `apps/desktop`. Starych publicznych instalatorów nie używamy do oceny nowego PoC. Ewentualny lokalny build ma służyć demonstracji; pipeline wydawniczy i publikacja strony nie są zadaniami PoC.

### P0-02 — brak kompletnego procesu wdrożenia klienta

Aktualny klient oczekuje control_url, company_slug i enrollment_token w
deployment.json lub zmiennych środowiskowych. Instalator Windows nie kopiuje
tego pliku. Publiczny DMG także go nie zawiera. GUI nie ma ekranu wpisania kodu
firmy.

Lokalny, niecommitowany deployment.json był zgodny z lokalnym serwerem, ale
wskazywał 127.0.0.1:8100. Taki adres działa tylko wtedy, gdy control-plane
działa na tym samym laptopie. W czasie audytu nic nie nasłuchiwało na porcie
8100.

**Znaczenie dla PoC**

Pierwszy krok to usunięcie ze ścieżki uruchamiania rejestracji, konfiguracji i heartbeat HTTP. ID oraz progi zapisujemy w lokalnym `poc_config.json`. PoC nie potrzebuje `deployment.json`, adresu serwera, tokenu firmy ani enrollmentu.

### P0-03 — błąd startu BLE może trwale zatrzymać ochronę

W main.py pierwsze configure_scanner jest wykonywane przed wejściem do pętli
try/except. Jeżeli Bluetooth jest wyłączony, brakuje uprawnień albo backend
Bleak zgłosi błąd, coroutine control_loop kończy się.

Dodatkowo configure_scanner zapisuje current_scanner_key i globalny obiekt
scanner przed udanym await scanner.start. Przy kolejnym wywołaniu identyczny
klucz może spowodować przedwczesny return, mimo że skaner nigdy nie wystartował.
Future zwrócony przez run_coroutine nie jest przechowywany ani obserwowany.

**Znaczenie dla PoC**

Obsłużyć błąd także przy pierwszym starcie; ustawiać aktywny skaner dopiero po sukcesie i czyścić nieudany stan. Retry START 0,5 / 1 / 2 / 5 s działa niezależnie od timera utraty pakietów. GUI pokazuje stan adaptera i przyczynę błędu.

### P0-04 — niepełna maszyna stanów ochrony

Obecna logika jest zbiorem timerów, a nie pełną maszyną stanów.

Problemy:

- brak urządzenia od chwili startu nie wywoła blokady;
- watchdog blokuje tylko raz;
- po blokadzie kolejna próbka RSSI natychmiast może zmienić GUI z locked na
  protected;
- nie ma stanu powrotu i stabilnego ponownego uzbrojenia;
- nie ma jednoznacznej polityki dla awarii skanera;
- nie ma osobnej obsługi uśpienia i wznowienia.

**Znaczenie dla PoC**

Przyjąć tryby UNCONFIGURED, OBSERVE, ARMED i PAUSED opisane w planie PoC. Start bez breloka pozostaje w obserwacji. Uzbrojenie wymaga aktualnych danych i sprawdzonego adaptera OS. Jedna blokada na epizod zapobiega pętli; świeży powrót albo jawne ponowne uzbrojenie przygotowuje kolejny epizod. Błąd BLE ma jawny komunikat; podczas ARMED utrata kontaktu nadal prowadzi do L1.

### P0-05 — brak gwarantowanego uruchomienia agenta

- Windows: zadanie autostartu w Inno Setup jest domyślnie odznaczone.
- macOS: brak LaunchAgenta lub Login Item.
- Menu zasobnika zawiera zwykłe „Wyjdź”.
- Brak watchdoga procesu i blokady wielu instancji.
- Ochrona jest połączona z GUI, zamiast działać jako niezależny agent.

**Znaczenie dla PoC**

Jedna aplikacja z GUI jest całym programem PoC. Użytkownik uruchamia ją i może zakończyć albo zapauzować ochronę lokalnie. Nie dodajemy osobnego agenta, usługi ani wymogu zgody administratora. Tray i autostart są opcjonalne po działającej demonstracji.

### P0-06 — publiczny pakiet macOS jest niezgodny z deklaracją

W publicznym DMG potwierdzono:

- architekturę arm64 zamiast Universal 2;
- brak opisów użycia Bluetooth w Info.plist;
- podpis ad-hoc bez Developer ID;
- brak notaryzacji;
- wersję 0.0.0;
- brak konfiguracji firmy.

Strona równocześnie deklaruje obsługę Apple Silicon i Intel.

Wariant desktop-sm1go ma późniejszy skrypt dopisujący opisy Bluetooth i
entitlements, ale te poprawki nie znajdują się w głównym kliencie ani w
publicznym DMG.

**Znaczenie dla PoC**

Pierwszym celem jest laptop demonstracyjny i jego architektura. Potrzebujemy działającego BLE i rzeczywistych uprawnień blokady na tym komputerze. Universal 2, podpisy, notaryzacja i publiczne instalatory nie blokują PoC uruchamianego ze źródeł.

### P0-07 — aplikacja nie wie, czy system faktycznie został zablokowany

system_controller.py ignoruje wartości zwrotne:

- Windows nie sprawdza wyniku LockWorkStation;
- macOS wysyła skrót klawiszowy przez System Events i ignoruje kod os.system;
- Linux zakłada obecność xdg-screensaver.

main.py zawsze pokazuje stan „Laptop został zablokowany”, nawet gdy polecenie
się nie udało.

Na macOS symulowanie skrótu może wymagać uprawnienia Accessibility. Brak zgody
użytkownika daje dokładnie objaw „aplikacja działa, ale nie blokuje”.

**Znaczenie dla PoC**

Adapter OS zwraca wynik oraz błąd. GUI odróżnia zlecenie blokady od potwierdzenia i wykonuje ręczny test na komputerze demonstracyjnym. Log zapisujemy lokalnie. Maksymalnie jedno ograniczone ponowienie; bez wyłączania komputera i bez nieskończonej pętli.

### P0-08 — tożsamość BLE nie jest uwierzytelniona

Firmware wysyła stały identyfikator oparty na eFuse MAC. Klient uznaje za
breLock dowolną reklamę z company ID 0xFFFF, wersją 1, typem 1 i właściwymi
6 bajtami ID. Nie sprawdza nawet obecności service UUID.

0xFFFF jest identyfikatorem testowym, nie identyfikatorem firmy przydzielonym
przez Bluetooth SIG.

**Skutek**

Atakujący może nagrać lub odczytać pakiet i emitować jego kopię. Laptop będzie
widział pozornie obecny breLock, chociaż prawdziwy użytkownik odszedł.

**Znaczenie dla PoC**

ID służy wyborowi urządzenia. Nowy licznik i boot ID służą diagnostyce oraz odrzucaniu duplikatów, nie uwierzytelnieniu. PoC świadomie nie ma odporności kryptograficznej na podszycie/replay; demonstruje wykrywanie przypadkowego odejścia. Provisionowanie sekretów, rotujące tożsamości i rozbudowany protokół bezpieczeństwa nie są warunkiem tego eksperymentu.

### P1-09 — detektor RSSI zależy od częstotliwości pakietów

EMA używa stałego alpha 0,3 na każdą próbkę. ESP32 nadaje co 40–60 ms, ale
Windows i macOS mogą agregować lub odfiltrowywać powtórzenia. Ten sam ruch może
więc dać kilkadziesiąt callbacków na sekundę na jednym laptopie i kilka na
innym.

Detektor trendu wymaga co najmniej 6 próbek, a jego okno jest automatycznie
równe reaction_seconds. Dla krótkiego okna i wolnych callbacków trend nigdy nie
osiągnie minimalnej liczby próbek.

Próg statyczny nie ma histerezy: pojedyncza próbka nad progiem zeruje licznik
słabego sygnału.

**Znaczenie dla PoC**

Grupować RSSI w przedziały czasu START 250 ms, używać mediany i EMA zależnej od czasu. Oddzielić trend, potwierdzenie słabego sygnału i timer utraty. Dodać histerezę oraz monotoniczny zegar zgodnie z L1–L4; zachowanie sprawdzić na replay tych samych danych.

### P1-10 — kluczowa tożsamość jest tylko w scan response

Pierwotna reklama zawiera 128-bitowy service UUID, natomiast manufacturer data
z pełnym ID trafia do scan response. Logika klienta nie rozpozna urządzenia bez
manufacturer data.

**Skutek**

Gdy system nie wykona aktywnego skanu, ograniczy go w tle albo nie scali scan
response z reklamą, breLock może być radiowo widoczny, ale logicznie niewidoczny.

**Znaczenie dla PoC**

Pełne ID oraz istotne podsumowanie IMU i baterii trafiają do reklamy podstawowej. UUID i nazwa mogą być w scan response. Nowy format 24 B wraz ze strukturami reklamy mieści się w 31 B; parser nie uzależnia obecności od nazwy.

### P1-11 — brak obsługi cyklu życia systemu i adaptera

Kod nie reaguje na:

- sleep i wake;
- wyłączenie lub restart Bluetooth;
- zmianę użytkownika/sesji;
- utratę uprawnień;
- nieoczekiwane zakończenie backendu Bleak.

Watchdog używa time.time, więc korekta zegara może zmienić wynik timera.
Przerwa podczas uśpienia może zostać błędnie potraktowana jako odejście.

**Znaczenie dla PoC**

Obsłużyć sleep/wake oraz restart adaptera w tej samej aplikacji. Timery są monotoniczne. Po resume odrzucić stare dane i dać jedno ograniczone okno 5 s; retry nie może go odnawiać. W obserwacji/pauzie awaria nie uruchamia automatycznej blokady.

### P1-12 — control-plane ma kruchą konfigurację i brak migracji

Problemy:

- aplikacja sama nie ładuje .env; operator musi ręcznie wyeksportować zmienne;
- bez zmiennych serwer tworzy konto admin@example.com z hasłem change-me-now i
  tokenem dev-enrollment-token;
- przykładowo secure cookie jest wyłączone;
- względna ścieżka bazy zależy od katalogu uruchomienia;
- zmiana hasła, nazwy firmy lub enrollment tokenu w środowisku nie aktualizuje
  istniejących rekordów;
- CREATE TABLE IF NOT EXISTS nie jest systemem migracji.

**Znaczenie dla PoC**

PoC nie uruchamia tego serwera. Nie naprawiamy jego bootstrapu, migracji ani kont w ramach PoC; odpinamy aplikację od niego w kroku 0.

### P1-13 — lokalny cache jest jednocześnie sekretem i polityką

client-state.json zawiera device_token i cached_config. Na Unixie dostaje tryb
0600, ale na Windows nie ma analogicznej ochrony. Plik pozostaje zapisywalny dla
użytkownika, więc można zmienić enabled, próg lub przypisanie, a następnie
odciąć serwer.

Nie ma czasu ważności cache ani podpisu polityki.

**Znaczenie dla PoC**

Lokalny `poc_config.json` zawiera ID, progi i kalibrację, bez tokenów. Użytkownik może go zmieniać z GUI. Nie wczytujemy starego cache jako źródła ustawień PoC. Zapis jest atomowy, walidowany i wersjonowany na potrzeby odtwarzania pomiarów.

### P1-14 — brak trwałych logów i diagnostyki zdarzeń

Build PyInstaller działa z console=False. Komunikaty print o błędach skanera,
panelu i blokady nie tworzą użytecznego śladu dla użytkownika ani administratora.

Brakuje informacji:

- czy skaner wystartował;
- kiedy widziano ostatni pakiet;
- dlaczego podjęto decyzję o blokadzie;
- czy blokada się udała;
- czy aplikacja wznowiła się po sleep;
- jaka wersja i commit są uruchomione.

**Znaczenie dla PoC**

Pokazywać stan BLE/IMU, wiek danych, powody L1–L4 i wynik adaptera OS. Zapisywać lokalny JSONL/CSV wraz z ustawieniami i oznaczeniami operatora. START limit nagrania 50 MB; błąd zapisu nie zatrzymuje decyzji. Nie budujemy centralnej telemetrii.

### P1-15 — trzy źródła prawdy i duży bałagan w repozytorium

Repo zawiera:

- apps/desktop — obecny klient centralny;
- variants/desktop-sm1go — starszy klient lokalny;
- stare buildy skopiowane do apps/website;
- zagnieżdżone repozytoria Git dla desktop, website i wariantu;
- brak .gitmodules;
- tysiące śledzonych plików buildów, venv, pyc i bibliotek;
- niespójne .gitignore.

Główny klient w swoim zagnieżdżonym repo jest trzy commity przed origin i ma
dużo niecommitowanych plików. Wariant śledzi środowisko wirtualne i artefakty.

**Skutek**

Nie wiadomo, z którego repo, brancha i katalogu powstał release. Można łatwo
zbudować starą wersję albo zgubić poprawki.

**Znaczenie dla PoC**

Bazą implementacji są `apps/desktop` i `apps/firmware-esp32`. Pozostałe części są historyczne, poza PoC. Uporządkowanie historii Git i przebudowa całego repozytorium nie są warunkami demonstracji; nie usuwamy istniejących historii ani lokalnych zmian.

### P2-16 — strona i pipeline webowy są zależne od sieci

- next/font pobiera dwa fonty podczas builda.
- Skrypty p5 i Vanta są ładowane z CDN w runtime.
- Vanta używa ścieżki latest.
- Brakuje Subresource Integrity i polityki CSP.
- ESLint obecnie nie przechodzi.

**Znaczenie dla PoC**

Strona nie jest częścią PoC. Jej build, fonty, skrypty i pipeline nie są zadaniami ani zależnościami jednej aplikacji desktopowej.

### P2-17 — control-plane nie jest przygotowany operacyjnie

- Brak Dockerfile, usługi systemowej lub manifestu wdrożenia.
- Brak reverse proxy w repo, automatyzacji TLS i backupu.
- Brak rate limitu logowania i rejestracji.
- Brak audytu zmian przypisań i polityki.
- Brak zarządzania administratorami oraz unieważniania laptopów.
- Klient pobiera politykę i zapisuje heartbeat co 2 sekundy.
- Każdy heartbeat otwiera SQLite, wykonuje zapis i sprzątanie telemetrii.

Dla małego demo SQLite wystarczy. Przy wielu laptopach taki wzorzec będzie
powodował zbędne I/O i ryzyko blokad.

**Znaczenie dla PoC**

Operacje serwera nie należą do PoC. Nie projektujemy infrastruktury, backupów serwera, baz produkcyjnych, zarządzania laptopami ani administracyjnego API. Wszystkie ustawienia i pomiary pozostają lokalne.

### P2-18 — dokumentacja i marketing opisują inny produkt

Niespójności:

- README strony mówi o blokadzie „w ułamku sekundy”, a domyślne czasy to 3 i
  6 sekund.
- Strona mówi o smartfonie jako uniwersalnym tokenie, ale aktualny klient
  akceptuje tylko własny format manufacturer data.
- Strona obiecuje precyzyjną kalibrację dystansu, ale aktualny klient nie ma
  kreatora kalibracji.
- reference_rssi wpływa wyłącznie na estymację w panelu, nie na decyzję o
  blokadzie.
- diagnostics.py jest martwym kodem używanym tylko w testach.
- README firmware opisuje ciągłe światło po połączeniu, ale klient tylko skanuje
  i nigdy nie łączy się GATT.
- Strona mówi „paruje się automatycznie”, chociaż nie ma procesu parowania.
- Strona deklaruje Intel, a DMG jest arm64.

**Znaczenie dla PoC**

Aktualny zakres opisują README produktu i plan jednej aplikacji z brelokiem Waveshare. Czasy oraz progi są hipotezami START; RSSI nie jest pewną odległością. LCD początkowo pokazuje stan nadajnika i sensorów, a nie niepotwierdzoną blokadę laptopa. Nie rozwijamy marketingu strony.

### P2-19 — niespójne wersjonowanie

- API i aktualny klient: 0.2.0.
- Instalator Windows: 1.0.0.
- Publiczna aplikacja macOS: 0.0.0.
- Brak protokołu kompatybilności client/server/firmware poza jednym bajtem
  wersji reklamy.

**Znaczenie dla PoC**

W nagraniach zapisywać wersję aplikacji, firmware, protokołu i config_revision. Nowy parser jawnie obsługuje wersję 2 formatu PoC. Nie tworzymy systemu aktualizacji, zgodności z centralnym serwerem ani kanałów wydawniczych.

### P2-20 — testy nie obejmują ryzyk produktu

Obecne testy sprawdzają czyste funkcje i podstawowy happy path API. Brakuje
testów:

- startu i restartu skanera;
- Bluetooth off/on;
- watchdog i ponowne uzbrojenie;
- skan rate 1 Hz kontra 20 Hz;
- jitter wokół progu;
- sleep/wake;
- błędu polecenia blokady;
- konfiguracji i migracji;
- instalatora na czystym systemie;
- zgodności surowego pakietu firmware z dekoderem;
- replay i spoofingu;
- zgodności artefaktu z commitem.

**Znaczenie dla PoC**

Testować rdzeń L1–L4, czas, duplikaty, histerezę, parser i replay. Na docelowym sprzęcie sprawdzić IMU, ADC, realne callbacky, uprawnienia blokady, sleep/wake, Bluetooth off/on i baterię. Testy API, instalatorów firmowych i flot nie należą do tej walidacji.

## Kolejność implementacji PoC

| Krok | Rezultat | Ustalenia audytu, które wykorzystuje |
| --- | --- | --- |
| 0. Samodzielna apka | Start i lokalne ustawienia bez serwera | P0-02, P1-13, P2-18 |
| 1. Waveshare | IMU, bateria, ekran, profil S3 | Dobór sprzętu opisany w architekturze PoC |
| 2. BLE i ślad pomiarów | ID/ruch/bateria i poprawny parser | P0-08, P1-10, P1-14 |
| 3. Decyzje | Obserwacja, timery, trend, L1–L4 | P0-03, P0-04, P1-09 |
| 4. Frontend i kalibracja | Jeden interfejs do całego eksperymentu | P1-14, P2-18 |
| 5. Blokada i cykl życia | Rzeczywisty lock, błędy, sleep/wake | P0-07, P1-11 |
| 6. Demonstracja | Porównanie algorytmów i pomiar baterii | P2-20 oraz pomiary sprzętowe |

Szczegółowe zadania i odbiór: [kroki implementacji](ARCHITEKTURA_WAVESHARE_BRELOCK.md#8-kroki-implementacji). Scenariusze oraz warunki gotowości: [testy PoC](ARCHITEKTURA_WAVESHARE_BRELOCK.md#9-testy-i-gotowość-demonstracji).

Celem jest sprawdzenie wykrywania odejścia na tej parze komputer–brelok. Kryterium odbioru nie obejmuje zarządzania firmą, publikacji instalatorów ani utwardzania historycznego serwera.
