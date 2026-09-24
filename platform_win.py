"""Windows: vše, co závisí na operačním systému."""

import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
import time
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


def run_on_main(fn):
    fn()  # pystray ve Windows zvládá změny z libovolného vlákna


def foreground_id():
    """Identifikátor aktivního okna – podle něj se pozná, že uživatel mezitím přepnul jinam."""
    return ctypes.windll.user32.GetForegroundWindow()


# --- schránka --------------------------------------------------------------------
CF_UNICODETEXT = 13
_u32, _k32 = ctypes.windll.user32, ctypes.windll.kernel32
_k32.GlobalAlloc.restype = ctypes.c_void_p
_k32.GlobalAlloc.argtypes = (ctypes.c_uint, ctypes.c_size_t)
_k32.GlobalLock.restype = ctypes.c_void_p
_k32.GlobalLock.argtypes = (ctypes.c_void_p,)
_k32.GlobalUnlock.argtypes = (ctypes.c_void_p,)
_u32.SetClipboardData.restype = ctypes.c_void_p
_u32.SetClipboardData.argtypes = (ctypes.c_uint, ctypes.c_void_p)
_u32.GetClipboardSequenceNumber.restype = wt.DWORD


def _open_clipboard():
    for _ in range(20):  # schránku může mít chvíli otevřenou jiná aplikace
        if _u32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def _global(data):
    h = _k32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    p = _k32.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    _k32.GlobalUnlock(h)
    return h


def set_clipboard(text, private=True):
    """Vloží text do schránky. private=True: text se neuloží do historie schránky (Win+V)
    ani do cloudové schránky a správci schránky ho mají ignorovat."""
    if not _open_clipboard():
        raise OSError("Schránka je obsazená jinou aplikací")
    try:
        _u32.EmptyClipboard()
        _u32.SetClipboardData(CF_UNICODETEXT, _global(text.encode("utf-16-le") + b"\0\0"))
        if private:
            zero = (0).to_bytes(4, "little")
            for name in ("ExcludeClipboardContentFromMonitorProcessing", "CanIncludeInClipboardHistory",
                         "CanUploadToCloudClipboard"):
                _u32.SetClipboardData(_u32.RegisterClipboardFormatW(name), _global(zero))
    finally:
        _u32.CloseClipboard()


def get_clipboard():
    """Text ze schránky, nebo None, když v ní text není (obrázek, soubory…)."""
    if not _u32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return None
    import pyperclip

    try:
        return pyperclip.paste()
    except Exception:
        return None


def clipboard_seq():
    return _u32.GetClipboardSequenceNumber()


def wait_modifiers_released(timeout=1.0):
    """Počká, až uživatel pustí Ctrl/Alt/Shift/Win – jinak by z Ctrl+V byla jiná zkratka."""
    end = time.time() + timeout
    while time.time() < end:
        if not any(_u32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
            return
        time.sleep(0.02)


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


def _process_name(hwnd):
    pid = wt.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return ""
    try:
        size = wt.DWORD(1024)
        path = ctypes.create_unicode_buffer(size.value)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            return Path(path.value).name.lower()
        return ""
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def focus_window(proc, title):
    """Vyvolá už otevřené okno aplikace do popředí. Vrací False, když okno neběží.

    Hledá okno s titulkem aplikace, které patří Pythonu – ne třeba složku "Diktovátko" v Průzkumníku.
    """
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def check(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            n = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value == title and _process_name(hwnd).startswith("python"):
                found.append(hwnd)
                return False
        return True

    ctypes.windll.user32.EnumWindows(check, 0)
    if not found:
        return False
    ctypes.windll.user32.ShowWindow(found[0], 9)  # SW_RESTORE
    ctypes.windll.user32.SetForegroundWindow(found[0])
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


def overlay(level_source, engine_source, on_toggle):
    from overlay import Overlay

    return Overlay(level_source, engine_source, on_toggle)


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
