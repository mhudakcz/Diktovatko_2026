"""Windows: vše, co závisí na operačním systému."""

import ctypes
import ctypes.wintypes as wt
import logging
import os
import re
import sys
import threading
import time
from pathlib import Path

from urls import clean_url

log = logging.getLogger("diktovatko")

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
_u32.GetClipboardData.restype = ctypes.c_void_p
_u32.GetClipboardData.argtypes = (ctypes.c_uint,)
_u32.EnumClipboardFormats.restype = ctypes.c_uint
_u32.EnumClipboardFormats.argtypes = (ctypes.c_uint,)
_k32.GlobalSize.restype = ctypes.c_size_t
_k32.GlobalSize.argtypes = (ctypes.c_void_p,)
# Formáty, jejichž data nejsou blok paměti (GDI objekty, kreslení vlastníkem) – uložit nejdou.
# Obrázek je ve schránce zároveň jako CF_DIB/CF_DIBV5, ze kterých si Windows bitmapu znovu vytvoří.
_NOT_MEMORY = {2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E}
_SNAPSHOT_LIMIT = 64 * 1024 * 1024


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


def snapshot_clipboard():
    """Celý obsah schránky ve všech formátech (text, formátovaný text, obrázek, soubory…).
    Vrací seznam (formát, data), nebo None, když schránku nejde přečíst nebo je moc velká."""
    if not _open_clipboard():
        return None
    try:
        items, total, fmt = [], 0, 0
        while True:
            fmt = _u32.EnumClipboardFormats(fmt)
            if not fmt:
                break
            if fmt in _NOT_MEMORY:
                continue
            h = _u32.GetClipboardData(fmt)
            if not h:
                continue
            size = _k32.GlobalSize(h)
            p = _k32.GlobalLock(h)
            if not p:
                continue
            try:
                items.append((fmt, ctypes.string_at(p, size)))
            finally:
                _k32.GlobalUnlock(h)
            total += size
            if total > _SNAPSHOT_LIMIT:
                return None
        return items
    except Exception:
        log.exception("Obsah schránky nejde uložit")
        return None
    finally:
        _u32.CloseClipboard()


def restore_clipboard(items):
    """Vrátí obsah schránky uložený funkcí snapshot_clipboard."""
    if not _open_clipboard():
        return False
    try:
        _u32.EmptyClipboard()
        for fmt, data in items:
            _u32.SetClipboardData(fmt, _global(data))
        return True
    finally:
        _u32.CloseClipboard()


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


# Aplikace, ve kterých titulek okna neříká, kde přesně píšete. Název konverzace přečteme přes
# UI Automation (zpřístupnění Windows) z popisku tlačítka v záhlaví – obsah zpráv se nečte.
_CONVERSATION = {
    "claude.exe": re.compile(r"^(.+?), rename (?:session|chat|conversation)$", re.I),
}


def conversation(app, hwnd=None):
    """Název otevřené konverzace v aktivním okně (např. v aplikaci Claude), jinak None."""
    pattern = _CONVERSATION.get((app or "").lower())
    if not pattern:
        return None
    try:
        import comtypes
        import comtypes.client

        try:
            comtypes.CoInitializeEx()
        except OSError:
            pass  # vlákno už COM má
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as U

        uia = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
        root = uia.ElementFromHandle(hwnd or ctypes.windll.user32.GetForegroundWindow())
        buttons = uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_ButtonControlTypeId)
        for _ in range(2):  # první dotaz v Chromiu teprve zapne zpřístupnění
            found = root.FindAll(U.TreeScope_Descendants, buttons)
            for i in range(found.Length):
                m = pattern.match((found.GetElement(i).CurrentName or "").strip())
                if m:
                    return m.group(1).strip()[:150]
            time.sleep(0.4)
    except Exception:
        log.debug("Název konverzace nejde přečíst", exc_info=True)
    return None


_BROWSERS = {"chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "vivaldi.exe", "firefox.exe"}
def page_url(app, hwnd=None):
    """Adresa stránky v aktivním okně prohlížeče (jen adresní řádek, ne obsah stránky), jinak None."""
    app = (app or "").lower()
    if app not in _BROWSERS:
        return None
    try:
        import comtypes
        import comtypes.client

        try:
            comtypes.CoInitializeEx()
        except OSError:
            pass
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as U

        uia = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
        root = uia.ElementFromHandle(hwnd or ctypes.windll.user32.GetForegroundWindow())
        if app == "firefox.exe":
            cond = uia.CreatePropertyCondition(U.UIA_AutomationIdPropertyId, "urlbar-input")
        else:  # v Chromiu je adresní řádek první editační pole v okně (před obsahem stránky)
            cond = uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_EditControlTypeId)
        el = root.FindFirst(U.TreeScope_Descendants, cond)
        if not el:
            return None
        vp = el.GetCurrentPattern(U.UIA_ValuePatternId).QueryInterface(U.IUIAutomationValuePattern)
        return clean_url(vp.CurrentValue)
    except Exception:
        log.debug("Adresu stránky nejde přečíst", exc_info=True)
    return None


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


def ask(title, text, yes, no):
    """Systémové okénko s otázkou (nezávislé na okně aplikace). Na Windows mají tlačítka popisky Ano / Ne."""
    import ctypes

    # MB_YESNO | MB_ICONQUESTION | MB_SETFOREGROUND | MB_TOPMOST
    return ctypes.windll.user32.MessageBoxW(0, text, title, 0x4 | 0x20 | 0x10000 | 0x40000) == 6


def overlay(level_source, engine_source, on_toggle, position=None, on_moved=None):
    from overlay import Overlay

    return Overlay(level_source, engine_source, on_toggle, position, on_moved)


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
