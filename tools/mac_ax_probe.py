"""Průzkum na Macu: co aplikace (např. Slack) nabízí přes zpřístupnění macOS.

Vypíše jen popisky tlačítek, nadpisů a polí pro psaní (role a název), ne obsah zpráv.
Slouží k tomu, abychom zjistili, jestli jde ve Slacku poznat otevřené vlákno.

Použití (v Terminálu ve složce Diktovátka, Slack s otevřeným vláknem):
    .venv/bin/python tools/mac_ax_probe.py Slack
Během 5 sekund klikněte do Slacku do pole pro odpověď ve vlákně. Výsledek se uloží
do souboru ax_probe.txt, ten pošlete.
"""

import sys
import time
from pathlib import Path

from AppKit import NSWorkspace
from ApplicationServices import (AXUIElementCopyAttributeValue, AXUIElementCreateApplication,
                                 AXUIElementSetAttributeValue)

APP = sys.argv[1] if len(sys.argv) > 1 else "Slack"
ROLES = {"AXButton", "AXHeading", "AXTextArea", "AXTextField", "AXTabGroup", "AXRadioButton", "AXLink"}


def ax(el, attr):
    err, value = AXUIElementCopyAttributeValue(el, attr, None)
    return value if err == 0 else None


print(f"Za 5 sekund čtu aplikaci {APP} – klikněte do ní…")
time.sleep(5)
front = NSWorkspace.sharedWorkspace().frontmostApplication()
if (front.localizedName() or "") != APP:
    sys.exit(f"V popředí je {front.localizedName()}, ne {APP}. Zkuste to znovu.")
app = AXUIElementCreateApplication(front.processIdentifier())
AXUIElementSetAttributeValue(app, "AXManualAccessibility", True)
time.sleep(1)

lines = []
focused = ax(app, "AXFocusedUIElement")
if focused is not None:
    lines.append("FOKUS: " + " | ".join(f"{a}={ax(focused, a)!r}" for a in
                                          ("AXRole", "AXDescription", "AXTitle", "AXPlaceholderValue", "AXHelp")))
win = ax(app, "AXFocusedWindow")
lines.append(f"OKNO: {ax(win, 'AXTitle')!r}")
todo, seen = [(win, 0)], 0
while todo and seen < 8000:
    el, depth = todo.pop(0)
    seen += 1
    role = ax(el, "AXRole")
    if role in ROLES:
        label = ax(el, "AXDescription") or ax(el, "AXTitle") or ax(el, "AXPlaceholderValue") or ""
        if label:
            lines.append(f"{'  ' * min(depth, 12)}[{role}] {str(label)[:100]}")
    todo.extend((c, depth + 1) for c in list(ax(el, "AXChildren") or []))
lines.append(f"(prošlo prvků: {seen})")
out = Path(__file__).resolve().parent.parent / "ax_probe.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Hotovo, {len(lines)} řádků uloženo do {out}")
