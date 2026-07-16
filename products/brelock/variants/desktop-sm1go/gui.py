import os
import sys
import tkinter as tk
import customtkinter as ctk

# --- Windows: ustawienie AppUserModelID dla poprawnej ikony na pasku zadań ---
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("breLock.proximity.app")
except Exception:
    pass

# ── Paleta kolorów ──────────────────────────────────────────
BG_DARK      = "#0f172a"
CARD_BG      = "#1e293b"
CARD_BORDER  = "#334155"
ACCENT       = "#3b82f6"
ACCENT_HOVER = "#2563eb"
SUCCESS      = "#22c55e"
SUCCESS_HOVER= "#16a34a"
DANGER       = "#ef4444"
DANGER_HOVER = "#dc2626"
WARNING      = "#f59e0b"
WARNING_HOVER= "#d97706"
TEXT_PRIMARY  = "#f1f5f9"
TEXT_SECONDARY= "#94a3b8"
TRACK_BG     = "#334155"
TRACK_FILL   = "#3b82f6"
THUMB_GLOW   = "#253a52"


# ═══════════════════════════════════════════════════════════
#  Niestandardowy suwak dystansu (laptop.png ═══ bieg_*.png)
# ═══════════════════════════════════════════════════════════
class DistanceSlider(ctk.CTkFrame):
    """
    Suwak RSSI z metaforą dystansu.
    laptop.png na lewym brzegu = blisko urządzenia (-40 dBm).
    bieg_lewo/bieg_prawo.png jako ruchomy kciuk suwaka.
    Kierunek animacji zależy od kierunku ruchu suwaka.
    """
    RSSI_MIN = -90   # najdalej (słaby sygnał)
    RSSI_MAX = -40   # najbliżej (silny sygnał)
    ICON_SIZE = 32   # rozmiar ikon w px

    def __init__(self, master, command=None, initial_value=-70, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.command = command
        self._value = max(self.RSSI_MIN, min(self.RSSI_MAX, initial_value))
        self._prev_value = self._value
        self._dragging = False
        self._hover = False
        self._direction = "right"  # domyślny kierunek: oddalanie się

        # Wymiary Canvas
        self.canvas_w = 350
        self.canvas_h = 58
        self.track_left = 50
        self.track_right = 315
        self.track_y = 26

        # ── Ładowanie obrazków PNG ──
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
        self._tk_images = {}  # trzymamy referencje, żeby GC nie usunęło
        try:
            from PIL import Image as PILImage, ImageTk
            size = (self.ICON_SIZE, self.ICON_SIZE)

            laptop_pil = PILImage.open(os.path.join(base_path, "laptop.png")).resize(size, PILImage.LANCZOS)
            self._tk_images["laptop"] = ImageTk.PhotoImage(laptop_pil)

            left_pil = PILImage.open(os.path.join(base_path, "bieg_lewo.png")).resize(size, PILImage.LANCZOS)
            self._tk_images["lewo"] = ImageTk.PhotoImage(left_pil)

            right_pil = PILImage.open(os.path.join(base_path, "bieg_prawo.png")).resize(size, PILImage.LANCZOS)
            self._tk_images["prawo"] = ImageTk.PhotoImage(right_pil)

            self._images_ok = True
        except Exception as e:
            print(f"[DistanceSlider] Nie udało się załadować ikon: {e}")
            self._images_ok = False

        self.canvas = tk.Canvas(
            self,
            width=self.canvas_w,
            height=self.canvas_h,
            bg=CARD_BG,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(padx=5, pady=(5, 0))

        self._draw()

        # Obsługa myszy
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_motion)

    # ── Konwersja wartość ↔ pozycja ──
    def _value_to_x(self, value):
        """RSSI → pozycja X. -40 (blisko) = lewa strona, -90 (daleko) = prawa."""
        ratio = (self.RSSI_MAX - value) / (self.RSSI_MAX - self.RSSI_MIN)
        return self.track_left + ratio * (self.track_right - self.track_left)

    def _x_to_value(self, x):
        x = max(self.track_left, min(self.track_right, x))
        ratio = (x - self.track_left) / (self.track_right - self.track_left)
        return int(round(self.RSSI_MAX - ratio * (self.RSSI_MAX - self.RSSI_MIN)))

    def _update_direction(self, new_value):
        """Aktualizuje kierunek animacji na podstawie ruchu suwaka."""
        # Uwaga: niższa wartość RSSI = dalej = pozycja bardziej w prawo
        if new_value < self._prev_value:
            self._direction = "right"   # oddalamy się od laptopa (w prawo na ekranie)
        elif new_value > self._prev_value:
            self._direction = "left"    # zbliżamy się do laptopa (w lewo na ekranie)
        self._prev_value = new_value

    # ── Rysowanie ──
    def _draw(self, **kwargs):
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        ty = self.track_y
        px = self._value_to_x(self._value)

        # Tło toru
        self.canvas.create_line(
            self.track_left, ty, self.track_right, ty,
            fill=TRACK_BG, width=6, capstyle="round",
        )

        # Aktywna część toru (laptop → ludzik)
        if px > self.track_left + 1:
            self.canvas.create_line(
                self.track_left, ty, px, ty,
                fill=TRACK_FILL, width=6, capstyle="round",
            )

        # Ikona laptopa (stały punkt odniesienia)
        if self._images_ok:
            self.canvas.create_image(22, ty, image=self._tk_images["laptop"], anchor="center")
        else:
            self.canvas.create_text(
                22, ty, text="💻",
                font=("Segoe UI Emoji", 16), anchor="center",
            )

        # Znaczniki co 10 dBm
        for v in range(self.RSSI_MIN + 10, self.RSSI_MAX, 10):
            dx = self._value_to_x(v)
            self.canvas.create_line(
                dx, ty - 7, dx, ty + 7,
                fill="#475569", width=1,
            )

        # Poświata pod kciukiem podczas hover / drag
        if self._hover or self._dragging:
            self.canvas.create_oval(
                px - 17, ty - 17, px + 17, ty + 17,
                fill=THUMB_GLOW, outline="",
            )

        # Ikona biegnącego ludzika (kciuk suwaka) — kierunek zmienia się dynamicznie
        if self._images_ok:
            img_key = "lewo" if self._direction == "left" else "prawo"
            self.canvas.create_image(px, ty, image=self._tk_images[img_key], anchor="center", tags="thumb")
        else:
            self.canvas.create_text(
                px, ty, text="🚶",
                font=("Segoe UI Emoji", 16), anchor="center", tags="thumb",
            )

        # Etykieta wartości pod kciukiem
        self.canvas.create_text(
            px, ty + 22,
            text=f"{self._value} dBm",
            font=("Segoe UI", 9, "bold"),
            fill=TEXT_PRIMARY, anchor="center",
        )

        # Etykiety krawędzi (ukrywane gdy kciuk blisko)
        if abs(px - self.track_left) > 45:
            self.canvas.create_text(
                self.track_left, ty + 22, text="blisko",
                font=("Segoe UI", 7), fill=TEXT_SECONDARY, anchor="center",
            )
        if abs(px - self.track_right) > 45:
            self.canvas.create_text(
                self.track_right, ty + 22, text="daleko",
                font=("Segoe UI", 7), fill=TEXT_SECONDARY, anchor="center",
            )

    # ── Interakcja ──
    def _near_thumb(self, x, y):
        px = self._value_to_x(self._value)
        return abs(x - px) < 22 and abs(y - self.track_y) < 22

    def _on_motion(self, event):
        was = self._hover
        self._hover = self._near_thumb(event.x, event.y)
        if self._hover != was:
            self._draw()
            self.canvas.config(cursor="hand2" if self._hover else "")

    def _on_press(self, event):
        if self._near_thumb(event.x, event.y):
            self._dragging = True
        else:
            new_val = self._x_to_value(event.x)
            self._update_direction(new_val)
            self._value = new_val
            self._draw()
            if self.command:
                self.command(self._value)

    def _on_drag(self, event):
        if self._dragging:
            new_val = self._x_to_value(event.x)
            self._update_direction(new_val)
            self._value = new_val
            self._draw()
            if self.command:
                self.command(self._value)

    def _on_release(self, event):
        self._dragging = False
        self._draw()

    # ── API ──
    def get(self):
        return self._value

    def set(self, value):
        new_val = max(self.RSSI_MIN, min(self.RSSI_MAX, int(value)))
        self._update_direction(new_val)
        self._value = new_val
        self._draw()


# ═══════════════════════════════════════════════════════════
#  Okno kalibracji
# ═══════════════════════════════════════════════════════════
class CalibrationWindow(ctk.CTkToplevel):
    """
    Okno wyświetlane podczas kalibracji RSSI.
    Pokazuje odliczanie, instrukcję i wynik.
    """
    COUNTDOWN_SECONDS = 5

    def __init__(self, master, target_name, **kwargs):
        super().__init__(master, **kwargs)
        self.title("Kalibracja dystansu")
        self.geometry("380x320")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self.transient(master)
        self.grab_set()

        # Wyśrodkowanie względem okna głównego
        self.update_idletasks()
        mx = master.winfo_x() + (master.winfo_width() // 2) - 190
        my = master.winfo_y() + (master.winfo_height() // 2) - 160
        self.geometry(f"380x320+{mx}+{my}")

        self._remaining = self.COUNTDOWN_SECONDS
        self._finished = False

        # ── UI ──
        self.main_frame = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=14,
                                        border_width=1, border_color=CARD_BORDER)
        self.main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        self.lbl_icon = ctk.CTkLabel(
            self.main_frame, text="📡",
            font=("Segoe UI Emoji", 48),
        )
        self.lbl_icon.pack(pady=(20, 5))

        self.lbl_title = ctk.CTkLabel(
            self.main_frame, text="Kalibracja w toku…",
            font=("Segoe UI", 18, "bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_title.pack(pady=(0, 5))

        self.lbl_instruction = ctk.CTkLabel(
            self.main_frame,
            text=f"Odejdź z urządzeniem\n\"{target_name}\"\nna odległość ~2 metrów",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            justify="center",
        )
        self.lbl_instruction.pack(pady=(0, 10))

        self.lbl_countdown = ctk.CTkLabel(
            self.main_frame, text=f"{self._remaining}",
            font=("Segoe UI", 52, "bold"),
            text_color=ACCENT,
        )
        self.lbl_countdown.pack(pady=(0, 5))

        self.progress = ctk.CTkProgressBar(
            self.main_frame, width=280,
            progress_color=ACCENT, fg_color=TRACK_BG,
            height=8, corner_radius=4,
        )
        self.progress.set(1.0)
        self.progress.pack(pady=(0, 15))

        # Rozpocznij odliczanie
        self._tick()

    def _tick(self):
        """Odliczanie co sekundę."""
        if self._finished:
            return
        if self._remaining > 0:
            self.lbl_countdown.configure(text=f"{self._remaining}")
            frac = self._remaining / self.COUNTDOWN_SECONDS
            self.progress.set(frac)
            self._remaining -= 1
            self.after(1000, self._tick)
        else:
            self.lbl_countdown.configure(text="0")
            self.progress.set(0.0)
            self.lbl_title.configure(text="Analizuję sygnał…")
            self.lbl_instruction.configure(text="Proszę czekać")

    def show_success(self, threshold_dbm):
        """Wyświetl ekran sukcesu i zamknij po chwili."""
        self._finished = True
        self.main_frame.configure(fg_color="#0a3622", border_color=SUCCESS)
        self.lbl_icon.configure(text="✅")
        self.lbl_title.configure(text="Kalibracja zakończona!", text_color=SUCCESS)
        self.lbl_instruction.configure(
            text=f"Nowy próg czułości: {threshold_dbm} dBm",
            text_color=TEXT_PRIMARY,
        )
        self.lbl_countdown.configure(text="✓", text_color=SUCCESS)
        self.progress.configure(progress_color=SUCCESS)
        self.progress.set(1.0)
        self.after(2200, self._safe_close)

    def show_failure(self, message=""):
        """Wyświetl ekran błędu i zamknij po chwili."""
        self._finished = True
        self.main_frame.configure(fg_color="#3a1010", border_color=DANGER)
        self.lbl_icon.configure(text="❌")
        self.lbl_title.configure(text="Kalibracja nieudana", text_color=DANGER)
        self.lbl_instruction.configure(
            text=message if message else "Nie udało się zebrać próbek sygnału",
            text_color=TEXT_PRIMARY,
        )
        self.lbl_countdown.configure(text="✗", text_color=DANGER)
        self.progress.configure(progress_color=DANGER)
        self.progress.set(0.0)
        self.after(3000, self._safe_close)

    def _safe_close(self):
        try:
            self.grab_release()
            self.destroy()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
#  Główne okno aplikacji
# ═══════════════════════════════════════════════════════════
class ProximityGUI(ctk.CTk):
    def __init__(self, start_callback, stop_callback, scan_callback, calibrate_callback=None):
        super().__init__()

        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.scan_callback = scan_callback
        self.calibrate_callback = calibrate_callback

        self.title("breLock")
        self.geometry("430x620")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)

        # ── Ikona aplikacji ──
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))

        ico_path = os.path.join(base_path, "logo.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        png_path = os.path.join(base_path, "logo.png")
        if os.path.exists(png_path):
            try:
                self._icon_img = tk.PhotoImage(file=png_path)
                self.wm_iconphoto(True, self._icon_img)
            except Exception:
                pass

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ── Główny kontener ──
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(fill="both", expand=True, padx=16, pady=12)

        # ─────────────────── NAGŁÓWEK ───────────────────
        hdr = ctk.CTkFrame(self.main, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            hdr, text="🔒 breLock",
            font=("Segoe UI", 22, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr, text="Ochrona zbliżeniowa BLE",
            font=("Segoe UI", 10),
            text_color=TEXT_SECONDARY,
        ).pack(side="right", pady=6)

        # ─────────────── SEKCJA: Urządzenie ────────────────
        self._section("📡  Urządzenie BLE")
        dev_card = self._card()

        dev_row = ctk.CTkFrame(dev_card, fg_color="transparent")
        dev_row.pack(fill="x", pady=8, padx=10)

        self.device_combo = ctk.CTkComboBox(
            dev_row, values=["<Wybierz lub skanuj>"],
            width=225, font=("Segoe UI", 12),
            dropdown_font=("Segoe UI", 11),
            border_color=CARD_BORDER,
        )
        self.device_combo.pack(side="left", padx=(0, 8))

        self.btn_scan = ctk.CTkButton(
            dev_row, text="🔍 Skanuj", width=110,
            font=("Segoe UI", 12, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            corner_radius=8,
            command=self._on_scan_click,
        )
        self.btn_scan.pack(side="right")

        # ─────────── SEKCJA: Próg czułości RSSI ────────────
        self._section("📏  Próg czułości RSSI")
        rssi_card = self._card()

        self.lbl_rssi = ctk.CTkLabel(
            rssi_card, text="Próg: -70 dBm",
            font=("Segoe UI", 13, "bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_rssi.pack(pady=(8, 0))

        self.slider_rssi = DistanceSlider(
            rssi_card,
            command=self._update_rssi_label,
            initial_value=-70,
        )
        self.slider_rssi.pack(pady=(0, 4))

        self.btn_calibrate = ctk.CTkButton(
            rssi_card, text="⚙  Kalibruj dystans (~5 m)",
            width=220, height=30,
            font=("Segoe UI", 11, "bold"),
            fg_color=WARNING, hover_color=WARNING_HOVER,
            text_color="#1a1a2e", corner_radius=8,
            command=self._on_calibrate_click,
        )
        self.btn_calibrate.pack(pady=(0, 2))

        self.lbl_calibrate_status = ctk.CTkLabel(
            rssi_card, text="",
            font=("Segoe UI", 10, "bold"),
        )
        self.lbl_calibrate_status.pack(pady=(0, 6))

        # ─────────── SEKCJA: Opóźnienie blokady ────────────
        self._section("⏱  Opóźnienie blokady")
        time_card = self._card()

        self.lbl_time = ctk.CTkLabel(
            time_card, text="Czas: 1 s",
            font=("Segoe UI", 13, "bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_time.pack(pady=(8, 2))

        self.slider_time = ctk.CTkSlider(
            time_card, from_=1, to=10, number_of_steps=9,
            command=self._update_time_label,
            width=310,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            progress_color=ACCENT, fg_color=TRACK_BG,
        )
        self.slider_time.set(1)
        self.slider_time.pack(pady=(0, 10), padx=20)

        # ─────────────── SEKCJA: Status ─────────────────
        status_card = self._card()
        self.lbl_live_rssi = ctk.CTkLabel(
            status_card,
            text="●  Oczekuje na start",
            font=("Segoe UI", 14, "bold"),
            text_color=TEXT_SECONDARY,
        )
        self.lbl_live_rssi.pack(pady=12)

        # ─────────── PRZYCISK GŁÓWNY ────────────
        self.is_active = False
        self.btn_toggle = ctk.CTkButton(
            self.main,
            text="🛡  Aktywuj Ochronę",
            font=("Segoe UI", 16, "bold"),
            height=50, width=390,
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            corner_radius=12,
            command=self._toggle_protection,
        )
        self.btn_toggle.pack(pady=(10, 5))

        self.on_hide_callback = None

    # ── Helpers do budowy layoutu ──
    def _section(self, text):
        ctk.CTkLabel(
            self.main, text=text,
            font=("Segoe UI", 11, "bold"),
            text_color=TEXT_SECONDARY, anchor="w",
        ).pack(fill="x", padx=5, pady=(8, 2))

    def _card(self):
        f = ctk.CTkFrame(
            self.main,
            fg_color=CARD_BG,
            corner_radius=10,
            border_width=1,
            border_color=CARD_BORDER,
        )
        f.pack(fill="x", pady=(0, 2))
        return f

    # ── Aktualizacja etykiet ──
    def _update_rssi_label(self, value):
        self.lbl_rssi.configure(text=f"Próg: {int(value)} dBm")

    def _update_time_label(self, value):
        self.lbl_time.configure(text=f"Czas: {int(value)} s")

    # ── Skanowanie ──
    def _on_scan_click(self):
        self.btn_scan.configure(state="disabled", text="⏳ Szukam…")
        self.scan_callback()

    def update_devices_list(self, devices: list):
        cur = self.device_combo.get()
        if not devices:
            self.device_combo.configure(values=["<Nie znaleziono>"])
            if cur and cur not in ["<Wybierz lub skanuj>", "<Nie znaleziono>"]:
                self.device_combo.set(cur)
        else:
            if cur and cur not in ["<Wybierz lub skanuj>", "<Nie znaleziono>"] and cur not in devices:
                devices.insert(0, cur)
            self.device_combo.configure(values=devices)
            if cur and cur not in ["<Wybierz lub skanuj>", "<Nie znaleziono>"]:
                self.device_combo.set(cur)
            else:
                self.device_combo.set(devices[0])
        self.btn_scan.configure(state="normal", text="🔍 Skanuj")

    # ── Status na żywo ──
    def update_live_status(self, smoothed, current, is_locked):
        if not self.is_active:
            return
        if is_locked:
            self.lbl_live_rssi.configure(
                text="🔴  ZABLOKOWANE!  (Czekam na sygnał)",
                text_color=DANGER,
            )
        else:
            self.lbl_live_rssi.configure(
                text=f"🟢  EMA: {smoothed:.1f} dBm  │  Live: {current} dBm",
                text_color=SUCCESS,
            )

    # ── Przełączanie ochrony ──
    def _toggle_protection(self):
        if not self.is_active:
            target = self.device_combo.get()
            if target.startswith("<") or not target:
                self.lbl_live_rssi.configure(text="⚠  Wybierz urządzenie!", text_color=WARNING)
                return

            self.is_active = True
            self.btn_toggle.configure(
                text="⏹  Zatrzymaj Ochronę",
                fg_color=DANGER, hover_color=DANGER_HOVER,
            )

            thr = int(self.slider_rssi.get())
            tm = float(self.slider_time.get())

            self.start_callback(target, thr, tm)
            self.lbl_live_rssi.configure(text="⏳  Uruchamianie…", text_color=TEXT_PRIMARY)
        else:
            self.is_active = False
            self.btn_toggle.configure(
                text="🛡  Aktywuj Ochronę",
                fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            )
            self.lbl_live_rssi.configure(text="●  Zatrzymano", text_color=TEXT_SECONDARY)
            self.stop_callback()

    # ── Kalibracja ──
    def _on_calibrate_click(self):
        target = self.device_combo.get()
        if target.startswith("<") or not target:
            self.lbl_calibrate_status.configure(text="Wybierz urządzenie!", text_color=DANGER)
            return

        self.btn_calibrate.configure(state="disabled")
        self.btn_scan.configure(state="disabled")
        self.btn_toggle.configure(state="disabled")
        self.lbl_calibrate_status.configure(text="")

        # Otwórz okno kalibracji z odliczaniem
        self._calib_window = CalibrationWindow(self, target)
        self._calib_window.protocol("WM_DELETE_WINDOW", lambda: None)  # zablokuj zamykanie

        if self.calibrate_callback:
            self.calibrate_callback(target)

    def finish_calibration(self, success, new_threshold=None, message=""):
        self.btn_calibrate.configure(state="normal")
        self.btn_scan.configure(state="normal")
        self.btn_toggle.configure(state="normal")

        if success and new_threshold is not None:
            clamped = max(-90, min(-40, int(new_threshold)))
            self.slider_rssi.set(clamped)
            self._update_rssi_label(clamped)
            self.lbl_calibrate_status.configure(
                text=f"✓  Próg: {clamped} dBm", text_color=SUCCESS,
            )
            # Pokaż sukces w oknie kalibracji
            if hasattr(self, '_calib_window') and self._calib_window.winfo_exists():
                self._calib_window.show_success(clamped)
        else:
            self.lbl_calibrate_status.configure(
                text=message if message else "Błąd kalibracji!", text_color=DANGER,
            )
            # Pokaż błąd w oknie kalibracji
            if hasattr(self, '_calib_window') and self._calib_window.winfo_exists():
                self._calib_window.show_failure(message)

    # ── Ustawienia ──
    def get_settings(self):
        return {
            "target": self.device_combo.get(),
            "threshold": int(self.slider_rssi.get()),
            "timeout": int(self.slider_time.get()),
        }

    def apply_settings(self, config):
        if "target" in config and config["target"]:
            self.device_combo.configure(values=[config["target"]])
            self.device_combo.set(config["target"])

        if "threshold" in config:
            # Obcinamy do zakresu suwaka, żeby wartości spoza zakresu (np. stary -96) nie psuły UI
            val = max(-90, min(-40, int(config["threshold"])))
            self.slider_rssi.set(val)
            self._update_rssi_label(val)

        if "timeout" in config:
            self.slider_time.set(config["timeout"])
            self._update_time_label(config["timeout"])

    # ── Zamykanie ──
    def on_closing(self):
        if self.on_hide_callback:
            self.on_hide_callback()
        else:
            self.force_close()

    def force_close(self):
        self.destroy()
