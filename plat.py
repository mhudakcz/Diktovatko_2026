"""Vybere implementaci pro aktuální operační systém (Windows / macOS)."""

import sys

if sys.platform == "darwin":
    from platform_mac import *  # noqa: F401,F403
elif sys.platform == "win32":
    from platform_win import *  # noqa: F401,F403
else:
    raise SystemExit("Diktovátko zatím podporuje jen Windows a macOS.")
