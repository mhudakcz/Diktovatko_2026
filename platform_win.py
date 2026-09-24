"""Windows: vše, co závisí na operačním systému."""

import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
from pathlib import Path

NAME = "windows"
PASTE_HINT = "Ctrl+V"


def init_process():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # ostré písmo a indikátor na HiDPI displejích
    except Exception:
        pass


def beep(kind):
    import winsound

    freq, ms = {"start": (880, 60), "stop": (600, 60), "ready": (1000, 80), "error": (200, 300)}[kind]
    threading.Thread(target=winsound.Beep, args=(freq, ms), daemon=True).start()


def paste():
    import keyboard

    keyboard.send("ctrl+v")


def foreground_window():
    """Vrátí (název procesu, titulek okna) aktuálně aktivního okna."""
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    app = ""
    handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if handle:
        size = wt.DWORD(1024)
        path = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            app = Path(path.value).name
        kernel32.CloseHandle(handle)
    return app, title


def open_path(path):
    os.startfile(path)


def focus_window(proc, title):
    """Vyvolá už otevřené okno aplikace do popředí. Vrací False, když okno neběží."""
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    if not hwnd:
        return False
    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    return True


def hotkey_manager(on_press, on_release, on_interrupt):
    from hotkeys import HotkeyManager

    return HotkeyManager(on_press, on_release, on_interrupt)


def presets():
    from hotkeys import PRESETS

    return PRESETS


def audio_ducker(level):
    from audio_duck import AudioDucker

    return AudioDucker(level)


def overlay(level_source):
    from overlay import Overlay

    return Overlay(level_source)


# --- automatické spouštění po přihlášení -----------------------------------------
def _startup_link():
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/Diktovatko.lnk"


def autostart_enabled():
    return _startup_link().exists()


def set_autostart(on, app_dir):
    link = _startup_link()
    if not on:
        link.unlink(missing_ok=True)
        return
    import comtypes.client

    shell = comtypes.client.CreateObject("WScript.Shell", dynamic=True)
    sc = shell.CreateShortcut(str(link))
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    sc.TargetPath = str(pythonw if pythonw.exists() else sys.executable)
    sc.Arguments = f'"{app_dir / "diktovatko.py"}"'
    sc.WorkingDirectory = str(app_dir)
    sc.Save()
