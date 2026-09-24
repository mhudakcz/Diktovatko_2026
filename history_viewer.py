"""Okno s historií diktování (pywebview + HTML)."""

import json
import os
from datetime import date, timedelta

import pyperclip
import webview

import history

APP_DIR = history.APP_DIR
WINDOW_TITLE = "Diktovátko – historie"


def period_range(name):
    today = date.today()
    first_this = today.replace(day=1)
    if name == "today":
        return today, today
    if name == "7d":
        return today - timedelta(days=6), today
    if name == "month":
        return first_this, today
    if name == "last_month":
        end = first_this - timedelta(days=1)
        return end.replace(day=1), end
    if name == "90d":
        return today - timedelta(days=89), today
    return date(2000, 1, 1), today


class Api:
    def entries(self, period, search):
        start, end = period_range(period)
        return history.fetch_dicts(start, end, search.strip() or None)

    def copy(self, text):
        pyperclip.copy(text)
        return True

    def export(self, period, search):
        start, end = period_range(period)
        out, n = history.export(start, end, search=search.strip() or None)
        os.startfile(out)
        return n

    def settings(self):
        try:
            cfg = json.loads((APP_DIR / "config.json").read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
        return {"hotkey": cfg.get("hotkey", "right ctrl")}


if __name__ == "__main__":
    webview.create_window(
        WINDOW_TITLE,
        url=str(APP_DIR / "ui" / "history.html"),
        js_api=Api(),
        width=1120,
        height=700,
        min_size=(760, 520),
        background_color="#EEF1F5",
    )
    webview.start()
