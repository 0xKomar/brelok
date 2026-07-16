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

# ── Sprawdzenie narzędzi ──
if ! command -v pyinstaller &> /dev/null; then
    echo "[!] PyInstaller nie jest zainstalowany. Instaluję..."
    pip3 install pyinstaller
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

# ── Krok 3: Zamiana ikony na .icns (jeśli dostępna) ──
# PyInstaller na macOS domyślnie nie konwertuje .ico → .icns.
# Jeśli masz logo.icns — podmień ręcznie:
if [ -f "logo.icns" ]; then
    echo "[*] Podmieniam ikonę na logo.icns..."
    cp "logo.icns" "dist/${APP_NAME}.app/Contents/Resources/icon-windowed.icns"
fi

# ── Krok 4: Tworzenie .DMG ──
echo "[3/4] Tworzenie obrazu .DMG..."

# Utwórz tymczasowy DMG
DMG_SIZE=$(du -sm "dist/${APP_NAME}.app" | awk '{print $1 + 20}')
hdiutil create \
    -srcfolder "dist/${APP_NAME}.app" \
    -volname "${DMG_VOLUME_NAME}" \
    -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" \
    -format UDRW \
    -size "${DMG_SIZE}m" \
    "${DMG_TEMP}"

# Zamontuj tymczasowy DMG
MOUNT_DIR=$(hdiutil attach -readwrite -noverify -noautoopen "${DMG_TEMP}" | grep -oE '/Volumes/[^ ]+')

# Dodaj link do /Applications (drag & drop w Finderze)
ln -sf /Applications "${MOUNT_DIR}/Applications"

# Opcjonalnie: tło + rozmieszczenie ikon (AppleScript)
echo '
   tell application "Finder"
     tell disk "'"${DMG_VOLUME_NAME}"'"
       open
       set current view of container window to icon view
       set toolbar visible of container window to false
       set statusbar visible of container window to false
       set the bounds of container window to {400, 200, 900, 500}
       set viewOptions to the icon view options of container window
       set arrangement of viewOptions to not arranged
       set icon size of viewOptions to 80
       set position of item "'"${APP_NAME}.app"'" of container window to {130, 150}
       set position of item "Applications" of container window to {370, 150}
       close
       open
       update without registering applications
       delay 2
       close
     end tell
   end tell
' | osascript || true

# Odmontuj
sync
hdiutil detach "${MOUNT_DIR}"

# Skompresuj do finalnego DMG
hdiutil convert "${DMG_TEMP}" -format UDZO -imagekey zlib-level=9 -o "${DMG_FINAL}"
rm -f "${DMG_TEMP}"

echo ""
echo "[4/4] Gotowe!"
echo ""
echo "  Aplikacja:  dist/${APP_NAME}.app"
echo "  Instalator: ${DMG_FINAL}"
echo "  Rozmiar DMG: $(du -h "${DMG_FINAL}" | awk '{print $1}')"
echo ""
echo "============================================"
