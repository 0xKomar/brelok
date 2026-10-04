# breLock — strona prezentacyjna

Strona przedstawia ogólną zasadę działania sprzętowego PoC breLock: jedna
aplikacja na komputer i jeden brelok Bluetooth. Interakcje na stronie są
symulacją. Demo urządzenia pokazuje film załączony do zgłoszenia, a prezentacja
jest głównym materiałem z danymi i szczegółami projektu.

## Technologie

Next.js 16.2.3 (App Router), React 19, TypeScript, Tailwind CSS 4, Motion
i Lucide. Strona ma widok główny `/` oraz stronę pobierania `/pobierz`.

## Uruchomienie lokalne

Z głównego katalogu repozytorium:

```bash
cd products/brelock/apps/website
npm ci
npm run dev
```

Strona jest dostępna pod `http://localhost:3000`. Build produkcyjny:

```bash
npm run build
npm run start
```

## Wdrożenie na Netlify

Połącz repozytorium `0xKomar/brelok`, wybierz gałąź `main` i następujące ustawienia:

| Ustawienie | Wartość |
| --- | --- |
| Base directory | `products/brelock/apps/website` |
| Package directory | Pozostaw puste — strona jest w base directory. |
| Build command | `npm run build` |
| Publish directory | `.next` (względem base directory) |
| Node.js | `24` |

Główny [netlify.toml](../../../../netlify.toml) zapisuje base directory, polecenie
budowania, publish directory i wersję Node. Konfiguracja jawnie uruchamia
adapter Next.js / OpenNext, który przygotowuje routing, pliki publiczne oraz
optymalizację obrazów. Sam katalog `.next` opublikowany jako zwykłe pliki nie
jest gotową stroną HTML. Strona nie wymaga sekretów ani własnych
zmiennych środowiskowych.

Po zmianie konfiguracji wykonaj ponowny deploy z repozytorium. W logach buildu
powinien być widoczny krok `@netlify/plugin-nextjs`. Konfiguracja ustawia też
`NETLIFY_NEXT_PLUGIN_SKIP=false`, aby istniejące ustawienie pomijania adaptera
nie wyłączało go przy ponownym wdrożeniu.

Więcej informacji: [Netlify — projekty w podkatalogach](https://docs.netlify.com/build/configure-builds/monorepos/)
i [Next.js na Netlify](https://docs.netlify.com/build/frameworks/framework-setup-guides/nextjs/overview/).
