#!/bin/bash
set -e

echo "============================================"
echo "  breLock — Budowanie .DMG (macOS)"
echo "============================================"
echo ""

# ── Konfiguracja ──
APP_NAME="breLock"
DMG_NAME="${APP_NAME}.dmg"
DMG_VOLUME_NAME="${APP_NAME}"
DMG_TEMP="dist/${APP_NAME}_temp.dmg"
DMG_FINAL="dist/${DMG_NAME}"

# ── Wirtualne środowisko ──
VENV_DIR="$(cd "$(dirname "$0")" && pwd)/build_venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[*] Tworzę wirtualne środowisko w build_venv/..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# ── Sprawdzenie narzędzi ──
if ! command -v pyinstaller &> /dev/null; then
    echo "[!] PyInstaller nie jest zainstalowany. Instaluję..."
    pip install pyinstaller
fi

# Instalacja zależności projektu (jeśli istnieje requirements.txt)
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
fi

# ── Krok 1: Czyszczenie ──
echo "[1/4] Czyszczenie poprzednich buildów..."
rm -rf dist build "${APP_NAME}.spec"

# ── Krok 2: Budowanie .app ──
echo "[2/4] Budowanie ${APP_NAME}.app..."
pyinstaller \
    --noconfirm \
    --onedir \
    --windowed \
    --icon "logo.ico" \
    --add-data "logo.png:." \
    --add-data "logo.ico:." \
    --add-data "laptop.png:." \
    --add-data "bieg_lewo.png:." \
    --add-data "bieg_prawo.png:." \
    --name "${APP_NAME}" \
    --hidden-import "pystray._darwin" \
    --hidden-import "bleak" \
    --hidden-import "customtkinter" \
    --osx-bundle-identifier "com.brelock.proximity" \
    main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "[BŁĄD] Budowanie .app nie powiodło się!"
    exit 1
fi

# ── Krok 2.5: Wstrzykiwanie uprawnień Bluetooth do Info.plist ──
PLIST="dist/${APP_NAME}.app/Contents/Info.plist"
echo "[*] Dodaję opisy uprawnień Bluetooth do Info.plist..."
/usr/libexec/PlistBuddy -c "Add :NSBluetoothAlwaysUsageDescription string 'breLock potrzebuje dostępu do Bluetooth, aby wykrywać urządzenia BLE w pobliżu i automatycznie blokować/odblokowywać komputer.'" "$PLIST" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :NSBluetoothAlwaysUsageDescription 'breLock potrzebuje dostępu do Bluetooth, aby wykrywać urządzenia BLE w pobliżu i automatycznie blokować/odblokowywać komputer.'" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :NSBluetoothPeripheralUsageDescription string 'breLock potrzebuje dostępu do Bluetooth, aby komunikować się z urządzeniem ESP32.'" "$PLIST" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :NSBluetoothPeripheralUsageDescription 'breLock potrzebuje dostępu do Bluetooth, aby komunikować się z urządzeniem ESP32.'" "$PLIST"

# ── Krok 3: Zamiana ikony na .icns (jeśli dostępna) ──
# PyInstaller na macOS domyślnie nie konwertuje .ico → .icns.
# Jeśli masz logo.icns — podmień ręcznie:
if [ -f "logo.icns" ]; then
    echo "[*] Podmieniam ikonę na logo.icns..."
    cp "logo.icns" "dist/${APP_NAME}.app/Contents/Resources/icon-windowed.icns"
fi

# ── Krok 3.5: Podpisanie .app z entitlements Bluetooth ──
echo "[*] Podpisywanie .app z entitlements (Bluetooth)..."
codesign --deep --force --sign - --entitlements entitlements.plist "dist/${APP_NAME}.app"

# ── Krok 4: Tworzenie .DMG ──
echo "[3/4] Tworzenie obrazu .DMG..."

# Utwórz katalog staging z .app + link do Applications
STAGING_DIR="dist/.dmg_staging"
rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"
cp -R "dist/${APP_NAME}.app" "${STAGING_DIR}/"
ln -s /Applications "${STAGING_DIR}/Applications"

# Utwórz skompresowany DMG bezpośrednio (bez montowania)
rm -f "${DMG_FINAL}"
hdiutil create \
    -srcfolder "${STAGING_DIR}" \
    -volname "${DMG_VOLUME_NAME}" \
    -fs HFS+ \
    -format UDZO \
    -imagekey zlib-level=9 \
    "${DMG_FINAL}"
 
rm -rf "${STAGING_DIR}"

echo ""
echo "[4/4] Gotowe!"
echo ""
echo "  Aplikacja:  dist/${APP_NAME}.app"
echo "  Instalator: ${DMG_FINAL}"
echo "  Rozmiar DMG: $(du -h "${DMG_FINAL}" | awk '{print $1}')"
echo ""
echo "============================================"
