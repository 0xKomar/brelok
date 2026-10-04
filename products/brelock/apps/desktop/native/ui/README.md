# breLock — interfejs desktopowy

Pierwsza wersja w **Svelte 5 + TypeScript + Vite + CSS**, osadzona w **Tauri 2**. Granatowe, płaskie powierzchnie bez gradientów. Główny element to okrągły ON/OFF z zielonym/czerwonym stanem i dwoma pierścieniami oddychającymi co 4,2 s. Systemowa preferencja ograniczenia animacji wyłącza ruch.

## Podgląd wyglądu

Z tego katalogu, przy zainstalowanym Node.js 24 lub nowszym:

```bash
npm ci
npm run dev
```

Otwórz `http://127.0.0.1:1420/`. Przeglądarka pokazuje **DEMO** z przykładową telemetrią. ON/OFF zmienia prezentację; nie uzbraja ochrony ani nie blokuje systemu. Ustawienia podglądu pozostają w pamięci bieżącej sesji. Podgląd nie łączy się z fizycznym brelokiem.

## Natywna aplikacja

Potrzebne są Rust 1.98.1 i systemowe narzędzia kompilacji opisane w [README backendu](../README.md). Na macOS i Windows:

```bash
npm ci
npm run desktop:dev
npm run desktop:build -- -- --locked
```

`desktop:dev` sam uruchamia Vite; zakończ wcześniej osobno uruchomiony serwer na porcie 1420. Build sprawdza i pakuje frontend. macOS: `../target/release/bundle/macos/breLock.app`; Windows: instalator w `../target/release/bundle/nsis/`. Kod jest wspólny; pakiety kompilujemy osobno na każdym systemie. GUI macOS ma architekturę komputera wykonującego build; wcześniejszy CLI Universal jest osobnym narzędziem. [Pakowanie Tauri](https://v2.tauri.app/distribute/).

Natywna wersja pobiera prawdziwe snapshoty Rust przez IPC. **Backend działa wyłącznie w OBSERVE**, dlatego przycisk pozostaje czerwony OFF i jest nieaktywny. Rust również odrzuca próbę włączenia ochrony. Silnik L1–L4 oraz adapter blokady OS nie są jeszcze zaimplementowane.

## Dostępne funkcje

- **Status:** ON/OFF, opis ograniczenia, wybrany brelok, świeżość, RSSI, ruch, napięcie baterii i wiek pakietu. Brak danych to „—”, brak IMU to „Nieznany”.
- **Diagnostyka:** wykres RSSI z ostatnich 60 s, estymacje dystansu/prędkości radialnej, trend i R², IMU, bateria, liczniki, zdarzenia i kopiowanie raportu JSON. Przerwy rozdzielają linie wykresu.
- **Ustawienia:** wybór pełnego ID z listy lub wpisanie 12 znaków hex; edycja A/n oraz czasów świeżości/utraty. Rust waliduje dane i atomowo zapisuje lokalny JSON. Błąd zapisu nie zastępuje aktywnej konfiguracji.
- **Tło:** X i „Ukryj okno” chowają do ikony. Menu przywraca widoki i pozwala zakończyć proces. Jedna instancja, obsługa ponownego otwarcia na macOS i start `--background`. Nie ma jeszcze rejestracji autostartu.

Rust utrzymuje jeden skaner niezależnie od okna. Historia ma limit 60 s / 301 próbek, zdarzenia 100 wpisów. Ukryte okno nie otrzymuje odświeżeń; po pokazaniu dostaje aktualny stan przy najbliższym odświeżeniu (200 ms). Pakiety nie nadpisują niezapisanego formularza.

Ochrona, pauza, ręczna blokada, kalibracja, nagrywanie z GUI i autostart pozostają kolejnymi etapami. Metry i prędkość radialna są estymacjami RSSI z parametrami START; rzeczywista prędkość nie jest mierzona. Konfiguracja natywna jest w katalogu użytkownika wyznaczonym przez system; `BRELOCK_CONFIG_PATH` umożliwia wybranie innej ścieżki do testów.

## Pliki

```text
src/App.svelte                 # widoki, formularze, obsługa akcji
src/app.css                    # kolory, układ, animacja, dostępność
src/components/PowerButton.svelte
src/components/SignalChart.svelte
src/components/Icon.svelte
src/api/native.ts              # komendy i subskrypcje Tauri
src/api/preview.ts             # jawny podgląd DEMO
src/api/types.ts               # kontrakt snapshotów Rust
src/state/presentation.ts      # jednostki, limity, przerwy wykresu
../crates/shell/               # okno, tray, lifecycle, IPC, skaner
```

## Weryfikacja

```bash
npm test
npm run build
```

2 października 2026: 4 testy prezentacji, Svelte/TypeScript bez błędów i ostrzeżeń, produkcyjny build UI i pakiet `.app` na macOS ARM. Sprawdzono czerwony OFF, zielony ON w DEMO, Diagnostykę/Ustawienia i brak poziomego przewijania w małym oknie. Natywne okno odbiera stan Rust; po X proces pozostaje uruchomiony. Pełny test menu traya, odbioru fizycznego breloka i Windows pozostaje do wykonania. [CI obu systemów](../../../../../../.github/workflows/desktop-native.yml) przygotowuje testy oraz pakiety; nie uruchomiono go zdalnie w tej sesji.
