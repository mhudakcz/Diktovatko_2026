"""Úprava adresy stránky pro historii (společné pro Windows i macOS)."""

import re

URL_RE = re.compile(r"^(?:https?://)?[\w.-]+\.[a-z]{2,}(?::\d+)?(?:[/#].*)?$", re.I)


def clean_url(value):
    """Adresa z prohlížeče: doplní https://, zahodí parametry za ? (mohou v nich být tokeny)."""
    value = (value or "").strip()
    if not value or " " in value or not URL_RE.match(value):
        return None
    if not value.lower().startswith(("http://", "https://")):
        value = "https://" + value
    base, _, frag = value.partition("#")
    base = base.split("?", 1)[0]
    if frag and "=" not in frag:  # kotva typu #inbox/… pomáhá (Gmail), kotvy s parametry zahodíme
        base += "#" + frag
    return base[:500]
