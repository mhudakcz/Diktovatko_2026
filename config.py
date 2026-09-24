"""Nastavení aplikace (config.json) a automatické spouštění."""

import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    # Zapnuté klávesové zkratky (viz hotkeys.PRESETS), např. "right ctrl", "ctrl+windows", "f9"
    "hotkeys": ["right ctrl"],
    # "hold" = drž a mluv, "toggle" = stiskni pro start, znovu pro stop
    "mode": "hold",
    # Jazyk přepisu ("cs", "en", ...) nebo null pro automatickou detekci
    "language": "cs",
    # Lokální model: tiny / base / small / medium / large-v3-turbo / large-v3
    "model": "large-v3-turbo",
    "beam_size": 1,
    # Nápověda pro model (styl, interpunkce, odborné výrazy, jména)
    "initial_prompt": "Dobrý den, tohle je přepis diktovaného textu s interpunkcí.",
    # Volitelné: API klíč Groq (zdarma na console.groq.com) = mnohem rychlejší přepis v cloudu.
    # Když je prázdný, přepisuje se lokálně a offline.
    "groq_api_key": "",
    "groq_model": "whisper-large-v3-turbo",
    "sounds": True,
    # Za přepsaný text přidat mezeru (hodí se při diktování po kouscích)
    "trailing_space": True,
    # Ukládat přepisy do lokální historie (history.db) včetně času a cílového okna
    "history": True,
    # Plovoucí indikátor nahrávání dole uprostřed obrazovky
    "overlay": True,
    # Během nahrávání ztlumit ostatní aplikace (Spotify, videa…) na tento podíl hlasitosti (0 = úplně)
    "duck_audio": True,
    "duck_level": 0.1,
}


def load_config():
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
    cfg = dict(DEFAULT_CONFIG)
    stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    # Starší verze měly jen jednu zkratku v "hotkey".
    if "hotkeys" not in stored and stored.get("hotkey"):
        stored["hotkeys"] = [stored["hotkey"]]
    stored.pop("hotkey", None)
    cfg.update(stored)
    return cfg


def save_config(cfg):
    data = {k: cfg[k] for k in DEFAULT_CONFIG if k in cfg}
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, CONFIG_PATH)


def groq_key(cfg):
    return cfg["groq_api_key"] or os.environ.get("GROQ_API_KEY", "")


# --- automatické spouštění po přihlášení -----------------------------------------
def _startup_link():
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/Diktovatko.lnk"


def autostart_enabled():
    return _startup_link().exists()


def set_autostart(on):
    link = _startup_link()
    if not on:
        link.unlink(missing_ok=True)
        return
    import comtypes.client

    shell = comtypes.client.CreateObject("WScript.Shell", dynamic=True)
    sc = shell.CreateShortcut(str(link))
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    sc.TargetPath = str(pythonw if pythonw.exists() else sys.executable)
    sc.Arguments = f'"{APP_DIR / "diktovatko.py"}"'
    sc.WorkingDirectory = str(APP_DIR)
    sc.Save()
