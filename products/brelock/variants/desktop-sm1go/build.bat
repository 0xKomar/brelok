@echo off
chcp 65001 >nul 2>&1
echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║    breLock — Build ^& Package (Windows Installer)║
echo  ╚══════════════════════════════════════════════════╝
echo.

echo [1/3] Sprawdzam PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo       PyInstaller nie znaleziony — instaluję...
    python -m pip install pyinstaller
)

echo [2/3] Budowanie aplikacji (tryb --onedir)...
if exist "dist_new" rd /s /q "dist_new"
if exist "build_new" rd /s /q "build_new"

python -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --icon "logo.ico" ^
    --add-data "logo.png;." ^
    --add-data "logo.ico;." ^
    --add-data "laptop.png;." ^
    --add-data "bieg_lewo.png;." ^
    --add-data "bieg_prawo.png;." ^
    --name "breLock" ^
    --hidden-import "pystray._win32" ^
    --hidden-import "bleak" ^
    --hidden-import "customtkinter" ^
    --collect-data "customtkinter" ^
    --distpath "dist_new" ^
    --workpath "build_new" ^
    main.py

if %errorlevel% neq 0 (
    echo.
    echo   [BLAD] Budowanie paczki zrodlowej nie powiodlo sie!
    pause
    exit /b 1
)

echo [3/3] Pakowanie instalatora za pomoca Inno Setup...

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if defined ISCC (
    echo       Kompilacja instalatora za pomoca Inno Setup (%ISCC%)...
    if not exist "installer_output" mkdir "installer_output"
    "%ISCC%" installer.iss
    if %errorlevel% equ 0 (
        echo.
        echo   [✔] GOTOWE! Plik do pobrania:
        echo       installer_output\breLock_Setup.exe
    ) else (
        echo   [x] Budowanie instalatora nie powiodlo sie.
    )
) else (
    echo   [x] Nie znaleziono Inno Setup!
    echo       Pobierz z https://jrsoftware.org/isdl.php, zainstaluj i uruchom ponownie.
)

echo.
pause
