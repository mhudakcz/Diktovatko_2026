"""Překlady textů aplikace mimo okno (menu ikony, indikátor, export, hlášky).

Texty okna aplikace jsou v ui/i18n.js. Výchozí jazyk je čeština.
"""

LANGS = ("cs", "en", "de")
DEFAULT = "cs"

STRINGS = {
    "cs": {
        "status.loading": "Načítám model…",
        "status.idle": "Připraveno",
        "status.recording": "Nahrávám…",
        "status.transcribing": "Přepisuji…",
        "status.error": "Chyba, viz diktovatko.log",
        "menu.hotkey": "Zkratka: {keys}",
        "menu.history": "Historie",
        "menu.stats": "Statistiky",
        "menu.settings": "Nastavení",
        "menu.export": "Exportovat historii",
        "menu.exports_folder": "Otevřít složku exportů",
        "menu.log": "Otevřít log",
        "menu.quit": "Ukončit",
        "overlay.failed": "Přepis se nepovedl",
        "err.no_hotkey": "Vyberte klávesovou zkratku.",
        "err.autostart": "Nastavení je uložené, ale automatické spuštění se nepodařilo změnit: {e}",
        "export.title": "Diktování {start} – {end}",
        "export.count": "Záznamů: {n}",
        "export.csv": ["čas", "aplikace", "okno", "text"],
        "period.today": "Dnes", "period.7d": "Posledních 7 dní", "period.10d": "Posledních 10 dní",
        "period.14d": "Posledních 14 dní", "period.20d": "Posledních 20 dní", "period.30d": "Posledních 30 dní",
        "period.month": "Tento měsíc", "period.last_month": "Minulý měsíc", "period.90d": "Posledních 90 dní",
        "period.all": "Vše",
        "lang.cs": "Čeština", "lang.sk": "Slovenština", "lang.en": "Angličtina", "lang.de": "Němčina",
        "lang.pl": "Polština", "lang.uk": "Ukrajinština", "lang.auto": "Rozpoznat automaticky",
        "model.large-v3-turbo": "Nejpřesnější (doporučeno)", "model.medium": "Vyvážený",
        "model.small": "Rychlý, méně přesný", "model.base": "Nejrychlejší, nejméně přesný",
        "key.right ctrl": "Pravý Ctrl", "key.ctrl+alt+space": "Ctrl + Alt + mezerník",
        "key.ctrl+shift+space": "Ctrl + Shift + mezerník", "key.menu": "Klávesa Menu (vedle pravého Ctrl)",
        "key.right cmd": "Pravý ⌘ Cmd", "key.right option": "Pravý ⌥ Option",
        "key.ctrl+option+space": "Ctrl + Option + mezerník",
    },
    "en": {
        "status.loading": "Loading model…",
        "status.idle": "Ready",
        "status.recording": "Recording…",
        "status.transcribing": "Transcribing…",
        "status.error": "Error, see diktovatko.log",
        "menu.hotkey": "Shortcut: {keys}",
        "menu.history": "History",
        "menu.stats": "Statistics",
        "menu.settings": "Settings",
        "menu.export": "Export history",
        "menu.exports_folder": "Open exports folder",
        "menu.log": "Open log",
        "menu.quit": "Quit",
        "overlay.failed": "Transcription failed",
        "err.no_hotkey": "Choose a keyboard shortcut.",
        "err.autostart": "Settings are saved, but start at login could not be changed: {e}",
        "export.title": "Dictation {start} – {end}",
        "export.count": "Entries: {n}",
        "export.csv": ["time", "app", "window", "text"],
        "period.today": "Today", "period.7d": "Last 7 days", "period.10d": "Last 10 days",
        "period.14d": "Last 14 days", "period.20d": "Last 20 days", "period.30d": "Last 30 days",
        "period.month": "This month", "period.last_month": "Last month", "period.90d": "Last 90 days",
        "period.all": "All",
        "lang.cs": "Czech", "lang.sk": "Slovak", "lang.en": "English", "lang.de": "German",
        "lang.pl": "Polish", "lang.uk": "Ukrainian", "lang.auto": "Detect automatically",
        "model.large-v3-turbo": "Most accurate (recommended)", "model.medium": "Balanced",
        "model.small": "Fast, less accurate", "model.base": "Fastest, least accurate",
        "key.right ctrl": "Right Ctrl", "key.ctrl+alt+space": "Ctrl + Alt + Space",
        "key.ctrl+shift+space": "Ctrl + Shift + Space", "key.menu": "Menu key (next to right Ctrl)",
        "key.right cmd": "Right ⌘ Cmd", "key.right option": "Right ⌥ Option",
        "key.ctrl+option+space": "Ctrl + Option + Space",
    },
    "de": {
        "status.loading": "Modell wird geladen…",
        "status.idle": "Bereit",
        "status.recording": "Aufnahme…",
        "status.transcribing": "Wird transkribiert…",
        "status.error": "Fehler, siehe diktovatko.log",
        "menu.hotkey": "Tastenkürzel: {keys}",
        "menu.history": "Verlauf",
        "menu.stats": "Statistik",
        "menu.settings": "Einstellungen",
        "menu.export": "Verlauf exportieren",
        "menu.exports_folder": "Exportordner öffnen",
        "menu.log": "Log öffnen",
        "menu.quit": "Beenden",
        "overlay.failed": "Transkription fehlgeschlagen",
        "err.no_hotkey": "Wählen Sie ein Tastenkürzel.",
        "err.autostart": "Die Einstellungen sind gespeichert, aber der Start bei Anmeldung konnte nicht geändert werden: {e}",
        "export.title": "Diktat {start} – {end}",
        "export.count": "Einträge: {n}",
        "export.csv": ["Zeit", "App", "Fenster", "Text"],
        "period.today": "Heute", "period.7d": "Letzte 7 Tage", "period.10d": "Letzte 10 Tage",
        "period.14d": "Letzte 14 Tage", "period.20d": "Letzte 20 Tage", "period.30d": "Letzte 30 Tage",
        "period.month": "Dieser Monat", "period.last_month": "Letzter Monat", "period.90d": "Letzte 90 Tage",
        "period.all": "Alle",
        "lang.cs": "Tschechisch", "lang.sk": "Slowakisch", "lang.en": "Englisch", "lang.de": "Deutsch",
        "lang.pl": "Polnisch", "lang.uk": "Ukrainisch", "lang.auto": "Automatisch erkennen",
        "model.large-v3-turbo": "Am genauesten (empfohlen)", "model.medium": "Ausgewogen",
        "model.small": "Schnell, weniger genau", "model.base": "Am schnellsten, am wenigsten genau",
        "key.right ctrl": "Rechte Ctrl-Taste", "key.ctrl+alt+space": "Ctrl + Alt + Leertaste",
        "key.ctrl+shift+space": "Ctrl + Shift + Leertaste", "key.menu": "Menütaste (neben der rechten Ctrl-Taste)",
        "key.right cmd": "Rechte ⌘ Cmd", "key.right option": "Rechte ⌥ Option",
        "key.ctrl+option+space": "Ctrl + Option + Leertaste",
    },
}

_current = DEFAULT


def set_lang(lang):
    global _current
    _current = lang if lang in LANGS else DEFAULT


def lang():
    return _current


def t(key, lang=None, **params):
    table = STRINGS.get(lang or _current, STRINGS[DEFAULT])
    value = table.get(key, STRINGS[DEFAULT].get(key, key))
    return value.format(**params) if params and isinstance(value, str) else value


def hotkey_label(hk, default_label, lang=None):
    """Popisek zkratky v daném jazyce (neznámé zkratky zůstanou, jak jsou)."""
    key = "key." + hk
    table = STRINGS.get(lang or _current, STRINGS[DEFAULT])
    return table.get(key, default_label)
