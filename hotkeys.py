"""Klávesové zkratky pro diktování.

HotkeyCore vyhodnocuje zkratky nezávisle na systému: dostává názvy kláves
(stisk/puštění) a hlásí stisk zkratky, její puštění a přerušení jinou klávesou.
HotkeyManager je Windows verze nad knihovnou `keyboard` (její add_hotkey nerozliší
levý a pravý Ctrl a neumí poznat, že jste jen stiskli běžnou zkratku jako Ctrl+C).
"""

import threading

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
            threading.Thread(target=fire[0], args=(fire[1],), daemon=True).start()


class HotkeyManager(HotkeyCore):
    """Windows: události z knihovny `keyboard`."""

    _hook = None

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
