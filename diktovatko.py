"""Diktovátko – bezplatná alternativa k Wispr Flow.

Podržíte klávesovou zkratku, mluvíte, pustíte ji a přepsaný text
se vloží tam, kde máte kurzor.
"""

import io
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import wave
import winsound
from collections import deque
from datetime import date, datetime, timedelta
from pathlib import Path

import keyboard
import numpy as np
import pyperclip
import pystray
import sounddevice as sd
from PIL import Image, ImageDraw

import history
from audio_duck import AudioDucker
from overlay import Overlay

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
LOG_PATH = APP_DIR / "diktovatko.log"
SAMPLE_RATE = 16000

DEFAULT_CONFIG = {
    # Klávesová zkratka, např. "right ctrl", "ctrl+win", "f9", "ctrl+shift+space"
    "hotkey": "right ctrl",
    # "hold" = drž a mluv, "toggle" = stiskni pro start, znovu pro stop
    "mode": "hold",
    # Jazyk přepisu ("cs", "en", ...) nebo null pro automatickou detekci
    "language": "cs",
    # Lokální model: tiny / base / small / medium / large-v3-turbo / large-v3
    "model": "large-v3-turbo",
    "beam_size": 1,
    # Nápověda pro model (styl, interpunkce, odborné výrazy, jména)
    "initial_prompt": "Dobrý den, tohle je přepis diktovaného textu s interpunkcí.",
    # Volitelné: API klíč Groq (zdarma na console.groq.com) = mnohem rychlejší přepis v cloudu.
    # Když je prázdný, přepisuje se lokálně a offline.
    "groq_api_key": "",
    "groq_model": "whisper-large-v3-turbo",
    "sounds": True,
    # Za přepsaný text přidat mezeru (hodí se při diktování po kouscích)
    "trailing_space": True,
    # Ukládat přepisy do lokální historie (history.db) včetně času a cílového okna
    "history": True,
    # Plovoucí indikátor nahrávání dole uprostřed obrazovky
    "overlay": True,
    # Během nahrávání ztlumit ostatní aplikace (Spotify, videa…) na tento podíl hlasitosti (0 = úplně)
    "duck_audio": True,
    "duck_level": 0.1,
}

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("diktovatko")


def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    cfg["groq_api_key"] = cfg["groq_api_key"] or os.environ.get("GROQ_API_KEY", "")
    return cfg


def beep(freq, ms):
    threading.Thread(target=winsound.Beep, args=(freq, ms), daemon=True).start()


def make_icon(color):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=color)
    # mikrofon
    d.rounded_rectangle((25, 14, 39, 38), radius=7, fill="white")
    d.arc((19, 24, 45, 46), start=0, end=180, fill="white", width=3)
    d.line((32, 46, 32, 52), fill="white", width=3)
    return img


ICONS = {
    "loading": make_icon("#7B8496"),
    "idle": make_icon("#1B2230"),
    "recording": make_icon("#F0405A"),
    "transcribing": make_icon("#3847F5"),
    "error": make_icon("#B42318"),
}
STATUS_TEXT = {
    "loading": "Načítám model…",
    "idle": "Připraveno",
    "recording": "Nahrávám…",
    "transcribing": "Přepisuji…",
    "error": "Chyba – viz diktovatko.log",
}


class Transcriber:
    def __init__(self, cfg):
        self.cfg = cfg
        self.model = None

    def load(self):
        if self.cfg["groq_api_key"]:
            log.info("Používám Groq API (%s)", self.cfg["groq_model"])
            return
        from faster_whisper import WhisperModel

        log.info("Načítám lokální model %s…", self.cfg["model"])
        self.model = WhisperModel(
            self.cfg["model"], device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4
        )
        log.info("Model načten")

    def transcribe(self, audio):
        if self.cfg["groq_api_key"]:
            return self._groq(audio)
        segments, _ = self.model.transcribe(
            audio,
            language=self.cfg["language"],
            beam_size=self.cfg["beam_size"],
            initial_prompt=self.cfg["initial_prompt"] or None,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return "".join(s.text for s in segments).strip()

    def _groq(self, audio):
        import httpx

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
        data = {"model": self.cfg["groq_model"], "response_format": "json", "temperature": "0"}
        if self.cfg["language"]:
            data["language"] = self.cfg["language"]
        if self.cfg["initial_prompt"]:
            data["prompt"] = self.cfg["initial_prompt"]
        r = httpx.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {self.cfg['groq_api_key']}"},
            files={"file": ("audio.wav", buf.getvalue(), "audio/wav")},
            data=data,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["text"].strip()


def has_speech(audio, threshold=0.012, min_voiced=0.25):
    """Aspoň min_voiced sekund audia (po 50ms oknech) musí být hlasitější než práh."""
    win = SAMPLE_RATE // 20
    n = len(audio) // win
    if n == 0:
        return False
    rms = np.sqrt(np.mean(audio[: n * win].reshape(n, win) ** 2, axis=1))
    return (rms > threshold).sum() * 0.05 >= min_voiced


# Věty, které si Whisper vymýšlí z ticha (naučil se je z titulků a videí).
HALLUCINATIONS = re.compile(
    r"titulky (vytvořil|připravil|pro vás)|www\.|děkuji za (pozornost|sledování)|"
    r"subtitles by|thanks for watching|amara\.org|^\W*$",
    re.IGNORECASE,
)


def is_hallucination(text):
    return bool(HALLUCINATIONS.search(text)) and len(text) < 80


def paste_text(text):
    """Vloží text do aktivního okna přes schránku a pak schránku obnoví."""
    try:
        previous = pyperclip.paste()
    except Exception:
        previous = None
    pyperclip.copy(text)
    time.sleep(0.05)
    keyboard.send("ctrl+v")
    time.sleep(0.3)
    if previous is not None:
        pyperclip.copy(previous)


class App:
    def __init__(self):
        self.cfg = load_config()
        self.transcriber = Transcriber(self.cfg)
        self.state = "loading"
        self.hotkey_down = False
        self.chunks = []
        self.levels = deque(maxlen=40)
        self.overlay = Overlay(lambda: list(self.levels)) if self.cfg["overlay"] else None
        self.ducker = AudioDucker(self.cfg["duck_level"]) if self.cfg["duck_audio"] else None
        self.stream = None
        self.lock = threading.Lock()
        self.icon = pystray.Icon(
            "diktovatko",
            ICONS["loading"],
            "Diktovátko",
            menu=pystray.Menu(
                pystray.MenuItem(lambda _: STATUS_TEXT[self.state], None, enabled=False),
                pystray.MenuItem(lambda _: f"Zkratka: {self.cfg['hotkey']} ({self.cfg['mode']})", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Zobrazit historii", self.open_history, default=True),
                pystray.MenuItem(
                    "Exportovat historii",
                    pystray.Menu(
                        pystray.MenuItem("Tento měsíc", lambda: self.export_history("month")),
                        pystray.MenuItem("Minulý měsíc", lambda: self.export_history("last_month")),
                        pystray.MenuItem("Posledních 30 dní", lambda: self.export_history("30d")),
                        pystray.MenuItem("Otevřít složku exportů", self.open_exports),
                    ),
                ),
                pystray.MenuItem("Otevřít nastavení", lambda: os.startfile(CONFIG_PATH)),
                pystray.MenuItem("Otevřít log", lambda: os.startfile(LOG_PATH)),
                pystray.MenuItem("Ukončit", self.quit),
            ),
        )

    def set_state(self, state):
        self.state = state
        self.icon.icon = ICONS[state]
        self.icon.title = f"Diktovátko – {STATUS_TEXT[state]}"
        self.icon.update_menu()
        if self.overlay:
            if state in ("recording", "transcribing"):
                self.overlay.show(state)
            else:
                self.overlay.hide()

    # --- nahrávání ---------------------------------------------------------
    def _audio_callback(self, indata, frames, time_info, status):
        mono = indata[:, 0].copy()
        self.chunks.append(mono)
        rms = float(np.sqrt(np.mean(mono**2)))
        self.levels.append(min(1.0, (rms * 14) ** 0.8))

    def start_recording(self):
        with self.lock:
            if self.state != "idle":
                return
            self.chunks = []
            self.levels.clear()
            self.started_at = datetime.now()
            try:
                self.target = history.foreground_window()
            except Exception:
                log.exception("Nepodařilo se zjistit aktivní okno")
                self.target = ("", "")
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=800,
                callback=self._audio_callback,
            )
            self.stream.start()
            if self.ducker:
                self.ducker.duck()
            self.set_state("recording")
        if self.cfg["sounds"]:
            beep(880, 60)

    def stop_recording(self):
        with self.lock:
            if self.state != "recording":
                return
            self.stream.stop()
            self.stream.close()
            self.stream = None
            if self.ducker:
                self.ducker.restore()
            self.set_state("transcribing")
        if self.cfg["sounds"]:
            beep(600, 60)
        audio = np.concatenate(self.chunks) if self.chunks else np.zeros(0, dtype=np.float32)
        threading.Thread(
            target=self._process, args=(audio, self.started_at, self.target), daemon=True
        ).start()

    def _process(self, audio, started_at, target):
        failed = False
        try:
            duration = len(audio) / SAMPLE_RATE
            if duration < 0.3:
                log.info("Příliš krátká nahrávka (%.2fs), ignoruji", duration)
                return
            if not has_speech(audio):
                log.info("V nahrávce (%.1fs) není řeč, ignoruji", duration)
                return
            t0 = time.time()
            text = self.transcriber.transcribe(audio)
            log.info("Přepis %.1fs audia za %.1fs: %r", duration, time.time() - t0, text)
            if is_hallucination(text):
                log.info("Zahazuji typickou halucinaci Whisperu: %r", text)
                return
            if text:
                paste_text(text + (" " if self.cfg["trailing_space"] else ""))
                if self.cfg["history"]:
                    engine = "groq" if self.cfg["groq_api_key"] else self.cfg["model"]
                    history.save(started_at, text, target[0], target[1], duration, engine)
        except Exception:
            log.exception("Přepis selhal")
            failed = True
            if self.cfg["sounds"]:
                beep(200, 300)
        finally:
            self.set_state("idle")
            if failed and self.overlay:
                self.overlay.show("error", "Přepis se nepovedl")

    def on_hotkey(self):
        # Držená klávesa posílá opakované stisky – reagujeme jen na první.
        if self.hotkey_down:
            return
        self.hotkey_down = True
        if self.state == "idle":
            self.start_recording()
        elif self.state == "recording" and self.cfg["mode"] == "toggle":
            self.stop_recording()
        threading.Thread(target=self._wait_for_release, daemon=True).start()

    def _wait_for_release(self):
        while keyboard.is_pressed(self.cfg["hotkey"]):
            time.sleep(0.02)
        self.hotkey_down = False
        if self.cfg["mode"] == "hold":
            self.stop_recording()

    # --- běh ---------------------------------------------------------------
    def _init(self, icon):
        icon.visible = True
        try:
            self.transcriber.load()
        except Exception:
            log.exception("Nepodařilo se načíst model")
            self.set_state("error")
            return
        keyboard.add_hotkey(self.cfg["hotkey"], self.on_hotkey, suppress=False)
        self.set_state("idle")
        if self.cfg["sounds"]:
            beep(1000, 80)
        log.info("Připraveno, zkratka: %s (%s)", self.cfg["hotkey"], self.cfg["mode"])

    def open_history(self):
        import ctypes

        # Už otevřené okno jen vyvoláme do popředí.
        hwnd = ctypes.windll.user32.FindWindowW(None, "Diktovátko – historie")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return
        # Samostatný proces, aby okno nekolidovalo s ikonou v liště.
        subprocess.Popen([sys.executable, str(APP_DIR / "history_viewer.py")], cwd=APP_DIR)

    def export_history(self, period):
        today = date.today()
        first_this = today.replace(day=1)
        if period == "month":
            start, end = first_this, today
        elif period == "last_month":
            end = first_this - timedelta(days=1)
            start = end.replace(day=1)
        else:
            start, end = today - timedelta(days=29), today
        try:
            out, n = history.export(start, end)
            log.info("Export %s–%s: %d záznamů -> %s", start, end, n, out)
            os.startfile(out)
        except Exception:
            log.exception("Export selhal")

    def open_exports(self):
        history.EXPORT_DIR.mkdir(exist_ok=True)
        os.startfile(history.EXPORT_DIR)

    def quit(self):
        if self.ducker:
            self.ducker.restore_now()
        keyboard.unhook_all()
        self.icon.stop()

    def run(self):
        self.icon.run(setup=self._init)


if __name__ == "__main__":
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # ostrý indikátor na HiDPI displejích
    except Exception:
        pass
    try:
        App().run()
    except Exception:
        log.exception("Neočekávaná chyba")
        sys.exit(1)
