from __future__ import annotations

import os
import sys
import tkinter as tk

import customtkinter as ctk


BG = "#07110d"
SURFACE = "#0d1c16"
SURFACE_ALT = "#12261d"
BORDER = "#203d30"
PRIMARY = "#37d67a"
PRIMARY_HOVER = "#2abe69"
TEXT = "#f2f7f4"
MUTED = "#8fa99c"
BLUE = "#5aa7ff"
WARNING = "#f5b942"
DANGER = "#ff6577"


STATE_STYLE = {
    "starting": (WARNING, "URUCHAMIANIE", "…"),
    "unassigned": (WARNING, "CZEKA NA PRZYPISANIE", "○"),
    "searching": (BLUE, "SZUKAM BRELOCKA", "◎"),
    "protected": (PRIMARY, "OCHRONA AKTYWNA", "✓"),
    "disabled": (MUTED, "OCHRONA WYŁĄCZONA", "—"),
    "locked": (DANGER, "KOMPUTER ZABLOKOWANY", "!"),
    "offline": (DANGER, "BRAK POŁĄCZENIA", "×"),
    "error": (DANGER, "WYMAGANA KONFIGURACJA", "!"),
}


class ProximityGUI(ctk.CTk):
    """Deliberately simple employee-facing application."""

    def __init__(self, sync_callback=None, open_admin_callback=None):
        super().__init__()
        self.sync_callback = sync_callback
        self.open_admin_callback = open_admin_callback
        self.on_hide_callback = None
        self.is_active = False

        ctk.set_appearance_mode("dark")
        self.title("breLock")
        self.geometry("560x620")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._set_window_icon()
        self._build_ui()
        self.update_status(
            "starting", "Uruchamiam ochronę", "Łączę aplikację z panelem firmy."
        )

    def _set_window_icon(self):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
        ico_path = os.path.join(base_path, "logo.ico")
        png_path = os.path.join(base_path, "logo.png")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass
        if os.path.exists(png_path):
            try:
                self._icon_image = tk.PhotoImage(file=png_path)
                self.wm_iconphoto(True, self._icon_image)
            except Exception:
                pass

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 16))
        logo = ctk.CTkFrame(header, width=46, height=46, fg_color=PRIMARY, corner_radius=14)
        logo.pack(side="left", padx=(0, 12))
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="B", text_color=BG, font=("Segoe UI", 22, "bold")).place(relx=.5, rely=.5, anchor="center")
        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left", fill="y")
        ctk.CTkLabel(brand, text="breLock", text_color=TEXT, font=("Segoe UI", 22, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(brand, text="Ochrona zarządzana przez Twoją firmę", text_color=MUTED, font=("Segoe UI", 10), anchor="w").pack(fill="x")

        card = ctk.CTkFrame(self, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=22)
        card.pack(fill="both", expand=True, padx=28, pady=(0, 16))

        self.state_badge = ctk.CTkLabel(card, text="", fg_color=SURFACE_ALT, corner_radius=14, font=("Segoe UI", 10, "bold"), padx=14, pady=7)
        self.state_badge.pack(pady=(26, 18))
        self.state_ring = ctk.CTkFrame(card, width=130, height=130, fg_color=SURFACE_ALT, corner_radius=65, border_width=2, border_color=BORDER)
        self.state_ring.pack()
        self.state_ring.pack_propagate(False)
        self.state_icon = ctk.CTkLabel(self.state_ring, text="…", font=("Segoe UI", 52, "bold"))
        self.state_icon.place(relx=.5, rely=.5, anchor="center")

        self.title_label = ctk.CTkLabel(card, text="", text_color=TEXT, font=("Segoe UI", 22, "bold"))
        self.title_label.pack(pady=(20, 6))
        self.message_label = ctk.CTkLabel(card, text="", text_color=MUTED, font=("Segoe UI", 12), justify="center", wraplength=430)
        self.message_label.pack(padx=28)

        details = ctk.CTkFrame(card, fg_color=SURFACE_ALT, corner_radius=12)
        details.pack(fill="x", padx=24, pady=(24, 14))
        details.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(details, text="PRZYPISANY BRELOCK", text_color=MUTED, font=("Segoe UI", 9, "bold"), anchor="w").grid(row=0, column=0, padx=14, pady=(12, 3), sticky="w")
        self.brelock_label = ctk.CTkLabel(details, text="—", text_color=TEXT, font=("Segoe UI", 11, "bold"), anchor="e")
        self.brelock_label.grid(row=0, column=1, padx=14, pady=(12, 3), sticky="e")
        ctk.CTkLabel(details, text="IDENTYFIKATOR LAPTOPA", text_color=MUTED, font=("Segoe UI", 9, "bold"), anchor="w").grid(row=1, column=0, padx=14, pady=(3, 12), sticky="w")
        self.laptop_label = ctk.CTkLabel(details, text="—", text_color=MUTED, font=("Consolas", 10), anchor="e")
        self.laptop_label.grid(row=1, column=1, padx=14, pady=(3, 12), sticky="e")

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=24, pady=(0, 22))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        self.sync_button = ctk.CTkButton(actions, text="Synchronizuj", height=38, fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color=BG, font=("Segoe UI", 11, "bold"), command=self._sync)
        self.sync_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.admin_button = ctk.CTkButton(actions, text="Panel administratora", height=38, fg_color="transparent", border_color=BORDER, border_width=1, hover_color=SURFACE_ALT, text_color=TEXT, command=self._open_admin)
        self.admin_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        ctk.CTkLabel(self, text="Ustawienia ochrony są kontrolowane centralnie przez administratora.", text_color=MUTED, font=("Segoe UI", 9)).pack(pady=(0, 20))

    def set_installation_id(self, installation_id: str):
        self.laptop_label.configure(text=installation_id[:12].upper())

    def update_status(self, state: str, title: str, message: str, brelock_name: str | None = None):
        color, badge, icon = STATE_STYLE.get(state, STATE_STYLE["error"])
        self.is_active = state in {"searching", "protected"}
        self.state_badge.configure(text=f"●  {badge}", text_color=color)
        self.state_ring.configure(border_color=color)
        self.state_icon.configure(text=icon, text_color=color)
        self.title_label.configure(text=title)
        self.message_label.configure(text=message)
        self.brelock_label.configure(text=brelock_name or "—", text_color=color if brelock_name else MUTED)
        self.sync_button.configure(state="normal", text="Synchronizuj")

    def _sync(self):
        self.sync_button.configure(state="disabled", text="Synchronizuję…")
        if self.sync_callback:
            self.sync_callback()

    def _open_admin(self):
        if self.open_admin_callback:
            self.open_admin_callback()

    def on_closing(self):
        if self.on_hide_callback:
            self.on_hide_callback()
        else:
            self.force_close()

    def force_close(self):
        self.destroy()
