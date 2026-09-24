"""Plovoucí indikátor nahrávání ("pilulka") dole uprostřed obrazovky.

Běží ve vlastním vlákně s Tk. Okno nikdy nebere fokus a propouští kliknutí,
takže text se dál vkládá do okna, kde máte kurzor.
"""

import ctypes
import ctypes.wintypes
import math
import threading
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageTk

KEY = "#0d1017"  # průhledná barva okna (blízká barvě pilulky, aby okraje nebyly vidět)
INK = (27, 34, 48)
EDGE = (52, 61, 80)
VOICE = (240, 64, 90)
ULTRA = (141, 150, 255)
WHITE = (240, 243, 248)

W, H = 176, 44  # logická velikost (při 100 % měřítku)
SS = 3  # supersampling kvůli vyhlazeným okrajům


def _font(size):
    for name in ("seguisb.ttf", "segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


class Overlay:
    def __init__(self, level_source):
        self.level_source = level_source  # funkce -> seznam posledních úrovní 0..1
        self.state = "hidden"
        self.message = ""
        self.since = time.time()
        self._ready = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(5)

    # veřejné API (volat z libovolného vlákna)
    def show(self, state, message=""):
        self.state, self.message, self.since = state, message, time.time()

    def hide(self):
        self.state = "hidden"

    # --- Tk vlákno ---------------------------------------------------------------
    def _run(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.w, self.h = int(W * self.scale), int(H * self.scale)
        self.font = _font(int(13 * self.scale * SS))

        work = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(work), 0)  # SPI_GETWORKAREA
        x = (work.left + work.right - self.w) // 2
        y = work.bottom - self.h - int(28 * self.scale)
        self.root.geometry(f"{self.w}x{self.h}+{x}+{y}")

        self.label = tk.Label(self.root, bg=KEY, bd=0, highlightthickness=0)
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
        if on != self.visible:
            # SW_SHOWNOACTIVATE = 4 – zobrazí okno, ale nevezme fokus
            ctypes.windll.user32.ShowWindow(self.hwnd, 4 if on else 0)
            if on:
                ctypes.windll.user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            self.visible = on

    def _tick(self):
        try:
            state = self.state
            if state == "error" and time.time() - self.since > 2.2:
                state = self.state = "hidden"
            if state == "hidden":
                self._set_visible(False)
            else:
                self._photo = ImageTk.PhotoImage(self._render(state))
                self.label.config(image=self._photo)
                self._set_visible(True)
        finally:
            self.root.after(33, self._tick)

    def _render(self, state):
        w, h = self.w * SS, self.h * SS
        img = Image.new("RGB", (w, h), KEY)
        d = ImageDraw.Draw(img)
        r = h // 2
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=EDGE)
        b = max(1, int(self.scale * SS))
        d.rounded_rectangle((b, b, w - 1 - b, h - 1 - b), radius=r - b, fill=INK)
        t = time.time() - self.since
        s = self.scale * SS
        cy = h / 2

        if state == "recording":
            # pulzující tečka
            pr = (4.5 + 1.2 * math.sin(t * 6)) * s
            cx = 20 * s
            d.ellipse((cx - pr, cy - pr, cx + pr, cy + pr), fill=VOICE)
            # sloupečky hlasitosti
            levels = list(self.level_source())[-18:]
            levels = [0.0] * (18 - len(levels)) + levels
            x0, bw, gap = 36 * s, 2.6 * s, 2.4 * s
            for i, lv in enumerate(levels):
                bh = (3 + min(1.0, lv) * 23) * s
                x = x0 + i * (bw + gap)
                d.rounded_rectangle((x, cy - bh / 2, x + bw, cy + bh / 2), radius=bw / 2, fill=WHITE)
            secs = int(t)
            txt = f"{secs // 60}:{secs % 60:02d}"
            tw = d.textlength(txt, font=self.font)
            d.text((w - 18 * s - tw, cy), txt, font=self.font, fill=(170, 178, 196), anchor="lm")
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
            d.text((w / 2, cy), self.message or "Přepis se nepovedl", font=self.font, fill=VOICE, anchor="mm")

        return img.resize((self.w, self.h), Image.LANCZOS)
