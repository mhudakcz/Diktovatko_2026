"""Diktovátko – bezplatná alternativa k Wispr Flow.

Podržíte klávesovou zkratku, mluvíte, pustíte ji a přepsaný text
se vloží tam, kde máte kurzor.
"""

import io
import logging
import os
import re
import subprocess
import sys
import threading
import time
import wave
from collections import deque
from datetime import datetime

import numpy as np
import pyperclip
import pystray
import sounddevice as sd
from PIL import Image, ImageDraw

import config
import history
import plat
from version import VERSION

APP_DIR = config.APP_DIR
LOG_PATH = APP_DIR / "diktovatko.log"
UI_REQUEST = APP_DIR / ".ui_request"
WINDOW_TITLE = "Diktovátko"
SAMPLE_RATE = 16000

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("diktovatko")


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
HOTKEY_LABELS = dict(plat.presets())


class Transcriber:
    def __init__(self, cfg):
        self.cfg = cfg
        self.model = None
        self.model_name = None

    def load(self):
        if config.groq_key(self.cfg):
            log.info("Používám Groq API (%s)", self.cfg["groq_model"])
            return
        if self.model is not None and self.model_name == self.cfg["model"]:
            return
        from faster_whisper import WhisperModel

        log.info("Načítám lokální model %s…", self.cfg["model"])
        self.model = WhisperModel(
            self.cfg["model"], device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4
        )
        self.model_name = self.cfg["model"]
        log.info("Model načten")

    def transcribe(self, audio):
        if config.groq_key(self.cfg):
            # Groq přijme soubor do 25 MB (~13 min WAV), delší nahrávku dělíme v tichém místě.
            return " ".join(t for t in (self._groq(part) for part in split_audio(audio)) if t)
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
            headers={"Authorization": f"Bearer {config.groq_key(self.cfg)}"},
            files={"file": ("audio.wav", buf.getvalue(), "audio/wav")},
            data=data,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["text"].strip()


def split_audio(audio, max_seconds=600, search_seconds=60):
    """Rozdělí dlouhou nahrávku na části do max_seconds, řez vede v nejtišším místě."""
    parts, win = [], SAMPLE_RATE // 20
    max_len = max_seconds * SAMPLE_RATE
    while len(audio) > max_len:
        lo = (max_seconds - search_seconds) * SAMPLE_RATE
        region = audio[lo:max_len]
        n = len(region) // win
        energy = np.mean(region[: n * win].reshape(n, win) ** 2, axis=1)
        cut = lo + int(np.argmin(energy)) * win + win // 2
        parts.append(audio[:cut])
        audio = audio[cut:]
    parts.append(audio)
    return parts


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
    plat.paste()
    time.sleep(0.3)
    if previous is not None:
        pyperclip.copy(previous)


def hotkey_label(hk):
    return HOTKEY_LABELS.get(hk, hk)


class App:
    def __init__(self):
        self.cfg = config.load_config()
        self.config_mtime = config.CONFIG_PATH.stat().st_mtime
        self.transcriber = Transcriber(self.cfg)
        self.state = "loading"
        self.chunks = []
        self.levels = deque(maxlen=40)
        self.overlay = None
        self.ducker = None
        self._apply_extras()
        self.stream = None
        self.window_proc = None
        self.lock = threading.Lock()
        self.hotkeys = plat.hotkey_manager(self.on_hotkey_press, self.on_hotkey_release, self.on_hotkey_interrupt)

        export_items = [
            pystray.MenuItem(label, (lambda k: lambda: self.export_history(k))(key))
            for key, label in history.PERIODS
            if key != "today"
        ]
        export_items += [pystray.Menu.SEPARATOR, pystray.MenuItem("Otevřít složku exportů", self.open_exports)]
        self.icon = pystray.Icon(
            "diktovatko",
            ICONS["loading"],
            "Diktovátko",
            menu=pystray.Menu(
                pystray.MenuItem(f"Diktovátko {VERSION}", None, enabled=False),
                pystray.MenuItem(lambda _: STATUS_TEXT[self.state], None, enabled=False),
                pystray.MenuItem(
                    lambda _: "Zkratka: " + ", ".join(hotkey_label(h) for h in self.cfg["hotkeys"]),
                    None,
                    enabled=False,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Historie", lambda: self.open_window("history"), default=True),
                pystray.MenuItem("Statistiky", lambda: self.open_window("stats")),
                pystray.MenuItem("Nastavení", lambda: self.open_window("settings")),
                pystray.MenuItem("Exportovat historii", pystray.Menu(*export_items)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Otevřít log", lambda: plat.open_path(LOG_PATH)),
                pystray.MenuItem("Ukončit", self.quit),
            ),
        )

    def _apply_extras(self):
        if self.cfg["overlay"] and self.overlay is None:
            self.overlay = plat.overlay(lambda: list(self.levels))
        elif not self.cfg["overlay"] and self.overlay is not None:
            self.overlay.hide()
            self.overlay = None
        if self.cfg["duck_audio"]:
            if self.ducker is None:
                self.ducker = plat.audio_ducker(self.cfg["duck_level"])
            self.ducker.level = self.cfg["duck_level"]
        else:
            self.ducker = None

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
                self.target = plat.foreground_window()
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
            plat.beep("start")

    def _close_stream(self):
        self.stream.stop()
        self.stream.close()
        self.stream = None
        if self.ducker:
            self.ducker.restore()

    def stop_recording(self):
        with self.lock:
            if self.state != "recording":
                return
            self._close_stream()
            self.set_state("transcribing")
        if self.cfg["sounds"]:
            plat.beep("stop")
        audio = np.concatenate(self.chunks) if self.chunks else np.zeros(0, dtype=np.float32)
        threading.Thread(
            target=self._process, args=(audio, self.started_at, self.target), daemon=True
        ).start()

    def abort_recording(self):
        """Zkratka byla jen součástí jiné kombinace (např. Ctrl+C) – nahrávku zahodíme."""
        with self.lock:
            if self.state != "recording":
                return
            self._close_stream()
            self.set_state("idle")
        log.info("Nahrávání zrušeno – během držení zkratky byla stisknuta jiná klávesa")

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
                    engine = "groq" if config.groq_key(self.cfg) else self.cfg["model"]
                    history.save(started_at, text, target[0], target[1], duration, engine)
        except Exception:
            log.exception("Přepis selhal")
            failed = True
            if self.cfg["sounds"]:
                plat.beep("error")
        finally:
            self.set_state("idle")
            if failed and self.overlay:
                self.overlay.show("error", "Přepis se nepovedl")

    # --- zkratky -------------------------------------------------------------
    def on_hotkey_press(self, hk):
        if self.state == "idle":
            self.start_recording()
        elif self.state == "recording" and self.cfg["mode"] == "toggle":
            self.stop_recording()

    def on_hotkey_release(self, hk):
        if self.cfg["mode"] == "hold":
            self.stop_recording()

    def on_hotkey_interrupt(self, hk):
        self.abort_recording()

    # --- nastavení -------------------------------------------------------------
    def _watch_config(self):
        """Změny z okna nastavení (nebo ručně v config.json) se projeví bez restartu."""
        while True:
            time.sleep(1)
            try:
                mtime = config.CONFIG_PATH.stat().st_mtime
                if mtime == self.config_mtime:
                    continue
                self.config_mtime = mtime
                new = config.load_config()
            except Exception:
                log.exception("Nepodařilo se načíst config.json")
                continue
            engine_changed = (
                bool(config.groq_key(new)) != bool(config.groq_key(self.cfg)) or new["model"] != self.cfg["model"]
            )
            self.cfg.clear()
            self.cfg.update(new)
            self._apply_extras()
            self.hotkeys.set_hotkeys(self.cfg["hotkeys"])
            self.icon.update_menu()
            log.info("Nastavení aktualizováno, zkratky: %s (%s)", self.cfg["hotkeys"], self.cfg["mode"])
            if engine_changed and self.state == "idle":
                self._load_engine()

    def _load_engine(self):
        self.set_state("loading")
        try:
            self.transcriber.load()
        except Exception:
            log.exception("Nepodařilo se načíst model")
            self.set_state("error")
            return False
        self.set_state("idle")
        return True

    # --- běh ---------------------------------------------------------------
    def _init(self, icon):
        icon.visible = True
        threading.Thread(target=self._watch_config, daemon=True).start()
        if not self._load_engine():
            return
        self.hotkeys.set_hotkeys(self.cfg["hotkeys"])
        if self.cfg["sounds"]:
            plat.beep("ready")
        log.info("Diktovátko %s připraveno, zkratky: %s (%s)", VERSION, self.cfg["hotkeys"], self.cfg["mode"])

    def open_window(self, view):
        UI_REQUEST.write_text(view, encoding="utf-8")
        # Už otevřené okno jen vyvoláme do popředí (samo si přečte, kterou sekci ukázat).
        if plat.focus_window(self.window_proc, WINDOW_TITLE):
            return
        # Samostatný proces, aby okno nekolidovalo s ikonou v liště.
        self.window_proc = subprocess.Popen([sys.executable, str(APP_DIR / "app_window.py")], cwd=APP_DIR)

    def export_history(self, period):
        try:
            start, end = history.period_range(period)
            out, n = history.export(start, end)
            log.info("Export %s–%s: %d záznamů -> %s", start, end, n, out)
            plat.open_path(out)
        except Exception:
            log.exception("Export selhal")

    def open_exports(self):
        history.EXPORT_DIR.mkdir(exist_ok=True)
        plat.open_path(history.EXPORT_DIR)

    def quit(self):
        if self.ducker:
            self.ducker.restore_now()
        self.hotkeys.stop()
        self.icon.stop()

    def run(self):
        self.icon.run(setup=self._init)


if __name__ == "__main__":
    plat.init_process()
    try:
        App().run()
    except Exception:
        log.exception("Neočekávaná chyba")
        sys.exit(1)
