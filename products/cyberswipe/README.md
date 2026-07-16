# CyberSwipe

CyberSwipe to gra edukacyjna ucząca rozpoznawania quishingu i obrazów
wygenerowanych przez AI.

## Architektura

- `apps/api` — FastAPI, sesje, punktacja, ranking i `tasks.json`.
- `apps/web` — Next.js, ekran logowania, gra i ranking.

## Uruchomienie API

API należy obecnie uruchamiać z jego katalogu, ponieważ `tasks.json` jest
wczytywany względem bieżącego katalogu roboczego.

```bash
cd products/cyberswipe/apps/api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Uruchomienie aplikacji webowej

```bash
cd products/cyberswipe/apps/web
npm install
npm run dev
```

Domyślnie frontend łączy się z API pod `http://localhost:8000`. Inny adres można
ustawić przez `NEXT_PUBLIC_API_URL`.

