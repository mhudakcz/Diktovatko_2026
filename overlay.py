"""Plovoucí indikátor nahrávání ("pilulka") dole uprostřed obrazovky.

render_pill() kreslí samotnou pilulku a sdílí ho Windows i macOS.
Třída Overlay je Windows verze: běží ve vlastním vlákně s Tk a nikdy nebere
fokus, takže text se dál vkládá do okna s kurzorem. Kliknutí na štítek
Cloud · fast / Local · slow vpravo přepne způsob přepisu, za zbytek jde indikátor
přetáhnout jinam (dvojklik ho vrátí dole doprostřed). Je napůl průhledný.
"""

import logging
import math
import threading
import time

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("diktovatko")

KEY = (13, 16, 23)  # průhledná barva okna na Windows (blízká barvě pilulky, aby okraje nebyly vidět)
INK = (27, 34, 48)
EDGE = (52, 61, 80)
VOICE = (240, 64, 90)
ULTRA = (141, 150, 255)
WHITE = (240, 243, 248)
MUTED = (170, 178, 196)
OFFLINE = (94, 214, 160)

W, H = 280, 44  # logická velikost (při 100 % měřítku)
BADGE_X0, BADGE_X1 = 166, 272  # štítek Cloud / Local (logické souřadnice)
SS = 2  # supersampling kvůli vyhlazeným okrajům (2× stačí, 3× zbytečně zatěžovalo CPU)
FRAME_MS = 42  # ~24 snímků za sekundu
BOTTOM_MARGIN = 28
ALPHA = 0.7  # krytí indikátoru, ať je vidět, co je pod ním (pod myší je plně vidět)
DRAG_PX = 4  # posun myši, od kterého je kliknutí přetažení

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


def _bolt(d, x, cy, s, col):
    """Blesk (fast), 10 × 14 logických bodů, x = levý okraj."""
    pts = [(6, 0), (0, 8), (4.5, 8), (3.5, 14), (10, 5.5), (5.5, 5.5), (6.5, 0)]
    d.polygon([(x + px * s, cy - 7 * s + py * s) for px, py in pts], fill=col)


def _snail(d, x, cy, s, col):
    """Šnek (slow), 15 × 12 logických bodů, x = levý okraj."""
    w = max(1, round(1.5 * s))
    # tělo, hlavička a tykadla s tečkami
    base = cy + 5 * s
    d.rounded_rectangle((x, base - 2.4 * s, x + 13.5 * s, base + 0.4 * s), radius=1.4 * s, fill=col)
    hx, hy, hr = x + 13 * s, base - 3.2 * s, 2 * s
    d.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=col)
    for tx in (11.6, 15):
        d.line((hx, hy, x + tx * s, base - 8.6 * s), fill=col, width=w)
        d.ellipse((x + tx * s - 0.9 * s, base - 9.5 * s, x + tx * s + 0.9 * s, base - 7.7 * s), fill=col)
    # ulita se spirálou
    cx, sy, r = x + 5.4 * s, cy - 0.6 * s, 5 * s
    d.ellipse((cx - r, sy - r, cx + r, sy + r), outline=col, width=w)
    r2 = 2.4 * s
    d.arc((cx - r2, sy - r2, cx + r2, sy + r2), 90, 400, fill=col, width=w)


def _badge(d, engine, clickable, s, cy):
    """Štítek se způsobem přepisu: engine = "groq" (⚡ Cloud · fast) / "offline" (šnek Local · slow)."""
    col = ULTRA if engine == "groq" else OFFLINE
    x0, x1, bh = BADGE_X0 * s, BADGE_X1 * s, 13 * s
    fill = tuple(int(INK[k] * 0.78 + col[k] * 0.22) for k in range(3))
    d.rounded_rectangle((x0, cy - bh, x1, cy + bh), radius=bh, fill=fill,
                        outline=col if clickable else None, width=max(1, int(s)))
    # piktogram + "Cloud · fast" / "Local · slow": hlavní slovo bíle, rychlost v barvě štítku
    main, speed = ("Cloud", " · fast") if engine == "groq" else ("Local", " · slow")
    icon, iw = (_bolt, 10) if engine == "groq" else (_snail, 15)
    f1, f2 = _font(int(12 * s)), _font(int(11 * s))
    gap = 5 * s
    tw = iw * s + gap + d.textlength(main, font=f1) + d.textlength(speed, font=f2)
    x = (x0 + x1 - tw) / 2
    accent = col if clickable else MUTED
    icon(d, x, cy, s, accent)
    x += iw * s + gap
    d.text((x, cy), main, font=f1, fill=WHITE if clickable else MUTED, anchor="lm")
    d.text((x + d.textlength(main, font=f1), cy), speed, font=f2, fill=accent, anchor="lm")


def render_pill(state, t, levels, scale, message="", transparent=False, engine=None, clickable=False):
    """Vykreslí pilulku. t = sekundy od začátku stavu, levels = úrovně hlasitosti 0..1,
    engine = štítek vpravo ("groq" / "offline" / None), clickable = štítek jde přepnout."""
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
        right = (BADGE_X0 - 10) * s if engine else w - 18 * s
        d.text((right, cy), txt, font=font, fill=MUTED, anchor="rm")
    elif state == "transcribing":
        # vlna, která běží zleva doprava
        n, bw, gap = (20 if engine else 24), 2.6 * s, 2.4 * s
        area = BADGE_X0 * s if engine else w
        x0 = (area - (n * (bw + gap) - gap)) / 2
        for i in range(n):
            phase = (t * 2.2 - i / n) % 1.0
            amp = math.exp(-((phase - 0.5) ** 2) / 0.02)
            bh = (3 + amp * 14) * s
            col = tuple(int(WHITE[k] * (1 - amp) * 0.35 + ULTRA[k] * (0.35 + 0.65 * amp)) for k in range(3))
            x = x0 + i * (bw + gap)
            d.rounded_rectangle((x, cy - bh / 2, x + bw, cy + bh / 2), radius=bw / 2, fill=col)
    elif state == "error":
        d.text((w / 2, cy), message or "Přepis se nepovedl", font=font, fill=VOICE, anchor="mm")
        engine = None

    if engine and state in ("recording", "transcribing"):
        _badge(d, engine, clickable and state == "recording", s, cy)

    return img.resize((w // SS, h // SS), Image.LANCZOS)


class OverlayState:
    """Společný stav indikátoru – volá se z libovolného vlákna."""

    def __init__(self, level_source, engine_source=lambda: (None, False), on_toggle=None):
        self.level_source = level_source  # funkce -> seznam posledních úrovní 0..1
        self.engine_source = engine_source  # funkce -> ("groq" / "offline" / None, jde přepnout)
        self.on_toggle = on_toggle  # kliknutí na štítek
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
    """Windows: Tk okno s průhlednou barvou, které nebere fokus ani při kliknutí."""

    def __init__(self, level_source, engine_source=lambda: (None, False), on_toggle=None,
                 position=None, on_moved=None):
        super().__init__(level_source, engine_source, on_toggle)
        self.position = position  # [x, y] levého horního rohu, None = dole uprostřed
        self.on_moved = on_moved  # po přetažení: on_moved([x, y]), dvojklik: on_moved(None)
        self._drag = None
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
        self.root.attributes("-alpha", ALPHA)
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.w, self.h = int(W * self.scale), int(H * self.scale)

        self._place(self.position)

        self.label = tk.Label(self.root, bg=key_hex, bd=0, highlightthickness=0)
        self.label.pack()
        self.label.bind("<ButtonPress-1>", self._press)
        self.label.bind("<B1-Motion>", self._drag_move)
        self.label.bind("<ButtonRelease-1>", self._release)
        self.label.bind("<Double-Button-1>", self._reset_position)
        self.label.bind("<Motion>", self._motion)
        self.label.bind("<Enter>", lambda _e: self.root.attributes("-alpha", 1.0))
        self.label.bind("<Leave>", lambda _e: self._drag or self.root.attributes("-alpha", ALPHA))
        self.root.update_idletasks()

        self.hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        GWL_EXSTYLE = -20
        style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_TOPMOST
        # (bez WS_EX_TRANSPARENT, aby šlo kliknout na štítek; fokus okno i tak nevezme)
        style |= 0x08000000 | 0x80 | 0x80000 | 0x8
        ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style)
        ctypes.windll.user32.ShowWindow(self.hwnd, 0)  # SW_HIDE
        self.visible = False
        self._ready.set()
        self._tick()
        self.root.mainloop()

    def _on_badge(self, x):
        engine, clickable = self.engine_source()
        return bool(engine and clickable and self.current() == "recording"
                    and BADGE_X0 <= x / self.scale <= BADGE_X1)

    def _default_pos(self):
        import ctypes
        import ctypes.wintypes

        work = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(work), 0)  # SPI_GETWORKAREA
        return (work.left + work.right - self.w) // 2, work.bottom - self.h - int(BOTTOM_MARGIN * self.scale)

    def _place(self, pos):
        """Umístí okno na pos, nebo dole doprostřed, když pos chybí či je mimo všechny monitory."""
        import ctypes

        m = ctypes.windll.user32.GetSystemMetrics
        vx, vy, vw, vh = m(76), m(77), m(78), m(79)  # virtuální plocha přes všechny monitory
        if pos and vx <= pos[0] <= vx + vw - self.w // 2 and vy <= pos[1] <= vy + vh - self.h // 2:
            x, y = pos
        else:
            x, y = self._default_pos()
        self.root.geometry(f"{self.w}x{self.h}+{x}+{y}")

    def _press(self, e):
        self._drag = {"x": e.x_root, "y": e.y_root, "wx": self.root.winfo_x(), "wy": self.root.winfo_y(),
                      "moved": False, "badge": self._on_badge(e.x)}

    def _drag_move(self, e):
        d = self._drag
        if not d:
            return
        dx, dy = e.x_root - d["x"], e.y_root - d["y"]
        if not d["moved"] and abs(dx) < DRAG_PX and abs(dy) < DRAG_PX:
            return
        d["moved"] = True
        self.label.config(cursor="fleur")
        self.root.geometry(f"+{d['wx'] + dx}+{d['wy'] + dy}")

    def _release(self, e):
        d, self._drag = self._drag, None
        if not d:
            return
        if d["moved"]:
            self.position = [self.root.winfo_x(), self.root.winfo_y()]
            if self.on_moved:
                threading.Thread(target=self.on_moved, args=(self.position,), daemon=True).start()
        elif d["badge"] and self.on_toggle:
            threading.Thread(target=self.on_toggle, daemon=True).start()
        self._motion(e)

    def _reset_position(self, e):
        """Dvojklik mimo štítek vrátí indikátor dole doprostřed."""
        if self._on_badge(e.x):
            return
        self.position = None
        self._place(None)
        if self.on_moved:
            threading.Thread(target=self.on_moved, args=(None,), daemon=True).start()

    def _motion(self, e):
        if self._drag and self._drag["moved"]:
            return
        cur = "hand2" if self._on_badge(e.x) else "fleur"
        if self.label.cget("cursor") != cur:
            self.label.config(cursor=cur)

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
                engine, clickable = self.engine_source()
                img = render_pill(state, time.time() - self.since, self.level_source(), self.scale, self.message,
                                  engine=engine, clickable=clickable)
                self._photo = self._ImageTk.PhotoImage(img)
                self.label.config(image=self._photo)
                self._set_visible(True)
        except Exception:
            log.exception("Indikátor selhal")
        finally:
            self.root.after(FRAME_MS, self._tick)
