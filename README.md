**Projekt hardware’owy — demo działania fizycznego prototypu pokazujemy na filmie załączonym do zgłoszenia.**

# breLock

*Twoja obecność jest kluczem.*

> **Załączona prezentacja jest kluczowym materiałem do zapoznania się z projektem i jego oceny.** Zawiera więcej danych, najważniejsze informacje oraz zdjęcia projektu. Strona internetowa przedstawia tylko ogólną zasadę działania — po szczegóły przejdź do prezentacji.

**breLock to fizyczny brelok Bluetooth i mała aplikacja desktopowa, które pomagają chronić komputer pozostawiony bez opieki.** Zabierasz brelok ze sobą, odchodzisz od biurka, a aplikacja rozpoznaje oddalenie i po jego potwierdzeniu wysyła żądanie systemowej blokady ekranu.

Projekt rozwijamy jako **proof of concept: jeden komputer, jedna aplikacja i jeden brelok**. Odbiór danych, analiza, konfiguracja i kalibracja odbywają się lokalnie.

## Problem

Wychodzisz po kawę, odbierasz telefon albo podchodzisz do kogoś w biurze. Laptop zostaje na biurku z otwartą pocztą, dokumentami i zalogowanymi aplikacjami. Wystarczy zapomnieć o zablokowaniu ekranu, żeby inna osoba mogła skorzystać z Twojej sesji.

Blokada po bezczynności reaguje dopiero po upływie ustawionego czasu. breLock skupia się na samym momencie odejścia od stanowiska — w biurze, coworkingu czy na uczelni.

## Rozwiązanie

Brelok nosisz przy kluczach lub w kieszeni. Komputer odbiera jego sygnał przez **Bluetooth Low Energy (BLE)** i łączy zmiany siły sygnału z informacją o ruchu z akcelerometru. Dzięki temu aplikacja ma więcej informacji do oceny odejścia niż pojedynczy odczyt zasięgu.

Użytkownik kalibruje działanie przy swoim biurku i świadomie włącza ochronę. Aplikacja pracuje w tle, a ekran breloka pokazuje jej stan. Po powrocie logujesz się zwykłym sposobem: hasłem lub biometrią systemu. Ochrona ponownie uzbraja się po wykryciu stabilnego powrotu breloka w pobliże komputera.

**Do lokalnego działania nie potrzebujesz konta, serwera ani połączenia z internetem.**

## Jak to działa?

1. **Połącz brelok.** Wybierz urządzenie w aplikacji desktopowej i nadaj wymagane uprawnienia systemowe.
2. **Skalibruj stanowisko.** Kreator prowadzi przez pomiary w odległości 1, 2 i 3 metrów. Każdy punkt potwierdzasz po zajęciu właściwej pozycji; aplikacja zbiera rzeczywiste odczyty i sprawdza ich jakość.
3. **Włącz ochronę.** Centralny przycisk ON/OFF pokazuje jej stan. Zamknięcie okna ukrywa aplikację do ikony na pasku, a odbiór i analiza nadal działają.
4. **Odejdź z brelokiem.** Silnik decyzji ocenia filtrowany sygnał, trend oddalania, niedawny ruch i świeżość danych. Utrzymujące się oddalenie lub utrata komunikacji mogą uruchomić blokadę.
5. **Wróć do pracy.** Zaloguj się do komputera standardowym sposobem. Aplikacja pozostaje gotowa do ochrony podczas kolejnego odejścia.

## Co potrafi prototyp?

| Funkcja | Co daje użytkownikowi |
| --- | --- |
| **Automatyczna blokada sesji** | Reakcję na potwierdzone odejście z brelokiem oraz zanik świeżych danych urządzenia. |
| **Mała aplikacja działająca w tle** | Granatowe okno, czytelny ON/OFF, status ochrony i ikona na pasku. |
| **Kalibracja 1 / 2 / 3 m** | Dopasowanie modelu sygnału do stanowiska. Nieudana lub anulowana seria zachowuje poprzednie ustawienia. |
| **Ręczne dostrajanie reakcji** | Edycję progu sygnału RSSI i czasu potwierdzenia odejścia; osobny czas wykrywania utraty komunikacji. |
| **Cztery ekrany dotykowe breloka** | Status ochrony, przybliżony dystans, kalibrację i ręczną blokadę; przełączanie gestem w lewo lub w prawo. |
| **Blokada z breloka** | Wysłanie żądania blokady po przytrzymaniu przez 3 sekundy, z animacją postępu. |
| **Diagnostyka na żywo** | Surowy i filtrowany RSSI, dane ruchu, stan połączenia, świeżość pakietów oraz powód decyzji o blokadzie. |
| **Lokalne ustawienia i dane** | Konfigurację zapisywaną na komputerze oraz komunikację bezpośrednio z wybranym brelokiem. |

## Z czego zbudowaliśmy breLock?

| Część | Technologia |
| --- | --- |
| **Urządzenie** | Waveshare ESP32-S3-Touch-LCD-1.28: okrągły ekran dotykowy 1,28″, akcelerometr i żyroskop. |
| **Firmware** | C++, Arduino, PlatformIO; obsługa ekranu, dotyku, czujników i telemetrii. |
| **Łączność** | BLE: reklamy z telemetrią i dwukierunkowy kanał GATT do stanu, kalibracji oraz poleceń. |
| **Logika aplikacji** | Rust: odbiór danych, filtrowanie sygnału, kalibracja, reguły decyzji i integracja z blokadą systemu. |
| **Interfejs desktopowy** | Tauri 2, Svelte 5 i TypeScript; wspólny projekt dla macOS i Windows. |
| **Strona prezentacyjna** | Next.js, React i Tailwind CSS; wizualne przedstawienie pomysłu. |

## Status projektu

To **sprzętowy PoC**, z uruchomionym urządzeniem, komunikacją BLE, odczytem czujników, interfejsem breloka i aplikacją desktopową. Kod obejmuje kalibrację oraz integrację z systemową blokadą macOS i Windows. Próby z fizycznym urządzeniem prowadzimy na macOS; działanie na Windows wymaga osobnej weryfikacji na docelowym systemie.

Wskazanie metrów jest **przybliżeniem wyliczonym z sygnału radiowego**. Kieszeń, orientacja breloka, ściany i odbicia sygnału wpływają na wynik, dlatego kalibracja w miejscu użytkowania jest częścią projektu. Brelok musi być zabierany ze sobą — pozostawiony na biurku nie potwierdzi odejścia właściciela.

Kolejne kroki to sprawdzenie powtarzalności w różnych pomieszczeniach, testy zasilania bateryjnego, docelowa obudowa i dopracowanie bezpieczeństwa komunikacji Bluetooth.

## Demo i materiały prezentacyjne

- **Załączona prezentacja** — główny materiał do oceny projektu, z większą ilością danych, kluczowymi informacjami i zdjęciami.
- **Załączony film** — demo pokazujące działanie fizycznego prototypu.
- **Strona internetowa** — wprowadzenie do pomysłu i ogólnej zasady działania. Szczegóły projektu znajdują się w prezentacji.

## Kod i dokumentacja

- [Opis i zakres PoC](products/brelock/README.md)
- [Architektura oraz reguły decyzji](products/brelock/ARCHITEKTURA_WAVESHARE_BRELOCK.md)
- [Aplikacja desktopowa — kod, kompilacja i uruchomienie](products/brelock/apps/desktop/native/README.md)
- [Firmware — kod i wgrywanie na urządzenie](products/brelock/apps/firmware-esp32/README.md)
- [Ekrany, gesty i komunikacja breloka](products/brelock/DEVICE_UI.md)
- [Strona prezentacyjna](products/brelock/apps/website)
