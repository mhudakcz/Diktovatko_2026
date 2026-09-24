"""Okno aplikace: historie, statistiky a nastavení (pywebview + HTML)."""

import os

import pyperclip
import webview

import config
import history
from hotkeys import PRESETS

APP_DIR = config.APP_DIR
UI_REQUEST = APP_DIR / ".ui_request"
WINDOW_TITLE = "Diktovátko"

LANGUAGES = [
    ("cs", "Čeština"), ("sk", "Slovenština"), ("en", "Angličtina"), ("de", "Němčina"),
    ("pl", "Polština"), ("uk", "Ukrajinština"), (None, "Rozpoznat automaticky"),
]
MODELS = [
    ("large-v3-turbo", "Nejpřesnější (doporučeno)"),
    ("medium", "Vyvážený"),
    ("small", "Rychlý, méně přesný"),
    ("base", "Nejrychlejší, nejméně přesný"),
]


class Api:
    # --- historie ---
    def entries(self, period, search):
        start, end = history.period_range(period)
        return history.fetch_dicts(start, end, search.strip() or None)

    def periods(self):
        return history.PERIODS

    def copy(self, text):
        pyperclip.copy(text)
        return True

    def export(self, period, search, fmt="md"):
        start, end = history.period_range(period)
        out, n = history.export(start, end, fmt, search.strip() or None)
        os.startfile(out)
        return n

    # --- statistiky ---
    def stats(self):
        return history.stats()

    # --- nastavení ---
    def get_settings(self):
        return {
            "config": config.load_config(),
            "presets": PRESETS,
            "languages": LANGUAGES,
            "models": MODELS,
            "autostart": config.autostart_enabled(),
        }

    def save_settings(self, cfg, autostart):
        current = config.load_config()
        current.update({k: v for k, v in cfg.items() if k in config.DEFAULT_CONFIG})
        current["hotkeys"] = [h.strip().lower() for h in current["hotkeys"] if h.strip()]
        if not current["hotkeys"]:
            return {"ok": False, "error": "Zapněte alespoň jednu klávesovou zkratku."}
        current["duck_level"] = max(0.0, min(1.0, float(current["duck_level"])))
        config.save_config(current)
        try:
            config.set_autostart(bool(autostart))
        except Exception as e:
            return {"ok": False, "error": f"Nastavení je uložené, ale automatické spuštění se nepodařilo změnit: {e}"}
        return {"ok": True}

    def open_url(self, url):
        import webbrowser

        webbrowser.open(url)

    # --- přepínání sekcí z ikony v liště ---
    def pending_view(self):
        try:
            view = UI_REQUEST.read_text(encoding="utf-8").strip()
            UI_REQUEST.unlink()
            return view
        except FileNotFoundError:
            return None


if __name__ == "__main__":
    webview.create_window(
        WINDOW_TITLE,
        url=str(APP_DIR / "ui" / "app.html"),
        js_api=Api(),
        width=1120,
        height=700,
        min_size=(760, 520),
        background_color="#EEF1F5",
    )
    webview.start()
