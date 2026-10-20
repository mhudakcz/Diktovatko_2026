"""Hlídač: když Diktovátko nečekaně zmizí (pád, ukončení systémem), spustí ho znovu.

Diktovátko si při startu zapíše číslo procesu do .pid a hlídače spustí (jen jeden běží).
Hlídač každých 10 s ověří, že proces žije. Když zmizel a soubor .pid zůstal (při Ukončit
v menu ho Diktovátko maže), po druhé kontrole Diktovátko spustí znovu. Během aktualizace
(.update_backup) nic nedělá. Víc než 3 restarty za 10 minut = Diktovátko padá pořád,
hlídač to vzdá. Používá jen standardní knihovnu, ať ho nic nerozbije.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PID_FILE = APP_DIR / ".pid"
WATCHDOG_PID = APP_DIR / ".watchdog.pid"
LOG = APP_DIR / "diktovatko.log"
CHECK_SECONDS = 10
MAX_RESTARTS, WINDOW = 3, 600


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S,000") + " INFO Hlídač: " + msg + "\n")
    except OSError:
        pass


def alive(pid):
    """Běží proces s tímto číslem? (Ve Windows nesmí jít o os.kill – ten proces ukončí.)"""
    if not pid:
        return False
    if os.name == "nt":
        import ctypes

        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pid(path):
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def start_app():
    kw = {"cwd": str(APP_DIR)}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen([sys.executable, str(APP_DIR / "diktovatko.py"), "--restarted"], **kw)


def main():
    other = read_pid(WATCHDOG_PID)
    if other and other != os.getpid() and alive(other):
        return  # hlídač už běží
    WATCHDOG_PID.write_text(str(os.getpid()), encoding="utf-8")
    log(f"běží (PID {os.getpid()})")
    restarts, missing = [], 0
    while True:
        time.sleep(CHECK_SECONDS)
        if read_pid(WATCHDOG_PID) != os.getpid():
            return  # mezitím se spustil jiný hlídač (např. po aktualizaci)
        pid = read_pid(PID_FILE)
        if pid is None or alive(pid) or (APP_DIR / ".update_backup").exists():
            missing = 0  # ukončeno přes menu, běží, nebo právě probíhá aktualizace
            continue
        missing += 1
        if missing < 2:
            continue  # druhá kontrola, ať nespouštíme uprostřed restartu
        missing = 0
        now = time.time()
        restarts = [t for t in restarts if now - t < WINDOW]
        if len(restarts) >= MAX_RESTARTS:
            log("Diktovátko padá opakovaně, další restart vzdávám – podívejte se do diktovatko.log a pad.log")
            PID_FILE.unlink(missing_ok=True)
            continue
        restarts.append(now)
        log(f"Diktovátko (PID {pid}) nečekaně skončilo, spouštím ho znovu")
        start_app()
        # Start trvá pár sekund – počkáme, až nová instance zapíše své číslo, ať ji nespustíme dvakrát.
        for _ in range(30):
            time.sleep(1)
            if read_pid(PID_FILE) != pid:
                break


if __name__ == "__main__":
    main()
