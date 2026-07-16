import platform
import os

def lock_system():
    """
    Wykonuje polecenie blokady ekranu (Lock WorkStation), 
    zależnie od tego, na jakim systemie operacyjnym działa aplikacja.
    """
    os_name = platform.system()
    
    if os_name == "Windows":
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            print("[System] Wykonano blokadę ekranu (Windows).")
        except Exception as e:
            print(f"[ERROR] Błąd podczas blokowania Windows: {e}")
            
    elif os_name == "Darwin":  # macOS
        # Standardowy sposób natychmiastowego zablokowania ekranu na macOS (Ctrl + Cmd + Q)
        print("[System] Wykonano blokadę ekranu (macOS).")
        os.system("""osascript -e 'tell application "System Events" to keystroke "q" using {control down, command down}'""")
        
    else:  # Linux (zakładamy sesję okienkową np. Ubuntu)
        print("[System] Wykonano blokadę ekranu (Linux/xdg).")
        os.system('xdg-screensaver lock')


def shutdown_system():
    """
    Jednorazowe wyłączenie komputera (dead loop).
    Wywoływane przy całkowitej utracie urządzenia BLE (np. odłączenie zasilania).
    Zapobiega pętli blokada→odblokowanie→blokada.
    """
    os_name = platform.system()
    
    if os_name == "Windows":
        print("[System] DEAD LOOP — wyłączanie komputera (Windows).")
        os.system("shutdown /s /f /t 0")
        
    elif os_name == "Darwin":
        print("[System] DEAD LOOP — wyłączanie komputera (macOS).")
        os.system("""osascript -e 'tell app "System Events" to shut down'""")
        
    else:
        print("[System] DEAD LOOP — wyłączanie komputera (Linux).")
        os.system("systemctl poweroff")
