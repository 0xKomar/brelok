# Hackathon workspace

Workspace zawiera dwa niezależne produkty. Każdy produkt ma własny katalog,
aplikacje oraz instrukcje uruchomienia.

```text
.
├── products/
│   ├── brelock/
│   │   ├── apps/
│   │   │   ├── control-plane/    # panel firmowy i centralne API
│   │   │   ├── desktop/          # główny klient BLE (Python)
│   │   │   ├── firmware-esp32/   # firmware nadajnika BLE
│   │   │   └── website/          # strona produktowa i pliki instalacyjne
│   │   └── variants/
│   │       └── desktop-sm1go/    # niezależny wariant klienta desktopowego
│   └── cyberswipe/
│       └── apps/
│           ├── api/              # FastAPI, logika gry i dane zadań
│           └── web/              # interfejs gry w Next.js
└── assets/
    └── reference-images/         # nieprzypisane obrazy referencyjne
```

## Produkty

- [breLock](products/brelock/README.md) automatycznie blokuje komputer po
  oddaleniu się użytkownika z urządzeniem BLE.
- [CyberSwipe](products/cyberswipe/README.md) jest grą edukacyjną o
  cyberbezpieczeństwie.

Katalogi `desktop`, `desktop-sm1go` i `website` zachowują swoje istniejące
repozytoria Git. Wariant `desktop-sm1go` nie został scalony z głównym klientem,
aby nie utracić jego historii ani lokalnych zmian.
# breLockCompany
