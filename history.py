"""Lokální historie diktování (SQLite) a export.

Použití z příkazové řádky:
    python history.py                          # posledních 30 dní -> Markdown
    python history.py --from 2026-09-01 --to 2026-09-30
    python history.py --month 2026-09 --format csv
    python history.py --search "faktura"
"""

import argparse
import csv
import ctypes
import ctypes.wintypes as wt
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "history.db"
EXPORT_DIR = APP_DIR / "exporty"

SCHEMA = """
CREATE TABLE IF NOT EXISTS dictations (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,            -- ISO čas začátku nahrávání (lokální)
    text TEXT NOT NULL,
    app TEXT,                    -- např. chrome.exe, slack.exe
    window_title TEXT,           -- titulek okna (záložka, konverzace, dokument)
    audio_seconds REAL,
    engine TEXT
);
CREATE INDEX IF NOT EXISTS idx_dictations_ts ON dictations(ts);
"""


def connect():
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    return con


def save(ts, text, app, window_title, audio_seconds, engine):
    with connect() as con:
        con.execute(
            "INSERT INTO dictations (ts, text, app, window_title, audio_seconds, engine) VALUES (?,?,?,?,?,?)",
            (ts.isoformat(timespec="seconds"), text, app, window_title, round(audio_seconds, 1), engine),
        )


# --- informace o aktivním okně ----------------------------------------------
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32


def foreground_window():
    """Vrátí (název procesu, titulek okna) aktuálně aktivního okna."""
    hwnd = _user32.GetForegroundWindow()
    length = _user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    pid = wt.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    app = ""
    handle = _kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if handle:
        size = wt.DWORD(1024)
        path = ctypes.create_unicode_buffer(size.value)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            app = Path(path.value).name
        _kernel32.CloseHandle(handle)
    return app, title


# --- export -------------------------------------------------------------------
def fetch(date_from, date_to, search=None):
    sql = "SELECT ts, app, window_title, text FROM dictations WHERE ts >= ? AND ts < ?"
    params = [date_from.isoformat(), (date_to + timedelta(days=1)).isoformat()]
    if search:
        sql += " AND (text LIKE ? OR window_title LIKE ?)"
        params += [f"%{search}%"] * 2
    with connect() as con:
        return con.execute(sql + " ORDER BY ts", params).fetchall()


def fetch_dicts(date_from, date_to, search=None):
    sql = "SELECT id, ts, app, window_title, text, audio_seconds FROM dictations WHERE ts >= ? AND ts < ?"
    params = [date_from.isoformat(), (date_to + timedelta(days=1)).isoformat()]
    if search:
        sql += " AND (text LIKE ? OR window_title LIKE ?)"
        params += [f"%{search}%"] * 2
    with connect() as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(sql + " ORDER BY ts DESC", params)]


def export(date_from, date_to, fmt="md", search=None):
    rows = fetch(date_from, date_to, search)
    EXPORT_DIR.mkdir(exist_ok=True)
    out = EXPORT_DIR / f"diktovani_{date_from}_{date_to}.{fmt}"
    if fmt == "csv":
        with out.open("w", newline="", encoding="utf-8-sig") as f:  # BOM kvůli Excelu
            w = csv.writer(f, delimiter=";")
            w.writerow(["čas", "aplikace", "okno", "text"])
            w.writerows(rows)
    else:
        lines = [f"# Diktování {date_from} – {date_to}", "", f"Záznamů: {len(rows)}", ""]
        current_day = None
        for ts, app, title, text in rows:
            day, clock = ts[:10], ts[11:16]
            if day != current_day:
                lines += ["", f"## {day}", ""]
                current_day = day
            lines.append(f"- **{clock}** · `{app}` · {title}")
            lines.append(f"  > {text}")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out, len(rows)


def main():
    p = argparse.ArgumentParser(description="Export historie diktování")
    p.add_argument("--from", dest="date_from", type=date.fromisoformat)
    p.add_argument("--to", dest="date_to", type=date.fromisoformat)
    p.add_argument("--month", help="např. 2026-09")
    p.add_argument("--format", choices=["md", "csv"], default="md")
    p.add_argument("--search", help="hledat v textu nebo titulku okna")
    a = p.parse_args()

    if a.month:
        start = date.fromisoformat(a.month + "-01")
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    else:
        end = a.date_to or date.today()
        start = a.date_from or end - timedelta(days=29)
    out, n = export(start, end, a.format, a.search)
    print(f"Exportováno {n} záznamů do {out}")


if __name__ == "__main__":
    main()
