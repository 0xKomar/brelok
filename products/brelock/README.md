# breLock

breLock to aplikacja bezpieczeństwa oparta na BLE. Klient desktopowy monitoruje
siłę sygnału wybranego urządzenia i blokuje system po opuszczeniu skonfigurowanej
strefy.

## Katalogi

- `apps/desktop` — główna implementacja klienta Python/CustomTkinter.
- `apps/control-plane` — webowy panel administratora, API i baza SQLite.
- `apps/firmware-esp32` — firmware nadajnika BLE dla ESP32.
- `apps/website` — landing page Next.js i publiczne instalatory.
- `variants/desktop-sm1go` — drugi, niezależny fork klienta z dodatkowymi
  zmianami dotyczącymi buildów macOS. Pozostaje osobnym repozytorium Git.

## Uruchomienie strony

```bash
cd products/brelock/apps/website
npm install
npm run dev
```

## Uruchomienie klienta desktopowego

```bash
cd products/brelock/apps/desktop
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Uruchomienie panelu administratora

```bash
cd products/brelock/apps/control-plane
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
set -a; source .env; set +a
uvicorn main:app --port 8100
```

Szczegóły przypisywania urządzeń i konfiguracji wdrożeniowej opisuje
`apps/control-plane/README.md`.

Skrypty `build.sh` i `build.bat` należy uruchamiać z katalogu wybranego klienta,
ponieważ korzystają ze ścieżek względnych.
