# breLock — plan małej aplikacji desktopowej

**Data:** 3 października 2026. **Status:** host Tauri, tray, ochrona L1–L4, blokada systemu i kreator kalibracji są zaimplementowane; autostart, pauza i nagrywanie z GUI pozostają planem.  
**Zakres:** jedna aplikacja na macOS/Windows, jeden wybrany brelok Waveshare.  
**Stack:** Tauri 2, Svelte 5, TypeScript, Vite, zwykły CSS; istniejący backend Rust.

Najważniejsze wymaganie: **zamknięcie okna ukrywa je, a odbiór BLE, analiza i włączona ochrona nadal działają w tle**. Dostęp do aplikacji pozostaje przez ikonę w pasku menu macOS albo zasobniku systemowym Windows. Tray jest obowiązkową częścią PoC.

To uszczegółowienie [architektury i reguł blokowania](ARCHITEKTURA_WAVESHARE_BRELOCK.md). [Backend Rust](apps/desktop/native/README.md) odbiera BLE i udostępnia jawne uzbrojenie ochrony; frontend ma trzy widoki, tray, ukrywanie okna, zapis ustawień i kreator kalibracji przez ekran dotykowy breloka. PoC pozostaje lokalny.

## 1. Zamknięcie okna i praca w tle

| Działanie użytkownika / systemu | Zaplanowany rezultat |
| --- | --- |
| X, czerwony przycisk macOS, Alt+F4 lub Cmd+W | Ukrycie okna. Proces, skaner, timery, pauza i nagrywanie kontynuują działanie |
| „Ukryj okno” | Ten sam efekt co zamknięcie okna |
| Minimizacja systemowa | Nie zmienia trybu ani nie zatrzymuje backendu; wejściem do ukrycia do traya pozostaje X / „Ukryj okno” |
| Ponowne otwarcie z ikony | To samo okno i aktualny stan; bez restartu skanowania, filtrów i ochrony |
| Ponowne uruchomienie programu | Pokazanie istniejącej instancji, bez drugiego skanera i drugiego silnika decyzji |
| „Zakończ breLock — wyłącz ochronę” / Cmd+Q | Faktyczne zakończenie programu: zatrzymanie skanera, domknięcie logu, usunięcie ikony |
| Wylogowanie lub zamknięcie systemu | Program pozwala systemowi zakończyć sesję i domyka pracę w dostępnym czasie |
| Wymuszone zakończenie procesu / awaria | Program i ochrona przestają działać; nie obiecujemy pracy po zabiciu procesu |

„Działa po wyłączeniu aplikacji” rozumiemy jako działanie **po zamknięciu jej okna**. Pełne zakończenie programu jest osobną, jasno nazwaną akcją. Nie dokładamy niezależnej usługi systemowej ani drugiego programu utrzymującego ochronę.

Ukrycie jest możliwe dopiero po poprawnym utworzeniu ikony i jej menu. Jeśli tray nie działa, pozostawiamy dostępne okno oraz komunikat błędu. Ponowne kliknięcie ikony nie otwiera kolejnych okien. Utrata fokusu nie ukrywa okna automatycznie.

Pierwsze ukrycie pokazuje krótką informację: „breLock działa w tle. Otworzysz go z ikony na pasku”. Jest jednorazowa, bez blokującego dialogu. Zamknięcie okna nie uruchamia pytania o zgodę i nie przerywa nagrania.

## 2. Małe okno i nawigacja

Domyślny **obszar treści 380 × 520 pikseli logicznych**; minimum 340 × 440. To wartości START do sprawdzenia na obu systemach. Jedno okno z natywnym paskiem tytułu. Wysokość może się zwiększyć przy skalowaniu tekstu; dłuższe widoki przewijają treść pionowo, bez przewijania poziomego.

U góry trzy krótkie pozycje: **Status · Diagnostyka · Ustawienia**. Nagłówek i nawigacja pozostają widoczne przy przewijaniu. Kalibracja zastępuje treść Ustawień na czas kreatora, bez kolejnego okna. Dialogi systemowe wyboru pliku mogą otwierać się osobno.

Wygląd zgodnie z aktualną decyzją użytkownika: spokojny **granatowy motyw bez gradientów**, proste karty i duży okrągły ON/OFF w centrum. Zielony oznacza ON, czerwony OFF; oba stany mają ikonę i tekst oraz delikatne oddychające pierścienie (cykl 4,2 s). `prefers-reduced-motion` wyłącza animację. W natywnym OBSERVE przycisk pozostaje OFF i jest nieaktywny; oba warianty można sprawdzić w jawnie oznaczonym DEMO przeglądarki. Motyw jasny/systemowy odkładamy.

### 2.1. Status — główny widok

Szkic docelowy pokazuje położenie treści, a wartości są wyłącznie przykładem. Pauza i ręczna blokada pojawią się dopiero z adapterem OS:

```text
┌────────────────────────────────────┐
│ breLock              [Ukryj okno]   │
│ Status · Diagnostyka · Ustawienia   │
├────────────────────────────────────┤
│             TWÓJ KOMPUTER          │
│           ((   ON / OFF   ))       │
│         Ochrona włączona/wyłączona  │
│       Tryb i ograniczenia backendu │
│                                    │
│ Mój brelok                 Blisko  │
│ ID …E5F6 · telemetria aktualna     │
│                                    │
│ RSSI −58 dBm       Ruch: spoczynek │
│ Bateria 3,98 V     Pakiet: 0,2 s   │
│                                    │
│ [ Pauza ▾ ]      [Zablokuj teraz]  │
│                                    │
│ Ostatnie: brelok ponownie wykryty  │
│ Praca w tle · nagrywanie wyłączone │
└────────────────────────────────────┘
```

| Miejsce | Co pokazujemy i po co |
| --- | --- |
| Centralny przycisk i opis | Oddychający ON/OFF, nazwa stanu i osobna linia trybu/ograniczenia. Nie deklarujemy ochrony na podstawie samego koloru |
| Karta breloka | Lokalna nazwa, skrót ID, stan obecności i telemetrii; pełne ID oraz kopiowanie w Ustawieniach |
| Siatka 2 × 2 | Filtrowane RSSI w dBm, ruch: porusza się / spoczynek / nieznany, napięcie baterii w V, wiek ostatniego nowego pakietu |
| Pod siatką, opcjonalnie | „Dystans szacowany: ~X m” po kalibracji modelu. Przed nią metry są wyłącznie w diagnostyce |
| Główna akcja | OBSERVE → „Włącz ochronę”; ARMED → „Przejdź do obserwacji”; PAUSED → „Wznów ochronę” |
| Akcje pomocnicze | „Pauza”: 5 / 15 / 60 min / do ręcznego wznowienia. „Zablokuj teraz”: osobna, jawna blokada OS |
| Dolna część | Ostatnie istotne zdarzenie z czasem, badge nagrywania i informacja o pracy w tle |

„Blisko / oddalony / brak aktualnych danych” pochodzi z lokalnych progów i stanu backendu. UI nie wylicza odrębnych progów ani własnego algorytmu blokowania. Jeśli nie ma jeszcze klasyfikacji strefy, pokazuje sam stan świeżości. Mocny sygnał nie oznacza automatycznie włączonej ochrony.

Przycisk ochrony jest nieaktywny z krótkim powodem, gdy brakuje ID, aktualnych danych, poprawnej konfiguracji albo sprawdzonego adaptera blokady OS. W obecnym OBSERVE blokada jest niedostępna. Ręczna blokada wymaga działającego adaptera OS, ale nie wymaga obecności breloka.

Napięcie baterii nie staje się procentem naładowania. Nieaktualne wartości zastępujemy „—”; pokazujemy powód i wiek danych. Brak odczytu IMU nie jest interpretowany jako spoczynek.

### 2.2. Diagnostyka — pomiary i debugowanie

Widok przewijany w tym samym małym oknie. Na górze krótki wykres ostatnich **60 s**: surowe i filtrowane RSSI, lokalne progi po ich wdrożeniu, przerwy w danych oraz pas aktywności IMU. Przerw nie łączymy linią sugerującą ciągły pomiar.

Poniżej sekcje rozwijane:

| Sekcja | Pola |
| --- | --- |
| Radio i model | RSSI raw/filtered, jakość i nachylenie trendu w dB/s, R², modelowy dystans, estymacja prędkości radialnej z RSSI, parametry A/n |
| Ruch i bateria | RMS przyspieszenia w mg, RMS gyro w °/s, wiek ruchu, nasycenie wieku, ważność IMU/gyro, clipping, bateria w mV |
| Odbiór | Pełne ID, adres identyfikowany przez OS, boot ID, sequence, wiek pakietu/callbacku, nowe pakiety/s, duplikaty, konflikty, pominięte podsumowania i restarty |
| Decyzja | Aktywny tryb, powód ostatniej decyzji, `would_lock`, timery L1–L4 i wynik blokady OS; dopiero po wdrożeniu silnika |
| Szczegóły pakietu | Payload HEX i flagi ostatniego odebranego pakietu, wyraźnie oznaczone jako dane historyczne, jeśli nie są świeże |
| Zdarzenia | Ostatnie 100 zmian: start, wybór ID, utrata/powrót BLE, pauza, błąd, decyzja, próba i wynik blokady |

Prędkość podpisujemy „**zmiana dystansu z RSSI — estymacja**”, z jednostką m/s. Rzeczywista prędkość nie jest mierzona. Niedostateczny trend oznacza „—”, nie 0 m/s. Nie wyznaczamy przebytej drogi z IMU.

Na dole akcje: **Rozpocznij/zatrzymaj nagranie**, **Otwórz folder logów**, **Kopiuj diagnostykę**. Nagranie zapisuje lokalny JSONL wraz z aktywną konfiguracją i źródłem BLE/demo. Plik ma unikalną nazwę; błąd zapisu kończy nagrywanie z jawnym komunikatem i nie zatrzymuje analizy.

Zwykłe nagranie pomiarów nie zmienia trybu ochrony. Kreator kalibracji osobno przełącza do obserwacji. Ukrycie okna nie zatrzymuje żadnego z nich. Pełne logi zapisujemy na dysk tylko podczas nagrywania; pamięć wykresu i listy zdarzeń ma limit.

### 2.3. Ustawienia — cztery zwijane sekcje

| Sekcja | Funkcje |
| --- | --- |
| Brelok | „Szukaj breloka”, lista wykrytych ID z RSSI i świeżością, wybór jednego ID, lokalna nazwa i kopiowanie pełnego ID |
| Ochrona | Progi i czasy START, odnośnik do kalibracji, test ręcznej blokady, przywrócenie START; zaawansowane parametry schowane |
| Działanie aplikacji | „Uruchamiaj po zalogowaniu”, start w tle, motyw System/Jasny/Ciemny; informacja „Zamknięcie okna pozostawia aplikację w tle” |
| Pliki i informacje | Folder konfiguracji/logów, wersja programu/protokołu, status uprawnień Bluetooth, ostatni błąd i instrukcja naprawy |

Wybór ID nie bazuje na nazwie ani samym adresie BLE. To lokalny wybór konkretnego payloadu, bez obietnicy uwierzytelnienia urządzenia.

Zmiany progów mają **Zapisz / Anuluj**. Walidacja jest po stronie Rust, a UI pokazuje błąd przy polu. Zmiana ID lub parametrów decyzji przełącza do obserwacji i resetuje związane z nimi dowody; informacja o tym znajduje się przy przycisku zapisu. Motyw i autostart nie zmieniają ochrony. Ukrycie okna zachowuje niezapisany formularz w bieżącej sesji, ale go nie zatwierdza.

Stan „Autostart włączony” pokazujemy po sukcesie rejestracji w OS, nie po samym przestawieniu przełącznika. Autostart domyślnie jest wyłączony i użytkownik włącza go lokalnie. Po włączeniu uruchamia program przy logowaniu z flagą startu w tle. Program startuje w obserwacji; autostart nie oznacza automatycznego uzbrojenia.

### 2.4. Kalibracja — prosty kreator w Ustawieniach

1. **Przygotowanie:** wybrany ID, świeże dane, przejście do obserwacji, opis noszenia breloka jak podczas normalnej pracy.
2. **Przy biurku:** nagranie START 60 s spoczynku i zwykłych ruchów przy komputerze.
3. **Odejście i powrót:** nagranie START 30–60 s z kilkoma próbami; oznaczenie momentów w kreatorze. Osobny pomiar w znanej odległości jest potrzebny do kalibracji metrów.
4. **Wynik:** jakość danych, proponowane progi i porównanie RSSI z RSSI+IMU. Profile z małą liczbą próbek lub dużymi przerwami nie są zatwierdzane jako dobra kalibracja.
5. **Zastosuj / odrzuć:** lokalny zapis dopiero po decyzji użytkownika. Koniec lub anulowanie pozostawia obserwację; ochronę włącza się osobno.

Zamknięcie okna jedynie ukrywa trwający krok; ponowne otwarcie pokazuje postęp. Anulowanie kreatora zatrzymuje jego sesję. Zebrane próby nie są gwarancją dokładności poza tym stanowiskiem i sposobem noszenia breloka.

## 3. Ikona i menu na pasku

**macOS:** ikona w górnym pasku menu, kliknięcie otwiera menu; „Otwórz breLock” pokazuje i aktywuje małe okno. Po ukryciu okna brak stałej ikony w Docku.  
**Windows:** ikona obok zegara; lewy klik pokazuje okno, prawy otwiera menu. Przy ukrytym oknie zostaje ikona zasobnika, bez pozycji otwartego okna na pasku zadań. System może umieścić ją w grupie ukrytych ikon.

Menu traya:

```text
breLock · Obserwacja                 [status, bez akcji]
Brelok: telemetria aktualna          [status, bez akcji]
────────────────────────────────────
Otwórz breLock
Włącz ochronę / Przejdź do obserwacji / Wznów
Pauza ochrony › 5 min / 15 min / 60 min / do wznowienia
Zablokuj komputer teraz
────────────────────────────────────
Diagnostyka
Ustawienia
────────────────────────────────────
Zakończ breLock — wyłącz ochronę
```

Menu jest dynamiczne. Pauza jest dostępna przy aktywnej ochronie, a wznowienie przy pauzie. Zablokowane akcje mają ten sam powód co w oknie. Sterowanie działa w Rust także przy ukrytym lub niedziałającym frontendzie.

| Stan ikony | Komunikat w menu i oknie |
| --- | --- |
| Tarcza z oznaczeniem aktywności | Ochrona włączona i bieżący stan jest poprawny |
| Symbol obserwacji | Analiza działa, automatyczna blokada wyłączona |
| Symbol pauzy | Pauza do określonego czasu albo do ręcznego wznowienia |
| Wykrzyknik | Brak konfiguracji, niedostępny BLE, nieaktualne dane lub błąd blokady; tekst podaje konkretny powód |

Priorytet ikony: błąd wymagający uwagi → pauza → ochrona → obserwacja. Awaria IMU przy poprawnym BLE pokazuje ograniczenie analizy, zgodnie z regułami L1–L4; nie udaje utraty całego breloka. Na macOS symbole muszą być czytelne również jako monochromatyczne ikony. Nie polegamy na tooltipie dostępnym na każdej platformie; stan jest zawsze w menu.

Pauza nie wyłącza odbioru. Jej termin obsługuje Rust; ukryte okno ani uśpiony WebView nie mogą go opóźniać. Wznowienie podlega regułom backendu i jest widoczne jako zdarzenie.

## 4. Tryb, błędy i powiadomienia

Trzy niezależne informacje: **tryb ochrony**, **jakość danych** i **widoczność okna**. Ukryte okno z poprawnym odbiorem nadal ma wybrany tryb. Nieaktualne dane w ARMED nie wyłączają po cichu reguły utraty sygnału.

| Sytuacja | Co widzi użytkownik |
| --- | --- |
| Brak wybranego ID | „Wybierz brelok” oraz wejście do Ustawień; ochrona niedostępna |
| Wersja OBSERVE, bez silnika blokady | „Analiza działa, blokada niedostępna w tej wersji”; akcje OS nieaktywne |
| Oczekiwanie na pierwszy pakiet | „Czekam na wybrany brelok”; wartości „—” |
| Aktualny pakiet | Bieżące wartości i wiek nowych danych; duplikaty nie odświeżają heartbeat |
| STALE / LOST | „Dane nieaktualne” / „Brelok niewykryty”, wiek ostatniego pakietu, brak bieżących metrów i ruchu |
| Permission denied / Bluetooth wyłączony | Konkretna instrukcja nadania uprawnienia lub włączenia Bluetooth; Rust ponawia odbiór |
| IMU nieważne / bateria nieważna | Odpowiednie pole „—” i informacja o ograniczeniu; dostępne dane radiowe nadal są prezentowane |
| Decyzja w OBSERVE | „W tym momencie nastąpiłaby blokada: powód”; wpis w historii |
| Żądanie blokady przyjęte przez OS | „Wysłano żądanie blokady”, z czasem i powodem. „Komputer zablokowany” tylko z potwierdzonym stanem OS |
| Blokada OS zwróciła błąd | Jawny błąd, wpis w historii i ikona uwagi; brak komunikatu sukcesu |
| Epizod blokady został już wykonany | „Ochrona aktywna · czekam na powrót breloka”; po 1 s w pobliżu następny epizod uzbraja się automatycznie, bez pętli blokad po ręcznym odblokowaniu |
| Nagrywanie nie działa | „Nagrywanie zatrzymane: powód”; pomiary i ochrona pracują nadal |

Powiadomienia systemowe są oszczędne: jednorazowa informacja o pracy w tle, błąd uniemożliwiający odbiór/blokowanie, nieudane nagranie i ważna zmiana po odzyskaniu działania. Bez powiadomienia dla każdego pakietu, duplikatu i wahania RSSI. Powtarzające się błędy łączymy w jeden epizod; odmowa powiadomień w OS nie wpływa na odbiór ani ochronę. Szczegóły pozostają w oknie, menu i historii.

Powiadomienie nie jest warunkiem wykonania blokady. Powrót breloka nie odblokowuje systemu. Nie dodajemy domyślnego odliczania przed blokadą, które zmieniałoby progi L1–L4.

## 5. Start, sen i zapis stanu

| Start / zdarzenie | Zachowanie |
| --- | --- |
| Pierwszy ręczny start | Pokazanie Statusu z „Wybierz brelok”; przejście do wyboru ID |
| Kolejny ręczny start | Pokazanie okna, wczytanie lokalnego ID i ustawień, OBSERVE |
| Autostart po zalogowaniu | Ikona i odbiór w tle, OBSERVE lub wymóg konfiguracji; bez samoczynnego uzbrojenia |
| Zamknięcie/otwarcie okna w tej samej sesji | Zachowanie trybu, danych, pauzy, nagrywania i szkicu formularza |
| Sleep/wake | Po wybudzeniu odrzucenie starych dowodów, odtworzenie odbioru i widoczny stan odzyskiwania |
| Odłączenie monitora / zmiana DPI | Przywrócenie okna w dostępnym obszarze ekranu; brak zagubionego okna poza ekranem |

W PoC sleep/wake zachowuje dotychczasową regułę architektury: przy wcześniejszym ARMED jedno okno START 5 s na nowy poprawny pakiet; sukces przywraca ocenę, brak pakietu oznacza `RESUME_TIMEOUT`. Retry i otwieranie okna nie odnawiają tego terminu. W OBSERVE rejestrujemy wynik bez skutku OS. Należy sprawdzić to na rzeczywistych systemach; sam ukryty frontend nie obsługuje resume.

Zapamiętujemy lokalnie ID, nazwę breloka, zatwierdzone parametry, profil kalibracji, motyw i położenie okna. Autostart odczytujemy również z OS. Tryb ARMED, pauza, aktywne nagranie i niezapisany szkic nie stają się automatycznie stanem po restarcie programu.

Ustawienia interfejsu trzymamy oddzielnie od walidowanej konfiguracji pomiarów. Obecny `AppConfig` Rust nie obsługuje jeszcze nowych parametrów silnika; jego rozszerzenie i migracja schematu są zadaniem implementacyjnym. `ConfigStore::save` zapewnia już walidację oraz atomową wymianę kompletnego pliku ustawień; konsolowe tworzenie nowych plików nadal odmawia nadpisania.

## 6. Połączenie frontendu z backendem

Planowana organizacja:

```text
apps/desktop/native/
├── crates/core/               # istniejący rdzeń + przyszły silnik decyzji
├── crates/platform/           # BLE, pliki, OS i powiadomienia
├── crates/app/                # Backend + długotrwały AppRuntime + CLI
├── crates/shell/              # host Tauri: start, tray, okno, IPC
└── ui/                        # Svelte + TypeScript + Vite + CSS
    └── src/
        ├── App.svelte         # Status, Diagnostyka, Ustawienia
        ├── components/        # karty, jednostki, kontrolki i mały wykres
        ├── state/             # snapshot, formularze i subskrypcja
        └── api/               # typy oraz wywołania IPC
```

`crates/shell` i `ui` są już dodane. GUI jest jedną aplikacją z jednym aktywnym backendem w hoście Tauri. Systemowy WebView może korzystać z własnych procesów pomocniczych. Nie uruchamiamy obok niego CLI jako drugiego skanera.

`runtime::stream_events` udostępnia wspólne źródło BLE/DEMO dla hosta i konsoli. Tauri utrzymuje skaner, monotoniczny czas, backend i ograniczoną historię poza komponentami Svelte. CLI nadal służy debugowaniu i korzysta z tych samych bibliotek.

Planowane granice API:

| API | Odpowiedzialność |
| --- | --- |
| Snapshot / subskrypcja | Pełny stan początkowy i aktualizacje telemetrii; ponowne otwarcie pobiera aktualny snapshot |
| Wybierz ID / zapisz konfigurację | Walidacja, zapis lokalny, przejście do obserwacji przy zmianie pomiarów i reset odpowiednich dowodów |
| Obserwacja / uzbrój / pauza / wznów | Sprawdzenie warunków i zmiana trybu w Rust |
| Zablokuj teraz | Adapter OS i jawny wynik; bez udawania sukcesu |
| Rozpocznij/zatrzymaj nagranie | Sesja lokalnego logu, wynik operacji oraz licznik błędów zapisu |
| Autostart / pokaż / ukryj / zakończ | Integracja OS i cykl życia hosta Tauri |

Komendy mają typowane argumenty i wyniki, sprawdzane w Rust. Aktualizacje małych snapshotów mogą być zdarzeniami Tauri; większy strumień diagnostyki korzysta z kanału IPC. [Mechanizmy przesyłania danych Tauri](https://v2.tauri.app/develop/calling-frontend/).

Plan wydajności START: publikowanie danych do widocznego UI maksymalnie 5 Hz, zdarzenia trybu i błędu od razu, aktualizowanie menu/ikony po zmianie stanu. Ukryty UI nie renderuje wykresu i nie tworzy rosnącej kolejki wiadomości; Rust przechowuje ograniczoną historię 60 s oraz 100 zdarzeń. Wznowienie widoku zastępuje stan aktualnym snapshotem, zamiast odtwarzać całą kolejkę. Zatrzymanie subskrypcji UI nie zatrzymuje BLE.

Technicznie: ikona i menu przez `tray-icon` Tauri, obsługa `CloseRequested` po stronie Rust z `prevent_close()` i ukryciem okna; zmiana ta nie jest zależna od wykonania JavaScript. [Tray](https://v2.tauri.app/learn/system-tray/), [obsługa żądania zamknięcia](https://docs.rs/tauri/latest/tauri/struct.CloseRequestApi.html).

Autostart i jedna instancja przez oficjalne `tauri-plugin-autostart` oraz `tauri-plugin-single-instance`; autostart uruchamia program z `--background`. Na Windows wykorzystujemy ukrywanie pozycji okna na pasku zadań; na macOS osobną politykę aplikacji z ikoną w pasku menu, bo `set_skip_taskbar` nie obsługuje macOS. Konkretną integrację Docka sprawdzamy podczas implementacji. [Autostart](https://v2.tauri.app/plugin/autostart/), [jedna instancja](https://v2.tauri.app/plugin/single-instance/), [ograniczenie API paska zadań](https://docs.rs/tauri/latest/tauri/webview/struct.WebviewWindow.html#method.set_skip_taskbar).

## 7. Kolejność implementacji

| Etap | Rezultat i kryterium odbioru |
| --- | --- |
| 1. Runtime i host Tauri | Jedna sesja backendu niezależna od okna. Małe okno uruchamia się na Macu i Windowsie, CLI zachowuje wspólną logikę |
| 2. Tray i zamknięcie do tła | X ukrywa, ikona przywraca, jedna instancja, jawne pełne zakończenie. Stan i odbiór nie resetują się |
| 3. Status w OBSERVE | Wybór ID, aktualne jednostki, świeżość i jasne braki. Niedostępne funkcje blokady pozostają wyłączone |
| 4. Diagnostyka i log | Wykres 60 s, liczniki, kopiowanie informacji i nagrywanie także po ukryciu okna |
| 5. Ustawienia i autostart | Walidowane zmiany, atomowy zapis, odczyt uprawnień, poprawny start po zalogowaniu w tle |
| 6. Ochrona i OS | Silnik L1–L4, tryby, pauza, ręczna blokada, wyniki adapterów i sleep/wake; menu i okno pokazują ten sam stan |
| 7. Kalibracja | Kreator w tym samym oknie, lokalny profil i świadome zastosowanie ustawień |

Odtwarzanie logów z GUI, eksport CSV i rozbudowane porównywanie wielu sesji mogą powstać po działającym cyklu ochrony. Obsługa traya i praca w tle nie czekają na te dodatki.

## 8. Kryteria odbioru

1. Zamknąć okno i obserwować przez co najmniej 60 s przyrost nowych pakietów w nagraniu; otworzyć i potwierdzić zachowane liczniki, tryb i historię.
2. W ARMED zamknąć okno, odejść z brelokiem i potwierdzić jedną skuteczną blokadę na epizod. Powtórzyć w OBSERVE: powód pojawia się w historii bez blokady OS.
3. W tle uruchomić krótką pauzę: termin jest respektowany bez otwierania UI. W OBSERVE sprawdzić, że pauza/wznowienie nie uruchamia ochrony przypadkowo.
4. Wielokrotnie kliknąć ikonę i uruchomić program ponownie: jedno okno, jedna instancja backendu, żadnego resetu heartbeat ani skanera.
5. Wybrać pełne „Zakończ”: ikona znika, log zostaje domknięty, proces kończy się. Zamykanie sesji OS nie jest blokowane przez przechwytywanie zamknięcia okna.
6. Sprawdzić autostart po prawdziwym wylogowaniu/logowaniu na obu systemach; program działa w tle w OBSERVE, a UI wskazuje faktyczny stan rejestracji OS.
7. Wyłączyć Bluetooth, odmówić uprawnienia, zasymulować błąd IMU i błąd zapisu: konkretne komunikaty, brak starych pomiarów jako aktualnych, brak fałszywego sukcesu ochrony.
8. Sprawdzić sleep/wake przy ukrytym oknie, zachowanie 5-sekundowego okna resume oraz brak jego odnawiania przez retry.
9. Sprawdzić 100/150/200% DPI, duży tekst, motyw jasny/ciemny, klawiaturę oraz odłączenie monitora. Podstawowe akcje pozostają dostępne w małym oknie.
10. Podczas dłuższej sesji porównać użycie pamięci i CPU z oknem widocznym/ukrytym; brak wzrostu historii ponad limity i drugiej sesji BLE. Wyniki zmierzyć zamiast zakładać.

Pierwszy frontend i host Tauri mają produkcyjny build macOS ARM; 4 testy prezentacji, 21 testów Rust i Clippy przeszły. Sprawdzono wygląd DEMO, natywny stan OBSERVE i zachowanie procesu po zamknięciu okna. Pełny test menu traya, fizyczny BLE i Windows pozostają do wykonania. Autostart, kalibracja, nagrywanie z GUI oraz ochrona nadal wymagają implementacji. Bieżący zakres i uruchomienie opisuje [README interfejsu](apps/desktop/native/ui/README.md).
