"""Okno aplikace: historie, statistiky a nastavení (pywebview + HTML)."""

import pyperclip
import webview

import config
import history
import i18n
import plat
from i18n import t
from version import VERSION

APP_DIR = config.APP_DIR
UI_REQUEST = APP_DIR / ".ui_request"
WINDOW_TITLE = "Diktovátko"

LANGUAGES = ["cs", "sk", "en", "de", "pl", "uk", None]  # jazyky přepisu, None = automaticky
MODELS = ["large-v3-turbo", "medium", "small", "base"]
UI_LANGUAGES = [("cs", "Čeština"), ("en", "English"), ("de", "Deutsch")]  # každý ve svém jazyce


def _lang():
    lang = config.load_config().get("ui_language", i18n.DEFAULT)
    i18n.set_lang(lang)
    return i18n.lang()


class Api:
    # --- historie ---
    def entries(self, period, search):
        start, end = history.period_range(period)
        return history.fetch_dicts(start, end, search.strip() or None)

    def periods(self):
        return [(key, t("period." + key, _lang())) for key, _ in history.PERIODS]

    def copy(self, text):
        pyperclip.copy(text)
        return True

    def export(self, period, search, fmt="md"):
        start, end = history.period_range(period)
        out, n = history.export(start, end, fmt, search.strip() or None, lang=_lang())
        plat.open_path(out)
        return n

    # --- statistiky ---
    def stats(self):
        return history.stats()

    # --- nastavení ---
    def get_settings(self):
        lang = _lang()
        return {
            "config": config.load_config(),
            "lang": lang,
            "presets": [(k, i18n.hotkey_label(k, label, lang)) for k, label in plat.presets()],
            "platform": plat.NAME,
            "version": VERSION,
            "languages": [(v, t("lang." + (v or "auto"), lang)) for v in LANGUAGES],
            "models": [(m, t("model." + m, lang)) for m in MODELS],
            "ui_languages": UI_LANGUAGES,
            "autostart": config.autostart_enabled(),
        }

    def save_settings(self, cfg, autostart):
        current = config.load_config()
        current.update({k: v for k, v in cfg.items() if k in config.DEFAULT_CONFIG})
        current["hotkeys"] = [h.strip().lower() for h in current["hotkeys"] if h.strip()]
        lang = current.get("ui_language", i18n.DEFAULT)
        if not current["hotkeys"]:
            return {"ok": False, "error": t("err.no_hotkey", lang)}
        current["duck_level"] = max(0.0, min(1.0, float(current["duck_level"])))
        config.save_config(current)
        try:
            config.set_autostart(bool(autostart))
        except Exception as e:
            return {"ok": False, "error": t("err.autostart", lang, e=e)}
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
