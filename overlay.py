"""Plovoucí indikátor nahrávání ("pilulka") dole uprostřed obrazovky.

render_pill() kreslí samotnou pilulku a sdílí ho Windows i macOS.
Třída Overlay je Windows verze: běží ve vlastním vlákně s Tk, nikdy nebere
fokus a propouští kliknutí, takže text se dál vkládá do okna s kurzorem.
"""

import math
import threading
import time

from PIL import Image, ImageDraw, ImageFont

KEY = (13, 16, 23)  # průhledná barva okna na Windows (blízká barvě pilulky, aby okraje nebyly vidět)
INK = (27, 34, 48)
EDGE = (52, 61, 80)
VOICE = (240, 64, 90)
ULTRA = (141, 150, 255)
WHITE = (240, 243, 248)

W, H = 176, 44  # logická velikost (při 100 % měřítku)
SS = 3  # supersampling kvůli vyhlazeným okrajům
BOTTOM_MARGIN = 28

_fonts = {}


def _font(size):
    if size not in _fonts:
        for name in ("seguisb.ttf", "segoeui.ttf", "/System/Library/Fonts/SFNS.ttf",
                     "/System/Library/Fonts/Helvetica.ttc", "arial.ttf"):
            try:
                _fonts[size] = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
        else:
            _fonts[size] = ImageFont.load_default()
    return _fonts[size]


def render_pill(state, t, levels, scale, message="", transparent=False):
    """Vykreslí pilulku. t = sekundy od začátku stavu, levels = úrovně hlasitosti 0..1."""
    w, h = int(W * scale) * SS, int(H * scale) * SS
    if transparent:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    else:
        img = Image.new("RGB", (w, h), KEY)
    d = ImageDraw.Draw(img)
    r = h // 2
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=EDGE)
    b = max(1, int(scale * SS))
    d.rounded_rectangle((b, b, w - 1 - b, h - 1 - b), radius=r - b, fill=INK)
    s = scale * SS
    cy = h / 2
    font = _font(int(13 * s))

    if state == "recording":
        # pulzující tečka
        pr = (4.5 + 1.2 * math.sin(t * 6)) * s
        cx = 20 * s
        d.ellipse((cx - pr, cy - pr, cx + pr, cy + pr), fill=VOICE)
        # sloupečky hlasitosti
        levels = list(levels)[-18:]
        levels = [0.0] * (18 - len(levels)) + levels
        x0, bw, gap = 36 * s, 2.6 * s, 2.4 * s
        for i, lv in enumerate(levels):
            bh = (3 + min(1.0, lv) * 23) * s
            x = x0 + i * (bw + gap)
            d.rounded_rectangle((x, cy - bh / 2, x + bw, cy + bh / 2), radius=bw / 2, fill=WHITE)
        secs = int(t)
        txt = f"{secs // 60}:{secs % 60:02d}"
        tw = d.textlength(txt, font=font)
        d.text((w - 18 * s - tw, cy), txt, font=font, fill=(170, 178, 196), anchor="lm")
    elif state == "transcribing":
        # vlna, která běží zleva doprava
        n, bw, gap = 24, 2.6 * s, 2.4 * s
        x0 = (w - (n * (bw + gap) - gap)) / 2
        for i in range(n):
            phase = (t * 2.2 - i / n) % 1.0
            amp = math.exp(-((phase - 0.5) ** 2) / 0.02)
            bh = (3 + amp * 14) * s
            col = tuple(int(WHITE[k] * (1 - amp) * 0.35 + ULTRA[k] * (0.35 + 0.65 * amp)) for k in range(3))
            x = x0 + i * (bw + gap)
            d.rounded_rectangle((x, cy - bh / 2, x + bw, cy + bh / 2), radius=bw / 2, fill=col)
    elif state == "error":
        d.text((w / 2, cy), message or "Přepis se nepovedl", font=font, fill=VOICE, anchor="mm")

    return img.resize((w // SS, h // SS), Image.LANCZOS)


class OverlayState:
    """Společný stav indikátoru – volá se z libovolného vlákna."""

    def __init__(self, level_source):
        self.level_source = level_source  # funkce -> seznam posledních úrovní 0..1
        self.state = "hidden"
        self.message = ""
        self.since = time.time()

    def show(self, state, message=""):
        self.state, self.message, self.since = state, message, time.time()

    def hide(self):
        self.state = "hidden"

    def current(self):
        """Vrátí stav k vykreslení (chyba po chvíli sama zmizí)."""
        if self.state == "error" and time.time() - self.since > 2.2:
            self.state = "hidden"
        return self.state


class Overlay(OverlayState):
    """Windows: Tk okno s průhlednou barvou, bez fokusu a propouštějící kliknutí."""

    def __init__(self, level_source):
        super().__init__(level_source)
        self._ready = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(5)

    def _run(self):
        import ctypes
        import ctypes.wintypes
        import tkinter as tk

        from PIL import ImageTk

        self._ImageTk = ImageTk
        key_hex = "#%02x%02x%02x" % KEY
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=key_hex)
        self.root.attributes("-transparentcolor", key_hex)
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.w, self.h = int(W * self.scale), int(H * self.scale)

        work = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(work), 0)  # SPI_GETWORKAREA
        x = (work.left + work.right - self.w) // 2
        y = work.bottom - self.h - int(BOTTOM_MARGIN * self.scale)
        self.root.geometry(f"{self.w}x{self.h}+{x}+{y}")

        self.label = tk.Label(self.root, bg=key_hex, bd=0, highlightthickness=0)
        self.label.pack()
        self.root.update_idletasks()

        self.hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        GWL_EXSTYLE = -20
        style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        # WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_TOPMOST
        style |= 0x08000000 | 0x20 | 0x80 | 0x80000 | 0x8
        ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style)
        ctypes.windll.user32.ShowWindow(self.hwnd, 0)  # SW_HIDE
        self.visible = False
        self._ready.set()
        self._tick()
        self.root.mainloop()

    def _set_visible(self, on):
        import ctypes

        if on != self.visible:
            # SW_SHOWNOACTIVATE = 4 – zobrazí okno, ale nevezme fokus
            ctypes.windll.user32.ShowWindow(self.hwnd, 4 if on else 0)
            if on:
                ctypes.windll.user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            self.visible = on

    def _tick(self):
        try:
            state = self.current()
            if state == "hidden":
                self._set_visible(False)
            else:
                img = render_pill(state, time.time() - self.since, self.level_source(), self.scale, self.message)
                self._photo = self._ImageTk.PhotoImage(img)
                self.label.config(image=self._photo)
                self._set_visible(True)
        finally:
            self.root.after(33, self._tick)
