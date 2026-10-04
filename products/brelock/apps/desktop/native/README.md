# breLock — aplikacja i natywny backend desktopowy

Docelową aplikację rozwijamy w **Rust**. Jeden projekt Cargo daje natywny program dla macOS i Windows; użytkownik gotowego pliku nie potrzebuje Pythona ani Rusta. Transport `btleplug` korzysta z CoreBluetooth na macOS i WinRT na Windows. [Obsługiwane platformy biblioteki](https://github.com/deviceplug/btleplug).

Backend uruchamia się wyłączony (**OBSERVE**) i obsługuje jawne uzbrojenie ochrony. Dostępne są konsola JSONL do inspekcji telemetrii oraz mała aplikacja **Tauri 2 + Svelte 5 + TypeScript + Vite + CSS**. Firmware Arduino/PlatformIO pozostaje osobną częścią urządzenia.

Frontend ma granatowe okno, oddychający ON/OFF, Status, Diagnostykę, Ustawienia i kreator dystansu. Host obsługuje tray, zamknięcie do tła, jedną instancję i atomowy zapis konfiguracji. Ochrona ma reguły L1–L4, kalibrację RSSI dotykiem ekranu breloka oraz natywną blokadę macOS/Windows. Po jednym żądaniu blokady pozostaje w stanie oczekiwania i automatycznie uzbraja kolejny epizod, gdy brelok wróci blisko komputera na 1 s. Podgląd przeglądarkowy jest wyraźnie oznaczonym DEMO i nie blokuje komputera. [Uruchomienie GUI i podglądu](ui/README.md), [pełny plan aplikacji](../../../PLAN_APLIKACJI_DESKTOPOWEJ.md).

Firmware `0.6.0-poc` ma cztery widoki na breloku. Host przesyła ochronę, RSSI, przybliżony dystans i krok kalibracji oraz obsługuje START/POMIAR i blokadę po 3 s przytrzymania. Kreator prowadzi przez 1, 2 i 3 m: odliczanie 2 s, potwierdzenie pozycji i 12–35 s pomiaru na punkt. Dopasowuje A oraz n, sprawdza jakość i zapisuje ustawienia dopiero po całej serii. Brelok sam pokazuje ekran kolejnego punktu. Diagnostyka pokazuje stan GATT. Po reconnectcie host nadaje nową sesję sterowania; ponowiony pakiet nie wykonuje akcji drugi raz. [Dokumentacja ekranów i komunikacji](../../../DEVICE_UI.md).

Na macOS bieżąca aplikacja ma nazwę systemową **breLock PoC** i identyfikator
`dev.brelock.desktop`; historyczne `/Applications/breLock.app` ma inny
identyfikator. ON pozostaje klikalny przy świeżym breloku także przed nadaniem
zgody, aby mógł rozpocząć jej konfigurację. Ochrona zostaje uzbrojona dopiero
po sprawdzeniu rzeczywistego dostępu Dostępność i wysyłania zdarzeń klawiatury.
Przyciski „Otwórz Dostępność” i „Pokaż tę aplikację” prowadzą do ustawień
i dokładnie uruchomionej kopii. Ustawienia pokazują oba odczyty uprawnień i ścieżkę aplikacji.
Lokalny build jest podpisany ad hoc: po zmianie binarnego kodu macOS może
wymagać ponownego zatwierdzenia tej kopii. Stabilny podpis deweloperski
pozostaje krokiem dystrybucji; nie obchodzimy systemowych kontroli TCC.

## Struktura jednego programu

```text
native/
├── Cargo.toml / Cargo.lock     # wspólny build i przypięte zależności
├── rust-toolchain.toml         # Rust 1.98.1, rustfmt, clippy
├── config.example.json        # lokalna konfiguracja
├── ui/                        # frontend Svelte/TypeScript, podgląd i testy
└── crates/
    ├── core/                  # biblioteka brelock-core
    │   ├── src/protocol.rs    # ID, parser BLE v2/v3, jednostki, marker dotyku
    │   ├── src/control.rs     # format GATT, sesje i pojedyncze wykonanie akcji
    │   ├── src/config.rs      # parametry i walidacja konfiguracji
    │   ├── src/signal.rs      # mediana, EMA, trend i model RSSI
    │   ├── src/monitor.rs     # świeżość, liczniki i DeviceSnapshot
    │   ├── src/protection.rs  # uzbrajanie, L1–L4, histereza i zatrzask epizodu
    │   └── tests/
    ├── platform/              # biblioteka brelock-platform
    │   ├── src/ble.rs         # natywne reklamy BLE i zatrzymanie skanera
    │   ├── src/control.rs     # połączenie z wybranym brelokiem, GATT i aktywny RSSI
    │   ├── src/storage.rs     # plik konfiguracji i zapis JSONL
    │   ├── src/system.rs      # preflight i natywna blokada sesji
    │   └── tests/
    ├── app/                   # biblioteka + program konsolowy brelock-desktop
        ├── src/backend.rs    # API aplikacji i AppSnapshot
        ├── src/runtime.rs    # czas życia, kolejki, źródła BLE/demo i retry
        ├── src/main.rs       # wejście CLI do weryfikacji backendu
    │   └── tests/
    └── shell/                 # brelock: host Tauri, tray, okno i IPC
```

GUI łączy cztery moduły w jedną aplikację, bez dodatkowych usług. `core` nie zna systemu, Bluetooth ani plików. `platform` dostarcza obserwacje i lokalny zapis. `app` składa te części i udostępnia stan hostowi `shell`. Systemowy WebView może mieć własne procesy pomocnicze; GUI nie uruchamia obok siebie konsoli ani drugiego skanera.

API `Backend`: `new(config)`, `select_device(id)`, `configure(config)`, `transport_event(event)`, `receive(raw_advertisement)`, `snapshot(monotonic_time)` i `tick(monotonic_time)`. `tick` ocenia ochronę i zwraca najwyżej jedno żądanie blokady na epizod. Zły config nie zastępuje aktywnego stanu; zmiana ustawień rozbraja ochronę i resetuje historię pomiarów. `AppSnapshot` zawiera wybrane urządzenie, listę wykrytych ID, dane, stan transportu, konfigurację, stan ochrony i błędy. Start zawsze jest wyłączony; do uzbrojenia wymagane są świeże pomiary, aktywne BLE oraz dostępny adapter blokady.

## Kompilacja na macOS i Windows

Zainstaluj [Rust przez rustup](https://rust-lang.org/tools/install/). Na macOS wymagane są Xcode Command Line Tools (`xcode-select --install`). Na Windows wybierz toolchain **MSVC** oraz Visual Studio Build Tools z C++ i Windows SDK; [instrukcja Rust](https://rust-lang.github.io/rustup/installation/). Projekt przypina Rust 1.98.1 automatycznie przez `rust-toolchain.toml`.

Z tego katalogu na **obu systemach**:

```text
cargo build --release --locked -p brelock-desktop
cargo test --locked -p brelock-core -p brelock-platform -p brelock-desktop
cargo clippy --all-targets --locked -p brelock-core -p brelock-platform -p brelock-desktop -- -D warnings
cargo fmt --all --check
```

Wynik macOS: `target/release/brelock-desktop`. Wynik Windows: `target\release\brelock-desktop.exe`. Gotowe pliki zawierają kod aplikacji i korzystają z API systemu. Pierwszy build pobiera zależności; następne można wykonać z `--offline`.

To wspólny kod z **osobną kompilacją dla systemu**, nie jeden uniwersalny plik Mac/Windows. Windows `.exe` linkujemy na Windowsie z MSVC/SDK. Samo `cargo check --target x86_64-pc-windows-msvc` na Macu sprawdza kod Windows, ale nie wytwarza `.exe`.

Opcjonalny wspólny plik macOS dla ARM i Intel:

```bash
rustup target add aarch64-apple-darwin x86_64-apple-darwin
cargo build --release --locked -p brelock-desktop --target aarch64-apple-darwin
cargo build --release --locked -p brelock-desktop --target x86_64-apple-darwin
lipo -create target/aarch64-apple-darwin/release/brelock-desktop target/x86_64-apple-darwin/release/brelock-desktop -output target/brelock-desktop-universal
```

[Workflow CI](../../../../../.github/workflows/desktop-native.yml) wykonuje osobne testy i buildy na `macos-latest` i `windows-latest`, tworzy CLI Mac Universal, pakiet GUI macOS i instalator GUI Windows. To konfiguracja do uruchomienia po umieszczeniu zmian w repozytorium; z tej sesji nie wysyłamy kodu ani nie uruchamiamy zdalnego workflow. Sprawdzenia `--workspace` obejmują również host GUI: wcześniej zbuduj UI przez `cd ui`, `npm ci`, `npm run build`.

## Uruchomienie i konfiguracja

Polecenia `cargo run` są takie same na Macu i Windowsie:

```text
cargo run --locked -p brelock-desktop -- demo --duration 5
cargo run --locked -p brelock-desktop -- scan --duration 10
cargo run --locked -p brelock-desktop -- monitor --device-id A1B2C3D4E5F6 --duration 60 --log logs/walk-01.jsonl
cargo run --locked -p brelock-desktop -- decode --hex 0201123456789ABC3412EFCDAB89177B00C8011503A00FFD
cargo run --locked -p brelock-desktop -- init-config --path poc_config.json
cargo run --locked -p brelock-desktop -- --config poc_config.json check-config
```

Po buildzie te same argumenty przyjmuje gotowy program, np. na Macu `./target/release/brelock-desktop demo --duration 5`, a na Windowsie `target\release\brelock-desktop.exe demo --duration 5`.

`--config` jawnie wybiera lokalny JSON; pominięcie flagi oznacza parametry START. `init-config` bez `--path` tworzy plik w katalogu konfiguracji użytkownika wyznaczanym przez system i wypisuje jego ścieżkę. Aby go wczytać, podaj tę ścieżkę przez `--config`. `device_id` może być zapisany w konfiguracji albo przekazany do `monitor` przez CLI. `scan` pokazuje wszystkie napotkane zgodne wersje beaconów, bez automatycznego wyboru. `demo` używa ID `A1B2C3D4E5F6` i jest oznaczone w pierwszym rekordzie sesji.

`Ctrl+C` kończy odbiór i zatrzymuje źródło. `--duration` ogranicza sesję; zamknięcie transportu ma dodatkowy limit 5 s. Konfiguracja i log są tworzone jako **nowe** pliki; istniejący plik nie zostaje nadpisany. Nieprawidłowy JSON, ID, parametry lub brak uprawnień do pliku są błędami.

Stdout zawiera rekordy `session`, `snapshot`, `end`. Z `--log` zapisujemy również surowe zdarzenia transportu, payload, wyniki parsowania i błędy. `snapshot.selected` dotyczy wybranego ID, a `snapshot.devices` pozwala przeprowadzić wybór. Na błędzie komenda zwraca kod różny od zera.

## Co działa w tym etapie

- BLE **v2/v3**: pełny ID z payloadu, boot, uint32 sequence, flagi, RMS, gyro, wiek ruchu i bateria; v3 niesie też licznik dotknięcia. Parser zachowuje zgodność wsteczną z v2.
- Świeżość według monotonicznego czasu: `waiting`, `live`, `stale` po >1,5 s, `lost` po ≥6 s. Stare dane nie są wystawiane jako bieżące.
- Duplikaty, konflikty treści, wrap licznika, stare pakiety i boot ID. Powtórka nie przesuwa heartbeat; restart/przerwa resetuje filtr.
- RSSI: przedziały 250 ms, mediana 750 ms, EMA 0,8 s; trend 3 s, pokrycie ≥80%, rozpiętość ≥2,4 s. Dopiero dobry trend daje estymację prędkości radialnej.
- Natywne zdarzenia reklam BLE, kolejka o ograniczonej wielkości, retry błędów transportu, lokalne pliki i demo bez urządzenia.
- Jawne uzbrojenie ochrony i reguły L1 (utrata pakietów), L2 (RSSI ≤−80 dBm przez 3 s), L3 (IMU + trend oddalania + RSSI ≤−68 dBm przez 0,75 s) i L4 (6 s dowodu RSSI ≤−72 dBm z histerezą). Każdy epizod wywołuje adapter OS najwyżej raz.
- Kreator „Ustaw dystans blokady”: przytrzymanie START przez 3 s otwiera kreator i wyłącza ochronę. Na PC podaj rzeczywistą odległość 0,5–20 m (domyślnie 4 m) i zatwierdź zmianę. POMIAR po 3 s przytrzymania rozpoczyna 2 s stabilizacji i co najmniej 10 s zbierania prawdziwego RSSI. Próba wydłuża się do 35 s przy rzadszym odbiorze. Zapis atomowo ustawia próg z marginesem 3–6 dB i RSSI przy 1 m dopasowane do znanej odległości, bez zmiany współczynnika n. Przerwy, dryf i błąd zapisu zachowują poprzednią konfigurację. Kolejne próby START/POMIAR nie resetują trwającego pomiaru.
- Windows korzysta z `LockWorkStation`; macOS sprawdza zgodę Dostępności i `CGPreflightPostEventAccess`, a następnie wysyła przez CoreGraphics skrót Control–Command–Q z jawnymi flagami modyfikatorów. Przy uzbrajaniu aplikacja może poprosić macOS o zgodę na wysyłanie zdarzeń. Interfejs mówi „żądanie wysłane”, nie obiecuje potwierdzenia blokady.

`distance_estimate_m` i `radial_speed_estimate_m_s` są obliczeniami modelu RSSI. Przed kalibracją używają parametrów START; pomiar ze znaną odległością dopasowuje skalę metrów. Jeden punkt nie wyznacza niezależnie współczynnika n; orientacja, kieszeń i odbicia nadal wpływają na wskazanie. **Rzeczywista prędkość** jest `null`. Demo przechodzi przez ten sam parser/backend, w cyklu spoczynek 0–5 s, oddalanie 5–14 s, zanik 14–22 s, powrót 22–32 s. Mac wymaga uprawnienia Bluetooth dla programu/terminala; [opis biblioteki](https://github.com/deviceplug/btleplug#macos). Nie pollujemy zapisanych properties jako nowych reklam.

Pełny cykl sleep/wake i odtwarzanie logów pozostają dalszymi etapami. Ochrona włącza się wyłącznie po kliknięciu ON; na macOS użytkownik musi zatwierdzić dostęp do Dostępności oraz wysyłania zdarzeń, a na Windows blokada jest dostępna bez dodatkowych uprawnień. Kalibracja jest lokalna dla wybranego breloka i komputera; RSSI jest przybliżeniem zasięgu, a nie pomiarem metrów. [Plan PoC](../../../ARCHITEKTURA_WAVESHARE_BRELOCK.md).

## Weryfikacja lokalna

Sprawdzenia z 3 października 2026:

- `cargo test --workspace --locked`: 35 testów przechodzi; `cargo clippy --workspace --all-targets --locked -- -D warnings` i `cargo fmt --all --check` bez błędów.
- Frontend: `npm run build` (Svelte bez błędów/ostrzeżeń) i `npm test`: 5 testów przechodzi, w tym możliwość rozpoczęcia zgody bez fałszywego ON. `npm run desktop:build -- --bundles app` tworzy macOS `target/release/bundle/macos/breLock.app`.
- Firmware Waveshare `0.5.0-poc` skompilowany i wgrany; 82 sprawdzenia firmware przechodzą. Log potwierdził IMU około 56 próbek/s, wykrycie CST816S bez błędów, GATT oraz przesyłanie stanu/RSSI/dystansu do breloka. Historyczne testy konsoli Python: 53 przechodzą.
- Kod backendu Windows przechodzi `cargo check` dla `x86_64-pc-windows-msvc`. Cross-check całego GUI na Macu wymaga dodatkowo `llvm-rc`, którego nie ma w lokalnym toolchainie; pakiet Windows pozostaje do zbudowania na Windowsie.
- Fizyczne gesty, kalibrację w docelowej lokalizacji i blokadę OS trzeba jeszcze sprawdzić palcem i z wymaganym uprawnieniem macOS.

Historyczna weryfikacja z 1 października 2026:

- 20 testów Rust: protokół, walidacja konfiguracji, świeżość, liczniki, filtr, wybór urządzenia, pliki i jawnie niedostępna blokada systemu.
- `cargo fmt --all --check` i Clippy z `-D warnings`.
- Build release dla macOS ARM i Intel; z obu plików utworzono `target/brelock-desktop-universal`. Demo i `Ctrl+C` działają w gotowym programie bez Pythona i Rusta.
- `cargo check --workspace --all-targets --target x86_64-pc-windows-msvc --locked`: kod Windows sprawdzony, bez lokalnego linkowania `.exe`. Build i testy na Windowsie pozostają do uruchomienia w przygotowanym CI.
- Dekodowanie wzorcowego payloadu daje dokładnie ten sam JSON co istniejący dekoder Python v2. Sprawdzone utworzenie/wczytanie konfiguracji, odrzucenie niepoprawnych argumentów i ochrona istniejących plików.
- 26-sekundowe demo i log JSONL: `waiting → live → stale → lost → live`, czyszczenie starych odczytów, dodatnia/ujemna estymacja prędkości radialnej, reset filtra po zaniku i zliczanie duplikatów.

Natywny `scan --duration 3` poprawnie zakończył sesję z błędem `BLE unavailable: Permission denied`; środowisko nie udzieliło uprawnienia Bluetooth. Odbiór fizycznego breloka nie jest jeszcze potwierdzony. Lokalny toolchain do weryfikacji przygotowano w `/tmp/brelock-rust-tools`, bez zmiany plików startowych powłoki użytkownika. Do uruchomienia gotowego Mac Universal wystarczy:

```bash
./target/brelock-desktop-universal demo --duration 5
```

### Techniczny pomiar kalibracji bez zapisu ustawień

Zakończ GUI z menu aplikacji, aby działał jeden odbiornik. Tester łączy się
z wybranym brelokiem, zbiera prawdziwe odczyty RSSI i podaje kandydat progu.
Nie zapisuje konfiguracji ani nie wykonuje żądań blokady. Wymaga dostępu
Bluetooth dla uruchamiającego programu. Plik śladu musi być nowy.

```bash
cargo run --release --locked -p brelock-desktop --example calibration_probe -- \
  142D6F020F3C logs/calibration-check.jsonl
```

Próba sprzętowa 3 października 2026: 16 próbek / 12,1 s — PASS.
Kreator GUI także zakończył zbieranie i zapisał próg.
