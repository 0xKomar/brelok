# breLock firmware dla ESP32

Firmware zmienia ESP32 w stabilny beacon BLE współpracujący z desktopowym
breLock. Każdy egzemplarz ma pełny, 48-bitowy identyfikator sprzętowy. Nazwa,
np. `breLock-A1B2C3`, zawiera jego skróconą, czytelną końcówkę.

## Co wysyła ESP

- unikalną nazwę utworzoną z identyfikatora układu,
- dedykowany UUID usługi breLock,
- wersję protokołu i pełny 48-bitowy identyfikator w manufacturer data,
- bieżącą moc nadajnika w scan response.

Reklamy są wysyłane co 40–60 ms. Pozwala to uzyskać płynny wykres RSSI bez
łączenia aplikacji desktopowej z ESP.

## Wymagania

- ESP32 z obsługą BLE,
- PlatformIO CLI lub rozszerzenie PlatformIO dla VS Code,
- przewód USB obsługujący transmisję danych.

Domyślna konfiguracja używa płytki `esp32dev`. Dla innego modelu zmień `board`
w `platformio.ini`. ESP32-S2 i ESP32-P4 nie mają natywnego BLE i nie nadają się
do tego wariantu firmware.

## Wgranie

```bash
cd products/brelock/apps/firmware-esp32
pio run -t upload
pio device monitor
```

Po starcie monitor powinien pokazać nazwę urządzenia, jego BLE address, UUID
usługi i interwał reklamowania. Uruchomiony klient pracownika zgłosi breLock do
panelu firmy automatycznie; administrator przypisuje go tam do laptopa.

## Kalibracja odległości

1. Ustaw ESP dokładnie metr od komputera.
2. Otwórz diagnostykę przypisanego laptopa w panelu administratora.
3. Dopasuj `RSSI @ 1 m` do stabilnej wartości widocznej na wykresie.
4. Przenieś ESP na granicę strefy i ustaw próg RSSI oraz czas reakcji.

Odległość wyliczana z RSSI jest estymacją. Orientacja anteny, ciało użytkownika,
meble i sieci Wi-Fi mogą zmieniać wynik.

## LED

- wolne miganie — ESP reklamuje się i czeka,
- światło ciągłe — klient BLE jest połączony,

Jeżeli LED płytki jest aktywny stanem niskim albo używa innego pinu, ustaw
`LED_BUILTIN` w `platformio.ini`, np. `-D LED_BUILTIN=8`.

## Uwaga przed produkcją

Manufacturer data używa identyfikatora firmy `0xFFFF`, przeznaczonego do testów.
Przed komercyjną dystrybucją należy uzyskać własny Bluetooth SIG Company ID.
Obecny protokół identyfikuje nadajnik, ale nie wykonuje kryptograficznego
challenge–response; nie należy traktować samej nazwy BLE jako odpornej na
podszywanie się autoryzacji.
