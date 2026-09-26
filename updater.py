"""Aktualizace Diktovátka z GitHubu.

Kontroluje vydání (GitHub Releases) v repozitáři projektu a sbírá popisy všech verzí
novějších než nainstalovaná, aby uživatel viděl i novinky z verzí, které přeskočil. Aktualizace stáhne ZIP
dané verze přímo z GitHubu (HTTPS), přepíše jen soubory programu – nastavení, historie,
logy, exporty ani virtuální prostředí nemění – a když se změnily knihovny, doinstaluje je.
Vývojovou kopii (složka s .git) nepřepisuje nikdy.

Před přepsáním se stávající soubory programu zálohují do .update_backup. Když se nové
soubory nepodaří zapsat nebo doinstalovat knihovny, záloha se hned vrátí. Po restartu
hlídá hlídač (guard), že nová verze naběhne, jinak vrátí předchozí verzi.
"""

import io
import json
import logging
import os
import re
import shutil
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
BACKUP_DIR = APP_DIR / ".update_backup"  # záloha předchozí verze a hlídač
OK_FILE = APP_DIR / ".update_ok"  # nová verze se po startu ohlásí, že naběhla
GUARD_TIMEOUT = 120  # sekund na to, aby nová verze naběhla

# Tyhle soubory a složky patří uživateli, aktualizace na ně nesahá.
PROTECTED = ("config.json", "config.tmp", "history.db", ".venv/", "exporty/", ".git/", ".claude/", ".ui_request",
             ".ducked.json", ".update.json", ".update_request", ".update_backup/", ".update_ok")
PROTECTED_PREFIXES = ("diktovatko.log", "okno.log", "update.log", "history.db")
SKIP_DIRS = {".venv", ".git", ".claude", "exporty", ".update_backup", "__pycache__"}


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


# Hlídač aktualizace. Spouští ho končící (stará, funkční) verze ze zálohy, takže nezávisí
# na nových souborech. Spustí novou verzi a čeká, až se ohlásí (.update_ok). Když spadne
# nebo se do časového limitu neohlásí, vrátí soubory ze zálohy a spustí starou verzi.
GUARD_SCRIPT = """
import json, os, shutil, subprocess, sys, time
from pathlib import Path

cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
app = Path(cfg["app_dir"]); backup = app / ".update_backup"; ok = app / ".update_ok"
logf = app / "update.log"

def log(msg):
    with open(logf, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\\n")

def spawn(args):
    kw = {"cwd": str(app)}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    return subprocess.Popen([cfg["python"], str(app / "diktovatko.py"), *args], **kw)

def rollback():
    files = backup / "files"
    for p in files.rglob("*"):
        if p.is_file():
            dst = app / p.relative_to(files)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    for rel in cfg.get("added", []):
        try:
            (app / rel).unlink()
        except OSError:
            pass

def tell(title, text):
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, text, title, 0x30 | 0x40000 | 0x10000)
        else:
            subprocess.run(["osascript", "-e", "on run argv", "-e",
                            "display dialog (item 1 of argv) with title (item 2 of argv) buttons {\\"OK\\"} with icon caution",
                            "-e", "end run", text, title], timeout=600)
    except Exception as e:
        log("hlášku nejde zobrazit: %r" % e)

try:
    ok.unlink()
except OSError:
    pass
time.sleep(2)  # stará verze se ještě ukončuje
log("spouštím verzi %s (předchozí %s)" % (cfg["to"], cfg["from"]))
proc = spawn(["--after-update"])
deadline = time.time() + cfg["timeout"]
while time.time() < deadline:
    if ok.exists():
        log("verze %s naběhla" % cfg["to"])
        try:
            ok.unlink()
        except OSError:
            pass
        shutil.rmtree(backup, ignore_errors=True)
        sys.exit(0)
    if proc.poll() is not None:
        log("verze %s skončila s kódem %s před ohlášením" % (cfg["to"], proc.returncode))
        break
    time.sleep(1)
else:
    log("verze %s se do %s s neohlásila" % (cfg["to"], cfg["timeout"]))
    proc.kill()
rollback()
log("vráceno na verzi %s" % cfg["from"])
spawn([])
if not cfg.get("quiet"):
    tell(cfg["title"], cfg["text"])
shutil.rmtree(backup, ignore_errors=True)
"""


def _program_files():
    """Relativní cesty souborů programu (bez dat uživatele, .venv a .git)."""
    out = []
    for root, dirs, files in os.walk(APP_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            rel = (Path(root) / f).relative_to(APP_DIR).as_posix()
            if not _protected(rel) and not rel.endswith(".pyc"):
                out.append(rel)
    return out


def _backup(version, new_rels):
    shutil.rmtree(BACKUP_DIR, ignore_errors=True)
    files = BACKUP_DIR / "files"
    old = _program_files()
    for rel in old:
        dst = files / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(APP_DIR / rel, dst)
    old_set = set(old)
    manifest = {"from": VERSION, "to": version, "added": [r for r in new_rels if r not in old_set]}
    (BACKUP_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest


def rollback():
    """Vrátí soubory programu ze zálohy (po nepovedené instalaci)."""
    manifest = json.loads((BACKUP_DIR / "manifest.json").read_text(encoding="utf-8"))
    files = BACKUP_DIR / "files"
    for p in files.rglob("*"):
        if p.is_file():
            dst = APP_DIR / p.relative_to(files)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    for rel in manifest["added"]:
        (APP_DIR / rel).unlink(missing_ok=True)
    log.warning("Aktualizace vrácena na verzi %s", manifest["from"])


def launch_guard(fail_title, fail_text, quiet=False):
    """Místo prostého restartu spustí hlídače, který novou verzi spustí a pohlídá."""
    manifest = json.loads((BACKUP_DIR / "manifest.json").read_text(encoding="utf-8"))
    guard = BACKUP_DIR / "guard.py"
    guard.write_text(GUARD_SCRIPT, encoding="utf-8")
    cfg = {**manifest, "app_dir": str(APP_DIR), "python": sys.executable, "timeout": GUARD_TIMEOUT,
           "title": fail_title, "text": fail_text, "quiet": quiet}
    (BACKUP_DIR / "guard.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    kw = {"cwd": APP_DIR}
    if sys.platform == "win32":
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen([sys.executable, str(guard), str(BACKUP_DIR / "guard.json")], **kw)


def mark_started():
    """Nová verze po aktualizaci naběhla (čte hlídač)."""
    if "--after-update" in sys.argv:
        OK_FILE.write_text(VERSION, encoding="utf-8")


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
    entries = []
    for name in names:
        rel = name[len(root):]
        if not rel or name.endswith("/") or _protected(rel):
            continue
        target = (APP_DIR / rel).resolve()
        if APP_DIR.resolve() not in target.parents:  # ochrana proti "../" v archivu
            continue
        entries.append((name, rel, target))
    _backup(version, [rel for _, rel, _ in entries])
    try:
        for name, _, target in entries:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
        log.info("Aktualizace na %s: zapsáno %d souborů", version, len(entries))

        new_req = (APP_DIR / "requirements.txt").read_text(encoding="utf-8")
        if new_req != old_req:
            py = Path(sys.executable)
            py = py.with_name("python.exe") if py.name.lower() == "pythonw.exe" and py.with_name("python.exe").exists() else py
            log.info("Změnily se knihovny, instaluji…")
            subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(APP_DIR / "requirements.txt")],
                           cwd=APP_DIR, check=True, capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        rollback()  # nic nesmí zůstat napůl nové
        shutil.rmtree(BACKUP_DIR, ignore_errors=True)
        raise
    return True


def restart():
    """Spustí novou instanci (ta chvíli počká, než se tahle ukončí)."""
    subprocess.Popen([sys.executable, str(APP_DIR / "diktovatko.py"), "--after-update"], cwd=APP_DIR)
