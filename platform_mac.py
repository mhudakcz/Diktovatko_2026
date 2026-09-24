"""macOS: vše, co závisí na operačním systému.

Potřebná oprávnění (Nastavení systému → Soukromí a zabezpečení):
- Mikrofon – nahrávání,
- Zpřístupnění (Accessibility) – sledování zkratky a vložení textu (Cmd+V),
- Sledování vstupu (Input Monitoring) – sledování zkratky,
- Nahrávání obrazovky – jen pro názvy oken v historii (bez něj se uloží jen aplikace).
"""

import logging
import plistlib
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from hotkeys import HotkeyCore

log = logging.getLogger("diktovatko")
STATE_FILE = Path(__file__).resolve().parent / ".ducked.json"

NAME = "macos"
PASTE_HINT = "Cmd+V"

# Nabídka zkratek na Macu – vybrané tak, aby nepřekážely psaní ani běžným zkratkám.
PRESETS = [
    ("ctrl+cmd", "Ctrl + ⌘ Cmd"),
    ("fn", "Fn / 🌐"),
    ("right cmd", "Pravý ⌘ Cmd"),
    ("right option", "Pravý ⌥ Option"),
    ("ctrl+option", "Ctrl + Option"),
    ("ctrl+option+space", "Ctrl + Option + mezerník"),
]

# Kódy kláves macOS (kVK_*) -> názvy používané ve zkratkách.
KEYCODES = {
    54: "right cmd", 55: "left cmd", 56: "left shift", 60: "right shift", 58: "left option",
    61: "right option", 59: "left ctrl", 62: "right ctrl", 63: "fn", 57: "caps lock",
    49: "space", 36: "return", 48: "tab", 51: "delete", 53: "escape",
    122: "f1", 120: "f2", 99: "f3", 118: "f4", 96: "f5", 97: "f6", 98: "f7", 100: "f8",
    101: "f9", 109: "f10", 103: "f11", 111: "f12",
    0: "a", 11: "b", 8: "c", 2: "d", 14: "e", 3: "f", 5: "g", 4: "h", 34: "i", 38: "j", 40: "k",
    37: "l", 46: "m", 45: "n", 31: "o", 35: "p", 12: "q", 15: "r", 1: "s", 17: "t", 32: "u",
    9: "v", 13: "w", 7: "x", 16: "y", 6: "z",
    29: "0", 18: "1", 19: "2", 20: "3", 21: "4", 23: "5", 22: "6", 26: "7", 28: "8", 25: "9",
}
# Bit v příznacích události, který říká, jestli je daná modifikační klávesa dole.
MODIFIER_MASKS = {
    59: 0x1, 56: 0x2, 60: 0x4, 55: 0x8, 54: 0x10, 58: 0x20, 61: 0x40, 62: 0x2000,
    63: 0x800000, 57: 0x10000,
}


def init_process():
    try:
        from AppKit import NSApplication

        # Bez ikony v Docku, aplikace žije jen v horní liště.
        NSApplication.sharedApplication().setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory
    except Exception:
        log.exception("Nepodařilo se skrýt ikonu v Docku")
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt

        # Poprvé otevře systémový dialog pro povolení Zpřístupnění.
        if not AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}):
            log.warning("Chybí oprávnění Zpřístupnění – zkratka ani vkládání nebudou fungovat")
    except Exception:
        log.exception("Nepodařilo se ověřit oprávnění Zpřístupnění")


SOUNDS = {"start": "Tink", "stop": "Pop", "ready": "Glass", "error": "Basso"}


def beep(kind):
    subprocess.Popen(
        ["afplay", "-v", "0.5", f"/System/Library/Sounds/{SOUNDS[kind]}.aiff"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def run_on_main(fn):
    """AppKit (ikona v liště) smí měnit jen hlavní vlákno."""
    from PyObjCTools import AppHelper

    AppHelper.callAfter(fn)


def foreground_id():
    from AppKit import NSWorkspace

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.processIdentifier() if app else None


def set_clipboard(text, private=True):
    """private=True: označí obsah jako dočasný, aby ho správci schránky neukládali."""
    from AppKit import NSPasteboard, NSPasteboardTypeString

    pb = NSPasteboard.generalPasteboard()
    types = [NSPasteboardTypeString]
    if private:
        types += ["org.nspasteboard.TransientType", "org.nspasteboard.ConcealedType"]
    pb.declareTypes_owner_(types, None)
    pb.setString_forType_(text, NSPasteboardTypeString)
    for extra in types[1:]:
        pb.setString_forType_("", extra)


def get_clipboard():
    from AppKit import NSPasteboard, NSPasteboardTypeString

    return NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString)


def clipboard_seq():
    from AppKit import NSPasteboard

    return NSPasteboard.generalPasteboard().changeCount()


def wait_modifiers_released(timeout=1.0):
    import Quartz

    mask = (Quartz.kCGEventFlagMaskCommand | Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskAlternate
            | Quartz.kCGEventFlagMaskShift | Quartz.kCGEventFlagMaskSecondaryFn)
    end = time.time() + timeout
    while time.time() < end:
        if not Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateHIDSystemState) & mask:
            return
        time.sleep(0.02)


def paste():
    import Quartz

    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for down in (True, False):
        ev = Quartz.CGEventCreateKeyboardEvent(src, 9, down)  # 9 = V
        Quartz.CGEventSetFlags(ev, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.01)


def foreground_window():
    """Vrátí (název aplikace, titulek okna). Titulek vyžaduje oprávnění Nahrávání obrazovky."""
    import Quartz
    from AppKit import NSWorkspace

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return "", ""
    name, pid = app.localizedName() or "", app.processIdentifier()
    title = ""
    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    for w in windows or []:
        if w.get("kCGWindowOwnerPID") == pid and w.get("kCGWindowLayer") == 0:
            title = w.get("kCGWindowName") or ""
            break
    return name, title


def open_path(path):
    subprocess.Popen(["open", str(path)])


def focus_window(proc, title):
    if proc is None or proc.poll() is not None:
        return False
    from AppKit import NSRunningApplication

    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(proc.pid)
    if app is None:
        return False
    app.activateWithOptions_(2)  # NSApplicationActivateIgnoringOtherApps, bez oprávnění Automatizace
    return True


# --- zkratky -----------------------------------------------------------------------
class MacHotkeyManager(HotkeyCore):
    """Sleduje klávesnici přes Quartz event tap (umí i Fn a levé/pravé modifikátory)."""

    _thread = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _run(self):
        import Quartz

        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
            | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
        )
        warned = False
        while True:  # dokud uživatel nepovolí oprávnění, zkoušíme to znovu každých 5 s
            self._tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly, mask, self._callback, None,
            )
            if self._tap:
                break
            if not warned:
                log.error("Nelze sledovat klávesnici – povolte Diktovátku (Terminálu/Pythonu) "
                          "Zpřístupnění a Sledování vstupu v Nastavení systému")
                warned = True
            time.sleep(5)
        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._tap, True)
        Quartz.CFRunLoopRun()

    def _callback(self, proxy, type_, event, refcon):
        import Quartz

        if type_ in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
            Quartz.CGEventTapEnable(self._tap, True)
            return event
        code = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        name = KEYCODES.get(code, f"key{code}")
        if type_ == Quartz.kCGEventFlagsChanged:
            m = MODIFIER_MASKS.get(code)
            if m is not None:
                self.feed(name, bool(Quartz.CGEventGetFlags(event) & m))
        elif type_ == Quartz.kCGEventKeyDown:
            self.feed(name, True)
        elif type_ == Quartz.kCGEventKeyUp:
            self.feed(name, False)
        return event


def hotkey_manager(on_press, on_release, on_interrupt):
    return MacHotkeyManager(on_press, on_release, on_interrupt)


def presets():
    return PRESETS


# --- ztlumení zvuku ------------------------------------------------------------------
class MacAudioDucker:
    """macOS neumí hlasitost po aplikacích, proto dočasně ztlumí celý výstup."""

    def __init__(self, level=0.1):
        self.level = level
        self.saved = None
        self.jobs = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def duck(self):
        self.jobs.put(self._duck)

    def restore(self):
        self.jobs.put(self._restore)

    def restore_now(self, timeout=2):
        done = threading.Event()
        self.jobs.put(lambda: (self._restore(), done.set()))
        done.wait(timeout)

    def _worker(self):
        while True:
            job = self.jobs.get()
            try:
                job()
            except Exception:
                log.exception("Ztlumení zvuku selhalo")

    @staticmethod
    def _osa(script):
        return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3).stdout.strip()

    def restore_leftover(self):
        """Po pádu během nahrávání vrátí hlasitost uloženou v .ducked.json."""
        def job():
            if STATE_FILE.exists():
                try:
                    self._osa(f"set volume output volume {int(STATE_FILE.read_text())}")
                except ValueError:
                    pass
                STATE_FILE.unlink(missing_ok=True)
        self.jobs.put(job)

    def _duck(self):
        if self.saved is not None:
            return
        vol = int(self._osa("output volume of (get volume settings)") or 0)
        if vol > 0:
            self.saved = vol
            STATE_FILE.write_text(str(vol))
            self._osa(f"set volume output volume {int(vol * self.level)}")

    def _restore(self):
        if self.saved is not None:
            self._osa(f"set volume output volume {self.saved}")
            self.saved = None
        STATE_FILE.unlink(missing_ok=True)


def audio_ducker(level):
    return MacAudioDucker(level)


# --- indikátor nahrávání -----------------------------------------------------------------
def overlay(level_source, engine_source, on_toggle):
    from overlay import OverlayState, W, H, BOTTOM_MARGIN, render_pill

    class MacOverlay(OverlayState):
        """NSPanel, který nebere fokus, propouští kliknutí a je vidět na všech plochách.
        Štítek Cloud / Local se na Macu jen zobrazuje, přepíná se v menu ikony."""

        def __init__(self):
            super().__init__(level_source, engine_source, on_toggle)
            from PyObjCTools import AppHelper

            AppHelper.callAfter(self._create)

        def _create(self):
            import AppKit
            from Foundation import NSTimer

            screen = AppKit.NSScreen.mainScreen()
            self.scale = screen.backingScaleFactor()
            f = screen.visibleFrame()
            rect = AppKit.NSMakeRect(f.origin.x + (f.size.width - W) / 2, f.origin.y + BOTTOM_MARGIN, W, H)
            p = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
                AppKit.NSBackingStoreBuffered,
                False,
            )
            p.setLevel_(AppKit.NSStatusWindowLevel)
            p.setOpaque_(False)
            p.setBackgroundColor_(AppKit.NSColor.clearColor())
            p.setIgnoresMouseEvents_(True)
            p.setHasShadow_(True)
            p.setHidesOnDeactivate_(False)
            p.setCollectionBehavior_(
                AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                | AppKit.NSWindowCollectionBehaviorStationary
                | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
            )
            self.view = AppKit.NSImageView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, W, H))
            p.setContentView_(self.view)
            self.panel, self.visible = p, False
            NSTimer.scheduledTimerWithTimeInterval_repeats_block_(1 / 24, True, lambda _t: self._tick())

        def _tick(self):
            import io

            import AppKit
            from Foundation import NSData

            try:
                state = self.current()
                if state == "hidden":
                    if self.visible:
                        self.panel.orderOut_(None)
                        self.visible = False
                    return
                engine, _ = self.engine_source()
                img = render_pill(state, time.time() - self.since, self.level_source(), self.scale,
                                  self.message, transparent=True, engine=engine)
                buf = io.BytesIO()
                img.save(buf, "PNG")
                data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
                ns = AppKit.NSImage.alloc().initWithData_(data)
                ns.setSize_((W, H))
                self.view.setImage_(ns)
                if not self.visible:
                    self.panel.orderFrontRegardless()
                    self.visible = True
            except Exception:
                log.exception("Indikátor selhal")

    return MacOverlay()


# --- automatické spouštění po přihlášení (LaunchAgent) -----------------------------------------
PLIST = Path.home() / "Library/LaunchAgents/cz.diktovatko.plist"


def autostart_enabled():
    return PLIST.exists()


def set_autostart(on, app_dir):
    if not on:
        PLIST.unlink(missing_ok=True)
        return
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    with PLIST.open("wb") as f:
        plistlib.dump({
            "Label": "cz.diktovatko",
            "ProgramArguments": [sys.executable, str(app_dir / "diktovatko.py")],
            "WorkingDirectory": str(app_dir),
            "RunAtLoad": True,
            "ProcessType": "Interactive",
        }, f)
