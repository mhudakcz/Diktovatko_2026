"""Klávesové zkratky pro diktování.

HotkeyCore vyhodnocuje zkratky nezávisle na systému: dostává názvy kláves
(stisk/puštění) a hlásí stisk zkratky, její puštění a přerušení jinou klávesou.
HotkeyManager je Windows verze nad knihovnou `keyboard` (její add_hotkey nerozliší
levý a pravý Ctrl a neumí poznat, že jste jen stiskli běžnou zkratku jako Ctrl+C).
"""

import logging
import queue
import threading

log = logging.getLogger("diktovatko")

# Nabídka zkratek ve Windows – vybrané tak, aby nepřekážely psaní ani běžným zkratkám.
PRESETS = [
    ("ctrl+windows", "Ctrl + Win"),
    ("right ctrl", "Pravý Ctrl"),
    ("ctrl+alt+space", "Ctrl + Alt + mezerník"),
    ("ctrl+shift+space", "Ctrl + Shift + mezerník"),
    ("menu", "Klávesa Menu (vedle pravého Ctrl)"),
    ("scroll lock", "Scroll Lock"),
    ("pause", "Pause"),
    ("f9", "F9"),
]

# Obecné názvy, které odpovídají levé i pravé variantě klávesy.
GENERIC = {
    "ctrl": {"ctrl", "left ctrl", "right ctrl"},
    "shift": {"shift", "left shift", "right shift"},
    "alt": {"alt", "left alt"},
    "windows": {"windows", "left windows", "right windows"},
    "cmd": {"cmd", "left cmd", "right cmd"},
    "option": {"option", "left option", "right option"},
}


def parse(hotkey):
    return [p.strip().lower() for p in hotkey.split("+") if p.strip()]


def _matches(part, name):
    return name in GENERIC.get(part, {part})


class HotkeyCore:
    def __init__(self, on_press, on_release, on_interrupt):
        self.on_press = on_press  # (hotkey) – zkratka stisknuta
        self.on_release = on_release  # (hotkey) – zkratka puštěna
        self.on_interrupt = on_interrupt  # (hotkey) – během držení stisknuta jiná klávesa
        self.hotkeys = []
        self.pressed = set()
        self.active = None
        self.lock = threading.Lock()
        # Stisk, puštění a přerušení zpracovává jedno vlákno v pořadí, v jakém přišly –
        # jinak by u rychlého ťuknutí mohlo puštění předběhnout stisk a mikrofon zůstal zapnutý.
        self._events = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            fn, hk = self._events.get()
            try:
                fn(hk)
            except Exception:
                log.exception("Obsluha zkratky selhala")

    def prune_stale(self, current):
        """Háček: zahodit z `pressed` klávesy, které ve skutečnosti už nejsou dole (Windows)."""

    def set_hotkeys(self, hotkeys):
        with self.lock:
            self.hotkeys = [(h, parse(h)) for h in hotkeys if parse(h)]
            self.active = None
        self.start()

    def start(self):
        pass

    def stop(self):
        pass

    def after_press(self, parts):
        """Háček pro systémové úpravy po stisku zkratky (Windows: maska nabídky Start)."""

    def feed(self, name, down):
        name = name.lower()
        fire = None
        with self.lock:
            if down:
                repeat = name in self.pressed
                self.pressed.add(name)
                if self.active:
                    hk, parts = self.active
                    if not repeat and not any(_matches(p, name) for p in parts):
                        self.active = None
                        fire = (self.on_interrupt, hk)
                elif not repeat:
                    self.prune_stale(name)
                    for hk, parts in self.hotkeys:
                        if any(_matches(p, name) for p in parts) and all(
                            any(_matches(p, n) for n in self.pressed) for p in parts
                        ):
                            self.active = (hk, parts)
                            fire = (self.on_press, hk)
                            self.after_press(parts)
                            break
            else:
                self.pressed.discard(name)
                if self.active and any(_matches(p, name) for p in self.active[1]):
                    hk = self.active[0]
                    self.active = None
                    fire = (self.on_release, hk)
        if fire:
            self._events.put(fire)


# Windows virtual-key kódy pro ověření, že je klávesa opravdu dole (GetAsyncKeyState).
_VK = {
    "ctrl": 0x11, "left ctrl": 0xA2, "right ctrl": 0xA3, "shift": 0x10, "left shift": 0xA0, "right shift": 0xA1,
    "alt": 0x12, "left alt": 0xA4, "right alt": 0xA5, "left windows": 0x5B, "right windows": 0x5C,
    "windows": 0x5B, "menu": 0x5D, "space": 0x20, "scroll lock": 0x91, "pause": 0x13,
}


class HotkeyManager(HotkeyCore):
    """Windows: události z knihovny `keyboard`."""

    _hook = None

    def prune_stale(self, current):
        # Puštění klávesy se může ztratit (zamčení Win+L, UAC, Ctrl+Alt+Del). Bez tohohle by pak
        # "zaseklý" Win v `pressed` způsobil, že nahrávání spustí už samotný Ctrl.
        import ctypes

        state = ctypes.windll.user32.GetAsyncKeyState
        for name in list(self.pressed - {current}):
            vk = _VK.get(name)
            if vk is not None and not (state(vk) & 0x8000):
                self.pressed.discard(name)

    def start(self):
        import keyboard

        if self._hook is None:
            self._hook = keyboard.hook(self._on_event)

    def stop(self):
        import keyboard

        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None

    def after_press(self, parts):
        if "windows" in parts:
            # Po puštění Win by se otevřela nabídka Start – "neutrální" klávesa to zablokuje.
            import ctypes

            ctypes.windll.user32.keybd_event(0xE8, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xE8, 0, 2, 0)

    def _on_event(self, e):
        import keyboard

        # Uměle vložené události (maska nabídky Start) nemají scan kód.
        if not e.name or e.scan_code == 0:
            return
        self.feed(e.name, e.event_type == keyboard.KEY_DOWN)
