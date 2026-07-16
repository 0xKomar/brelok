# breLock desktop

Minimalny klient pracownika. Rejestruje laptop w panelu firmy, wykrywa breLocki
BLE, pobiera centralną politykę i blokuje komputer po konsekwentnym oddalaniu
przypisanego breLocka. Użytkownik nie konfiguruje progów ani czasów lokalnie.

## Uruchomienie

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Na Windows aktywacja środowiska to `venv\Scripts\activate`.

## Konfiguracja firmy

Skopiuj `deployment.example.json` jako `deployment.json` i uzupełnij dane
otrzymane od administratora. W wersji źródłowej plik leży obok `main.py`, a w
zbudowanej aplikacji obok pliku wykonywalnego.

```json
{
  "control_url": "https://brelock.twoja-firma.pl",
  "company_slug": "twoja-firma",
  "enrollment_token": "dlugi-losowy-token-firmy"
}
```

Te same wartości można przekazać zmiennymi `BRELOCK_CONTROL_URL`,
`BRELOCK_COMPANY_SLUG` i `BRELOCK_ENROLLMENT_TOKEN`. Stan klienta i jego token
urządzenia są przechowywane w katalogu danych aplikacji użytkownika.

## Kiedy komputer jest blokowany

Administrator ustawia wspólne okno analizy w panelu. Blokada nastąpi, gdy:

- EMA pozostaje poniżej statycznego progu przez ustawiony czas, albo
- RSSI konsekwentnie spada przez ustawiony czas, a regresja, łączny spadek
  sygnału i większość kolejnych próbek potwierdzają oddalanie.

Pojedynczy słabszy pakiet i stabilny zaszumiony sygnał nie wystarczają do
uruchomienia reguły trendu.

## Testy

```bash
python -m unittest discover -s tests -v
```
