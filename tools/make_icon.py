"""Vytvoří ikonu okna Diktovátka (ui/icon.ico pro Windows, ui/icon.png pro Mac).

Korálové kolečko s bílým mikrofonem, stejné jako logo na webu. Spuštění:
    .venv\\Scripts\\python tools\\make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

UI = Path(__file__).resolve().parent.parent / "ui"
CORAL, WHITE = (255, 90, 110, 255), (255, 255, 255, 255)


def draw(size=1024):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 24  # kreslíme v souřadnicích 24 × 24 jako SVG logo na webu
    d.ellipse((0.4 * s, 0.4 * s, 23.6 * s, 23.6 * s), fill=CORAL)
    d.rounded_rectangle((9 * s, 5 * s, 15 * s, 15 * s), radius=3 * s, fill=WHITE)  # tělo mikrofonu
    w = round(1.9 * s)
    d.arc((7 * s, 7 * s, 17 * s, 17 * s), 0, 180, fill=WHITE, width=w)  # držák
    d.line((12 * s, 17 * s, 12 * s, 19.5 * s), fill=WHITE, width=w)  # stojánek
    r = w / 2
    for x in (7 * s + r, 17 * s - r):  # zakulacené konce držáku
        d.ellipse((x - r, 12 * s - r, x + r, 12 * s + r), fill=WHITE)
    d.ellipse((12 * s - r, 19.5 * s - r, 12 * s + r, 19.5 * s + r), fill=WHITE)
    return img


if __name__ == "__main__":
    big = draw()
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    big.resize((256, 256), Image.LANCZOS).save(UI / "icon.ico", sizes=[(n, n) for n in sizes])
    big.resize((512, 512), Image.LANCZOS).save(UI / "icon.png")
    print("ui/icon.ico a ui/icon.png hotové")
