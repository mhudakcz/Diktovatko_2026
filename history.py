"""Lokální historie diktování (SQLite), statistiky a export.

Použití z příkazové řádky:
    python history.py                          # posledních 30 dní -> Markdown
    python history.py --from 2026-09-01 --to 2026-09-30
    python history.py --month 2026-09 --format csv
    python history.py --search "faktura"
"""

import argparse
import csv
import os
import sqlite3
import sys
import threading
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "history.db"
EXPORT_DIR = APP_DIR / "exporty"
EXPORT_FORMATS = ("md", "csv")
MAX_ENTRIES = 2000  # nejvýš tolik záznamů naráz do okna historie

SCHEMA = """
CREATE TABLE IF NOT EXISTS dictations (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,            -- ISO čas začátku nahrávání (lokální)
    text TEXT NOT NULL,
    app TEXT,                    -- např. chrome.exe, slack.exe (na Macu název aplikace)
    window_title TEXT,           -- titulek okna (záložka, konverzace, dokument)
    audio_seconds REAL,
    engine TEXT,
    words INTEGER                -- počet slov, ať statistiky nemusí text znovu počítat
);
CREATE INDEX IF NOT EXISTS idx_dictations_ts ON dictations(ts);
"""

_ready = set()
_ready_lock = threading.Lock()


def _init(con):
    # Musí být jako první, mimo transakci. WAL: tray aplikace i okno historie čtou a zapisují souběžně.
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(dictations)")}
    if "words" not in cols:  # starší databáze bez sloupce words
        con.execute("ALTER TABLE dictations ADD COLUMN words INTEGER")
    todo = con.execute("SELECT id, text FROM dictations WHERE words IS NULL").fetchall()
    con.executemany("UPDATE dictations SET words = ? WHERE id = ?", [(_words(t), i) for i, t in todo])
    con.commit()
    if sys.platform != "win32":
        os.chmod(DB_PATH, 0o600)


@contextmanager
def connect():
    """Otevře databázi (schéma se zakládá jen jednou za běh) a po použití ji zavře."""
    with closing(sqlite3.connect(DB_PATH, timeout=5)) as con:
        con.create_function("fold", 1, lambda s: s.casefold() if s else "", deterministic=True)
        key = str(DB_PATH)
        if key not in _ready:
            with _ready_lock:
                if key not in _ready:
                    _init(con)
                    _ready.add(key)
        with con:
            yield con


def _words(text):
    return len(text.split())


def save(ts, text, app, window_title, audio_seconds, engine):
    with connect() as con:
        con.execute(
            "INSERT INTO dictations (ts, text, app, window_title, audio_seconds, engine, words) VALUES (?,?,?,?,?,?,?)",
            (ts.isoformat(timespec="seconds"), text, app, window_title, round(audio_seconds, 1), engine, _words(text)),
        )


def delete(ids):
    ids = [int(i) for i in ids]
    if not ids:
        return 0
    with connect() as con:
        cur = con.execute(f"DELETE FROM dictations WHERE id IN ({','.join('?' * len(ids))})", ids)
        return cur.rowcount


def clear_all():
    with connect() as con:
        n = con.execute("DELETE FROM dictations").rowcount
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.execute("VACUUM")  # smazaný text nezůstane ve volných stránkách souboru
    return n


def prune(keep_days):
    """Smaže záznamy starší než keep_days dní (0 = nechat vše)."""
    if not keep_days:
        return 0
    cutoff = (date.today() - timedelta(days=int(keep_days))).isoformat()
    with connect() as con:
        return con.execute("DELETE FROM dictations WHERE ts < ?", (cutoff,)).rowcount


# --- období ------------------------------------------------------------------------
PERIODS = [
    ("today", "Dnes"),
    ("7d", "Posledních 7 dní"),
    ("10d", "Posledních 10 dní"),
    ("14d", "Posledních 14 dní"),
    ("20d", "Posledních 20 dní"),
    ("30d", "Posledních 30 dní"),
    ("month", "Tento měsíc"),
    ("last_month", "Minulý měsíc"),
    ("90d", "Posledních 90 dní"),
    ("all", "Vše"),
]


def period_range(key, today=None):
    """Vrátí (od, do) pro klíč období nebo vlastní rozsah ve tvaru 'YYYY-MM-DD|YYYY-MM-DD'."""
    today = today or date.today()
    if "|" in key:
        a, b = key.split("|")
        return date.fromisoformat(a), date.fromisoformat(b)
    if key.endswith("d") and key[:-1].isdigit():
        return today - timedelta(days=int(key[:-1]) - 1), today
    first_this = today.replace(day=1)
    if key == "today":
        return today, today
    if key == "month":
        return first_this, today
    if key == "last_month":
        end = first_this - timedelta(days=1)
        return end.replace(day=1), end
    return date(2000, 1, 1), today


def _query(cols, date_from, date_to, search=None, order="ASC", limit=None):
    sql = f"SELECT {cols} FROM dictations WHERE ts >= ? AND ts < ?"
    params = [date_from.isoformat(), (date_to + timedelta(days=1)).isoformat()]
    if search:
        # instr + fold: hledání bez ohledu na velikost písmen i u diakritiky, bez zástupných znaků LIKE
        sql += " AND (instr(fold(text), ?) > 0 OR instr(fold(window_title), ?) > 0)"
        params += [search.casefold()] * 2
    sql += f" ORDER BY ts {order}"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return sql, params


def fetch(date_from, date_to, search=None):
    sql, params = _query("ts, app, window_title, text", date_from, date_to, search)
    with connect() as con:
        return con.execute(sql, params).fetchall()


def fetch_dicts(date_from, date_to, search=None):
    sql, params = _query("id, ts, app, window_title, text, audio_seconds", date_from, date_to, search, "DESC", MAX_ENTRIES)
    with connect() as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(sql, params)]


# --- statistiky (počítá je databáze, ne Python nad celou historií) --------------------------
TYPING_WPM = 40  # průměrná rychlost psaní na klávesnici, pro odhad ušetřeného času


def stats(today=None):
    today = today or date.today()
    with connect() as con:
        def summary(since):
            where, params = ("WHERE ts >= ?", [since.isoformat()]) if since else ("", [])
            count, words, chars, secs = con.execute(
                f"SELECT COUNT(*), COALESCE(SUM(words),0), COALESCE(SUM(LENGTH(text)),0), COALESCE(SUM(audio_seconds),0) "
                f"FROM dictations {where}", params,
            ).fetchone()
            return {
                "count": count,
                "words": words,
                "chars": chars,
                "audio_seconds": round(secs, 1),
                "saved_minutes": round(max(0.0, words / TYPING_WPM - secs / 60), 1),
            }

        periods = {
            "today": summary(today),
            "7d": summary(today - timedelta(days=6)),
            "30d": summary(today - timedelta(days=29)),
            "all": summary(None),
        }
        start = today - timedelta(days=29)
        per_day = dict(con.execute(
            "SELECT substr(ts,1,10), SUM(words) FROM dictations WHERE ts >= ? GROUP BY 1", (start.isoformat(),)
        ).fetchall())
        apps = [
            {"app": a or "", "count": c, "words": w}
            for a, c, w in con.execute(
                "SELECT app, COUNT(*), SUM(words) FROM dictations GROUP BY app ORDER BY 3 DESC LIMIT 8"
            )
        ]
        active_days = {r[0] for r in con.execute("SELECT DISTINCT substr(ts,1,10) FROM dictations")}
        first = con.execute("SELECT MIN(ts) FROM dictations").fetchone()[0]

    streak, d = 0, today
    while d.isoformat() in active_days:
        streak += 1
        d -= timedelta(days=1)
    total = periods["all"]
    days = [(start + timedelta(days=i)).isoformat() for i in range(30)]
    return {
        "periods": periods,
        "daily": [{"date": k, "words": per_day.get(k, 0)} for k in days],
        "apps": apps,
        "first_use": first[:10] if first else None,
        "active_days": len(active_days),
        "streak": streak,
        "wpm": round(total["words"] / (total["audio_seconds"] / 60)) if total["audio_seconds"] > 5 else None,
        "typing_wpm": TYPING_WPM,
    }


# --- export ------------------------------------------------------------------------
def _csv_safe(value):
    """Titulek okna nastavuje libovolná webová stránka – buňka začínající =, +, -, @ by se v Excelu spustila jako vzorec."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def export(date_from, date_to, fmt="md", search=None, lang=None):
    from i18n import t

    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"Nepodporovaný formát exportu: {fmt!r}")
    rows = fetch(date_from, date_to, search)
    EXPORT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")  # další export stejného období nepřepíše ten předchozí
    out = EXPORT_DIR / f"diktovani_{date_from}_{date_to}_{stamp}.{fmt}"
    if fmt == "csv":
        with out.open("w", newline="", encoding="utf-8-sig") as f:  # BOM kvůli Excelu
            w = csv.writer(f, delimiter=";")
            w.writerow(t("export.csv", lang))
            w.writerows([[_csv_safe(c) for c in row] for row in rows])
    else:
        lines = [
            "# " + t("export.title", lang, start=date_from, end=date_to),
            "",
            t("export.count", lang, n=len(rows)),
            "",
        ]
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
    p.add_argument("--format", choices=EXPORT_FORMATS, default="md")
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
