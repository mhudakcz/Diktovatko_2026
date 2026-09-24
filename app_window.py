"""Okno aplikace: historie, statistiky a nastavení (pywebview + HTML).

Metody třídy Api volá JavaScript v okně. Každý vstup z okna se tu kontroluje –
okno nesmí umět spustit soubor, otevřít libovolnou adresu ani zapsat mimo složku exportů.
"""

import logging
import logging.handlers

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
VIEWS = ("history", "stats", "settings")
URLS = {"groq_keys": "https://console.groq.com/keys"}  # jediné adresy, které okno smí otevřít
UI_LANGUAGES = [("cs", "Čeština"), ("en", "English"), ("de", "Deutsch")]  # každý ve svém jazyce

_handler = logging.handlers.RotatingFileHandler(APP_DIR / "okno.log", maxBytes=500_000, backupCount=1, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger("diktovatko.okno")


def _lang():
    i18n.set_lang(config.load_config().get("ui_language", i18n.DEFAULT))
    return i18n.lang()


class Api:
    # --- historie ---
    def entries(self, period, search):
        start, end = history.period_range(str(period))
        return history.fetch_dicts(start, end, str(search).strip() or None)

    def periods(self):
        return [(key, t("period." + key, _lang())) for key, _ in history.PERIODS]

    def copy(self, text):
        pyperclip.copy(str(text))
        return True

    def export(self, period, search, fmt="md"):
        if fmt not in history.EXPORT_FORMATS:
            return {"ok": False, "error": "format"}
        try:
            start, end = history.period_range(str(period))
            out, n = history.export(start, end, fmt, str(search).strip() or None, lang=_lang())
        except Exception as e:  # např. CSV je otevřené v Excelu
            log.exception("Export selhal")
            return {"ok": False, "error": type(e).__name__}
        plat.open_path(out)
        return {"ok": True, "count": n}

    def delete_entries(self, ids):
        return history.delete([int(i) for i in ids][:5000])

    def clear_history(self):
        return history.clear_all()

    # --- statistiky ---
    def stats(self):
        return history.stats()

    # --- nastavení ---
    def get_settings(self):
        lang = _lang()
        cfg = config.load_config()
        cfg["groq_api_key"] = ""  # klíč do okna neposíláme, stačí vědět, že je uložený
        return {
            "config": cfg,
            "has_key": bool(config.groq_key(cfg)),
            "lang": lang,
            "presets": [(k, i18n.hotkey_label(k, label, lang)) for k, label in plat.presets()],
            "platform": plat.NAME,
            "version": VERSION,
            "languages": [(v, t("lang." + (v or "auto"), lang)) for v in (*config.LANGUAGES, None)],
            "models": [(m, t("model." + m, lang)) for m in config.MODELS],
            "ui_languages": UI_LANGUAGES,
            "history_days": list(config.HISTORY_DAYS),
            "autostart": config.autostart_enabled(),
        }

    def save_settings(self, cfg, autostart, key_action="keep", new_key=""):
        """key_action: "keep" = klíč nechat, "set" = uložit new_key, "remove" = smazat."""
        current = config.load_config()
        current.update({k: v for k, v in dict(cfg).items() if k in config.DEFAULT_CONFIG and k != "groq_api_key"})
        current = config.validate(current)
        lang = current["ui_language"]
        if not current["hotkeys"]:
            return {"ok": False, "error": t("err.no_hotkey", lang)}
        new_key = str(new_key or "").strip()
        if key_action == "set" and new_key:
            if not new_key.startswith("gsk_") or len(new_key) < 20:
                return {"ok": False, "error": t("err.bad_key", lang)}
            if not config.set_groq_key(new_key):
                current["groq_api_key"] = new_key  # systém bez trezoru – zůstane v config.json (0600)
        elif key_action == "remove":
            config.set_groq_key("")
            current["groq_api_key"] = ""
        config.save_config(current)  # změní čas souboru, tray aplikace si tak načte i nový klíč
        try:
            config.set_autostart(bool(autostart))
        except Exception as e:
            log.exception("Automatické spuštění")
            return {"ok": False, "error": t("err.autostart", lang, e=e)}
        return {"ok": True}

    def open_url(self, name):
        import webbrowser

        if name in URLS:
            webbrowser.open(URLS[name])

    # --- přepínání sekcí z ikony v liště ---
    def pending_view(self):
        try:
            view = UI_REQUEST.read_text(encoding="utf-8").strip()
            UI_REQUEST.unlink()
        except FileNotFoundError:
            return None
        return view if view in VIEWS else None


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
