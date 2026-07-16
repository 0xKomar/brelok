# breLock Control Plane

Panel administratora i API zarządzające laptopami, breLockami oraz polityką
blokowania. Dane są przechowywane w SQLite, a każdy administrator widzi tylko
swoją firmę.

Wymagany Python: 3.11–3.13.

## Uruchomienie lokalne

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
set -a; source .env; set +a
uvicorn main:app --host 0.0.0.0 --port 8100
```

Na Windows ustaw zmienne z `.env` w PowerShellu lub systemie, a środowisko
aktywuj poleceniem `venv\Scripts\activate`. Panel będzie dostępny pod
`http://localhost:8100`.

Przed wdrożeniem bezwzględnie zmień hasło administratora i token wdrożeniowy.
Publiczne wdrożenie powinno działać za reverse proxy z HTTPS; wtedy ustaw też
`BRELOCK_SECURE_COOKIE=1`.

## Przepływ wdrożenia

1. Administrator tworzy konfigurację firmy w zmiennych środowiskowych serwera.
2. IT umieszcza obok aplikacji desktopowej plik `deployment.json` z adresem
   panelu, slugiem firmy i jej tokenem wdrożeniowym.
3. Klient przy pierwszym uruchomieniu generuje stały identyfikator instalacji,
   rejestruje laptop i skanuje dostępne breLocki.
4. Administrator loguje się do panelu i przypisuje wykryty breLock do laptopa.
5. Klient pobiera ustawienia automatycznie. Panel pokazuje administratorowi
   wykres RSSI i estymowanej odległości przypisanego breLocka na żywo.
6. Jeden breLock może być przypisany
   tylko do jednego laptopa, a jego sprzętowy identyfikator jest globalnie
   unikalny w bazie.

## Testy

```bash
python -m unittest discover -s tests -v
```
