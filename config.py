"""Nastavení aplikace (config.json), Groq klíč v systémovém trezoru a automatické spouštění."""

import json
import logging
import os
import sys
import threading
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
log = logging.getLogger("diktovatko")

LANGUAGES = ("cs", "sk", "en", "de", "pl", "uk")  # jazyky přepisu (None = automaticky)
MODELS = ("large-v3-turbo", "medium", "small", "base")
UI_LANGUAGES = ("cs", "en", "de")
HISTORY_DAYS = (0, 30, 90, 180, 365)  # jak dlouho uchovávat historii, 0 = napořád

DEFAULT_CONFIG = {
    # Jazyk aplikace (okno, menu ikony, indikátor): "cs", "en" nebo "de"
    "ui_language": "cs",
    # Zapnuté klávesové zkratky (viz PRESETS v hotkeys.py a platform_mac.py),
    # např. "ctrl+windows", "right ctrl", "f9", na Macu "ctrl+cmd", "fn", "right cmd"
    "hotkeys": ["ctrl+cmd"] if sys.platform == "darwin" else ["ctrl+windows"],
    # "hold" = drž a mluv, "toggle" = stiskni pro start, znovu pro stop
    "mode": "hold",
    # Jazyk přepisu ("cs", "en", ...) nebo null pro automatickou detekci
    "language": "cs",
    # Lokální model: large-v3-turbo / medium / small / base
    "model": "large-v3-turbo",
    "beam_size": 1,
    # Nápověda pro model (styl, interpunkce, odborné výrazy, jména). S Groq klíčem se posílá i na Groq.
    "initial_prompt": "Dobrý den, tohle je přepis diktovaného textu s interpunkcí.",
    # Groq klíč se v tomto souboru neukládá, je v trezoru systému (Správce přihlašovacích údajů / Klíčenka).
    # Pole zůstává jen kvůli převodu starších konfigurací a pro systémy bez trezoru.
    "groq_api_key": "",
    "groq_model": "whisper-large-v3-turbo",
    # Přepisovat v počítači i s uloženým Groq klíčem (pomalejší, nahrávka neopustí počítač)
    "offline": False,
    "sounds": True,
    # Za přepsaný text přidat mezeru (hodí se při diktování po kouscích)
    "trailing_space": True,
    # Ukládat přepisy do lokální historie (history.db)
    "history": True,
    # Ukládat k záznamům i názvy oken (konverzace, předměty e-mailů, dokumenty)
    "store_titles": True,
    # Jak dlouho historii uchovávat ve dnech (0 = napořád)
    "history_days": 0,
    # Plovoucí indikátor nahrávání dole uprostřed obrazovky
    "overlay": True,
    # Poloha indikátoru [x, y] v pixelech (přetažením myší), null = dole uprostřed
    "overlay_pos": None,
    # Během nahrávání ztlumit ostatní aplikace (Spotify, videa…) na tento podíl hlasitosti (0 = úplně)
    "duck_audio": True,
    "duck_level": 0.1,
    # Jednou za pár hodin se podívat na GitHub, jestli nevyšla nová verze
    "check_updates": True,
}


# --- Groq klíč v systémovém trezoru -------------------------------------------------
_KEYRING_SERVICE, _KEYRING_USER = "Diktovatko", "groq_api_key"
_key_cache = None
_key_lock = threading.Lock()


def _keyring():
    try:
        import keyring

        return keyring
    except Exception:
        return None


def groq_key(cfg=None):
    """Klíč z proměnné GROQ_API_KEY, ze systémového trezoru, případně z config.json (bez trezoru)."""
    global _key_cache
    if os.environ.get("GROQ_API_KEY"):
        return os.environ["GROQ_API_KEY"]
    with _key_lock:
        if _key_cache is None:
            kr = _keyring()
            try:
                _key_cache = (kr.get_password(_KEYRING_SERVICE, _KEYRING_USER) if kr else None) or ""
            except Exception:
                log.exception("Nepodařilo se přečíst klíč ze systémového trezoru")
                _key_cache = ""
        return _key_cache or (cfg or {}).get("groq_api_key", "")


def set_groq_key(key):
    """Uloží (nebo prázdným řetězcem smaže) klíč v trezoru. Vrací True, když se to povedlo."""
    global _key_cache
    kr = _keyring()
    if kr is None:
        return False
    try:
        if key:
            kr.set_password(_KEYRING_SERVICE, _KEYRING_USER, key)
        else:
            try:
                kr.delete_password(_KEYRING_SERVICE, _KEYRING_USER)
            except Exception:
                pass  # klíč tam nebyl
    except Exception:
        log.exception("Nepodařilo se uložit klíč do systémového trezoru")
        return False
    with _key_lock:
        _key_cache = key or ""
    return True


def invalidate_key_cache():
    """Po změně nastavení v jiném procesu (okno aplikace) klíč znovu načíst z trezoru."""
    global _key_cache
    with _key_lock:
        _key_cache = None


# --- načtení, kontrola a uložení -------------------------------------------------------
def validate(cfg):
    """Vrátí bezpečnou kopii nastavení: neznámé klíče zahodí, špatné hodnoty nahradí výchozími."""
    d = DEFAULT_CONFIG
    out = dict(d)
    for k, v in cfg.items():
        if k in d:
            out[k] = v
    hk = out["hotkeys"]
    out["hotkeys"] = [h.strip().lower()[:40] for h in hk if isinstance(h, str) and h.strip()][:4] if isinstance(hk, list) else d["hotkeys"]
    if not out["hotkeys"]:
        out["hotkeys"] = d["hotkeys"]
    if out["mode"] not in ("hold", "toggle"):
        out["mode"] = d["mode"]
    if out["language"] not in LANGUAGES and out["language"] is not None:
        out["language"] = d["language"]
    if out["model"] not in MODELS:
        out["model"] = d["model"]
    if out["ui_language"] not in UI_LANGUAGES:
        out["ui_language"] = d["ui_language"]
    for k in ("sounds", "trailing_space", "history", "store_titles", "overlay", "duck_audio", "check_updates", "offline"):
        out[k] = bool(out[k])
    try:
        out["duck_level"] = max(0.0, min(1.0, float(out["duck_level"])))
    except (TypeError, ValueError):
        out["duck_level"] = d["duck_level"]
    pos = out["overlay_pos"]
    if not (isinstance(pos, list) and len(pos) == 2 and all(isinstance(v, int) and abs(v) < 100000 for v in pos)):
        out["overlay_pos"] = None
    if out["history_days"] not in HISTORY_DAYS:
        out["history_days"] = d["history_days"]
    out["beam_size"] = out["beam_size"] if isinstance(out["beam_size"], int) and 1 <= out["beam_size"] <= 5 else 1
    for k in ("initial_prompt", "groq_api_key", "groq_model"):
        out[k] = str(out[k] or "")[:2000]
    return out


def load_config():
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
    try:
        stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.exception("config.json je poškozený, používám výchozí nastavení")
        stored = {}
    # Starší verze měly jen jednu zkratku v "hotkey".
    if "hotkeys" not in stored and stored.get("hotkey"):
        stored["hotkeys"] = [stored["hotkey"]]
    cfg = validate(stored)
    # Klíč z dřívějších verzí přesuneme z textového souboru do trezoru systému.
    if cfg["groq_api_key"] and set_groq_key(cfg["groq_api_key"]):
        cfg["groq_api_key"] = ""
        save_config(cfg)
        log.info("Groq klíč přesunut z config.json do systémového trezoru")
    return cfg


def save_config(cfg):
    data = validate(cfg)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if sys.platform != "win32":
        os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG_PATH)


# --- automatické spouštění po přihlášení (implementace je v platform_*.py) ----------
def autostart_enabled():
    import plat

    return plat.autostart_enabled()


def set_autostart(on):
    import plat

    plat.set_autostart(on, APP_DIR)
