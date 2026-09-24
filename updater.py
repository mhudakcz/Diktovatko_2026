"""Aktualizace Diktovátka z GitHubu.

Kontroluje vydání (GitHub Releases) v repozitáři projektu a sbírá popisy všech verzí
novějších než nainstalovaná, aby uživatel viděl i novinky z verzí, které přeskočil. Aktualizace stáhne ZIP
dané verze přímo z GitHubu (HTTPS), přepíše jen soubory programu – nastavení, historie,
logy, exporty ani virtuální prostředí nemění – a když se změnily knihovny, doinstaluje je.
Vývojovou kopii (složka s .git) nepřepisuje nikdy.
"""

import io
import json
import logging
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import config
from version import VERSION

log = logging.getLogger("diktovatko")

REPO = "mhudakcz/Diktovatko_2026"
API_RELEASES = f"https://api.github.com/repos/{REPO}/releases"
ZIP_URL = f"https://github.com/{REPO}/archive/refs/tags/v{{version}}.zip"
RELEASES_URL = f"https://github.com/{REPO}/releases"
APP_DIR = config.APP_DIR
STATE_FILE = APP_DIR / ".update.json"  # co našla tray aplikace – čte ho okno aplikace
REQUEST_FILE = APP_DIR / ".update_request"  # okno aplikace žádá tray aplikaci o instalaci

# Tyhle soubory a složky patří uživateli, aktualizace na ně nesahá.
PROTECTED = ("config.json", "config.tmp", "history.db", ".venv/", "exporty/", ".git/", ".claude/", ".ui_request",
             ".ducked.json", ".update.json", ".update_request")
PROTECTED_PREFIXES = ("diktovatko.log", "okno.log", "history.db")


def parse(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def is_dev_checkout():
    return (APP_DIR / ".git").exists()


def check():
    """Když na GitHubu je novější verze, vrátí {"version", "changes", "notes", "url"}, jinak None.

    changes = všechny vydané verze novější než nainstalovaná, od nejnovější:
    [{"version", "date", "notes"}]. notes = totéž jako jeden text (pro starší okna).
    """
    import httpx

    r = httpx.get(API_RELEASES, params={"per_page": 50}, headers={"Accept": "application/vnd.github+json"},
                  timeout=15, follow_redirects=True)
    r.raise_for_status()
    current = parse(VERSION)
    changes = []
    for rel in r.json():
        v = str(rel.get("tag_name", "")).lstrip("v")
        if rel.get("draft") or rel.get("prerelease") or not re.fullmatch(r"\d+\.\d+\.\d+", v) or parse(v) <= current:
            continue
        changes.append({"version": v, "date": str(rel.get("published_at") or "")[:10],
                        "notes": str(rel.get("body") or "").replace("﻿", "").strip()[:3000]})
    if not changes:
        return None
    changes.sort(key=lambda c: parse(c["version"]), reverse=True)
    changes = changes[:30]
    notes = "\n\n".join(f"{c['version']}\n{c['notes']}" for c in changes)[:8000]
    return {"version": changes[0]["version"], "changes": changes, "notes": notes, "url": RELEASES_URL}


def write_state(**state):
    STATE_FILE.write_text(json.dumps({"current": VERSION, "dev": is_dev_checkout(), **state}, ensure_ascii=False),
                          encoding="utf-8")


def read_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"current": VERSION, "dev": is_dev_checkout()}


def _protected(rel):
    return rel in PROTECTED or any(rel.startswith(p) for p in PROTECTED if p.endswith("/")) or rel.startswith(PROTECTED_PREFIXES)


def install(version):
    """Stáhne a nainstaluje danou verzi. Vrací True, když je potřeba aplikaci restartovat."""
    import httpx

    if is_dev_checkout():
        raise RuntimeError("Vývojová kopie z gitu se aktualizuje přes git pull")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"Neplatná verze {version!r}")
    r = httpx.get(ZIP_URL.format(version=version), timeout=120, follow_redirects=True)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    root = names[0].split("/")[0] + "/"
    # Kontrola, že je to opravdu balík Diktovátka ve verzi, kterou chceme.
    ver_py = zf.read(root + "version.py").decode("utf-8")
    if f'VERSION = "{version}"' not in ver_py:
        raise RuntimeError("Stažený balík neodpovídá požadované verzi")

    old_req = (APP_DIR / "requirements.txt").read_text(encoding="utf-8") if (APP_DIR / "requirements.txt").exists() else ""
    written = 0
    for name in names:
        rel = name[len(root):]
        if not rel or name.endswith("/") or _protected(rel):
            continue
        target = (APP_DIR / rel).resolve()
        if APP_DIR.resolve() not in target.parents:  # ochrana proti "../" v archivu
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zf.read(name))
        written += 1
    log.info("Aktualizace na %s: zapsáno %d souborů", version, written)

    new_req = (APP_DIR / "requirements.txt").read_text(encoding="utf-8")
    if new_req != old_req:
        py = Path(sys.executable)
        py = py.with_name("python.exe") if py.name.lower() == "pythonw.exe" and py.with_name("python.exe").exists() else py
        log.info("Změnily se knihovny, instaluji…")
        subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(APP_DIR / "requirements.txt")],
                       cwd=APP_DIR, check=True, capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True


def restart():
    """Spustí novou instanci (ta chvíli počká, než se tahle ukončí)."""
    subprocess.Popen([sys.executable, str(APP_DIR / "diktovatko.py"), "--after-update"], cwd=APP_DIR)
