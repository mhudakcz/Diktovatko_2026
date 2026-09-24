"""Diktovátko – bezplatná alternativa k Wispr Flow.

Podržíte klávesovou zkratku, mluvíte, pustíte ji a přepsaný text
se vloží tam, kde máte kurzor.
"""

import io
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import threading
import time
import wave
import webbrowser
from collections import deque
from datetime import datetime

import numpy as np
import pystray
import sounddevice as sd
from PIL import Image, ImageDraw

import config
import history
import i18n
import plat
import updater
from i18n import t
from version import VERSION

APP_DIR = config.APP_DIR
LOG_PATH = APP_DIR / "diktovatko.log"
UI_REQUEST = APP_DIR / ".ui_request"
WINDOW_TITLE = "Diktovátko"
SAMPLE_RATE = 16000
MAX_RECORDING_SECONDS = 15 * 60  # zapomenuté nahrávání v režimu Přepínat se samo ukončí
PRUNE_EVERY_SECONDS = 6 * 3600
SUPPORT_URL = "https://ko-fi.com/michalhudak"
UPDATE_EVERY_SECONDS = 2 * 3600
UPDATE_FIRST_DELAY = 30  # první kontrola chvíli po startu, ať nezdržuje načítání

# Log se rotuje (max. 3 × 1 MB) a nikdy neobsahuje nadiktovaný text, jen délky a časy.
_handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
if sys.platform != "win32":
    os.chmod(LOG_PATH, 0o600)
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
HOTKEY_LABELS = dict(plat.presets())


def status_text(state):
    return t("status." + state)


def hotkey_label(hk):
    return i18n.hotkey_label(hk, HOTKEY_LABELS.get(hk, hk))


class GroqError(Exception):
    """Chyba služby Groq s krátkým klíčem hlášky pro uživatele (overlay.*)."""

    def __init__(self, message_key, detail=""):
        super().__init__(detail or message_key)
        self.message_key = message_key


class Transcriber:
    def __init__(self, cfg):
        self.cfg = cfg
        self.model = None
        self.model_name = None
        self.active_engine = None  # "groq" nebo název lokálního modelu, který je právě připravený
        self._http = None
        self._lock = threading.Lock()

    def uses_groq(self):
        return bool(config.groq_key(self.cfg))

    def wanted_engine(self):
        return "groq" if self.uses_groq() else self.cfg["model"]

    def needs_reload(self):
        return self.wanted_engine() != self.active_engine

    def load(self):
        if self.uses_groq():
            log.info("Používám Groq API (%s)", self.cfg["groq_model"])
            self.active_engine = "groq"
            return
        with self._lock:
            if self.model is not None and self.model_name == self.cfg["model"]:
                self.active_engine = self.model_name
                return
            from faster_whisper import WhisperModel

            log.info("Načítám lokální model %s…", self.cfg["model"])
            self.model = WhisperModel(
                self.cfg["model"], device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4
            )
            self.model_name = self.cfg["model"]
            self.active_engine = self.model_name
            log.info("Model načten")

    def transcribe(self, audio):
        if self.uses_groq():
            # Groq přijme soubor do 25 MB (~13 min WAV), delší nahrávku dělíme v tichém místě.
            return " ".join(x for x in (self._groq(part) for part in split_audio(audio)) if x)
        if self.model is None or self.model_name != self.cfg["model"]:
            self.load()  # např. klíč byl smazán během přepisu – model nahrajeme teď
        segments, _ = self.model.transcribe(
            audio,
            language=self.cfg["language"],
            beam_size=self.cfg["beam_size"],
            initial_prompt=self.cfg["initial_prompt"] or None,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return "".join(s.text for s in segments).strip()

    def _client(self):
        import httpx

        if self._http is None:  # jedno spojení pro všechna diktování (bez nového TLS handshaku)
            self._http = httpx.Client(timeout=httpx.Timeout(60, connect=10))
        return self._http

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
        try:
            r = self._client().post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {config.groq_key(self.cfg)}"},
                files={"file": ("audio.wav", buf.getvalue(), "audio/wav")},
                data=data,
            )
        except httpx.HTTPError as e:
            raise GroqError("overlay.offline", type(e).__name__) from e
        if r.status_code in (401, 403):
            raise GroqError("overlay.bad_key", f"HTTP {r.status_code}")
        if r.status_code == 429:
            raise GroqError("overlay.rate_limit", "HTTP 429")
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


# Věty, které si Whisper vymýšlí z ticha (naučil se je z titulků a videí). Zahazujeme je,
# jen když tvoří celý přepis – skutečné diktování se slovy "děkuji za pozornost" projde.
HALLUCINATIONS = re.compile(
    r"^\W*(titulky (vytvořil|připravil|pro vás)\b.*|děkuji za (pozornost|sledování)|"
    r"subtitles by\b.*|thanks for watching!?|untertitel (im auftrag des zdf|von)\b.*|"
    r"amara\.org.*)?\W*$",
    re.IGNORECASE,
)


def is_hallucination(text):
    return bool(HALLUCINATIONS.match(text))


class App:
    def __init__(self):
        self.cfg = config.load_config()
        i18n.set_lang(self.cfg["ui_language"])
        self.config_mtime = config.CONFIG_PATH.stat().st_mtime
        self.transcriber = Transcriber(self.cfg)
        self.state = "loading"
        self.chunks = []
        self.levels = deque(maxlen=40)
        self.overlay = None  # vytváří se jen jednou, vypnutí se řeší přes nastavení
        self.ducker = None
        self.reload_engine = False
        self.update = None  # {"version", "notes", "url"}, když je na GitHubu novější verze
        self._notified = None
        self._stopping = False
        self.stream = None
        self.window_proc = None
        self.lock = threading.RLock()
        self._ensure_extras()
        self.hotkeys = plat.hotkey_manager(self.on_hotkey_press, self.on_hotkey_release, self.on_hotkey_interrupt)

        # Texty položek jsou funkce, aby se po změně jazyka v nastavení přeložily bez restartu.
        tr = lambda key: (lambda _: t(key))  # noqa: E731
        export_items = [
            pystray.MenuItem(tr("period." + key), (lambda k: lambda: self.export_history(k))(key))
            for key, _ in history.PERIODS
            if key != "today"
        ]
        export_items += [pystray.Menu.SEPARATOR, pystray.MenuItem(tr("menu.exports_folder"), self.open_exports)]
        self.icon = pystray.Icon(
            "diktovatko",
            ICONS["loading"],
            "Diktovátko",
            menu=pystray.Menu(
                pystray.MenuItem(f"Diktovátko {VERSION}", None, enabled=False),
                pystray.MenuItem(lambda _: status_text(self.state), None, enabled=False),
                pystray.MenuItem(
                    lambda _: t("menu.hotkey", keys=", ".join(hotkey_label(h) for h in self.cfg["hotkeys"])),
                    None,
                    enabled=False,
                ),
                pystray.MenuItem(
                    lambda _: t("menu.update", v=self.update["version"]) if self.update else "",
                    lambda: threading.Thread(target=self.install_update, daemon=True).start(),
                    visible=lambda _: bool(self.update),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(tr("menu.history"), lambda: self.open_window("history"), default=True),
                pystray.MenuItem(tr("menu.stats"), lambda: self.open_window("stats")),
                pystray.MenuItem(tr("menu.settings"), lambda: self.open_window("settings")),
                pystray.MenuItem(tr("menu.export"), pystray.Menu(*export_items)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(tr("menu.support"), lambda: webbrowser.open(SUPPORT_URL)),
                pystray.MenuItem(tr("menu.log"), lambda: plat.open_path(LOG_PATH)),
                pystray.MenuItem(tr("menu.quit"), self.quit),
            ),
        )

    def _ensure_extras(self):
        if self.cfg["overlay"] and self.overlay is None:
            self.overlay = plat.overlay(lambda: list(self.levels))
        if self.ducker is None:
            self.ducker = plat.audio_ducker(self.cfg["duck_level"])
            self.ducker.restore_leftover()  # hlasitost ztlumená před pádem aplikace se vrátí
        self.ducker.level = self.cfg["duck_level"]
        if not self.cfg["duck_audio"]:
            self.ducker.restore()

    def _show(self, state, message=""):
        if self.overlay and self.cfg["overlay"]:
            self.overlay.show(state, message)
        elif self.overlay:
            self.overlay.hide()

    def set_state(self, state):
        self.state = state

        def ui():
            self.icon.icon = ICONS[state]
            self.icon.title = f"Diktovátko – {status_text(state)}"
            self.icon.update_menu()

        plat.run_on_main(ui)  # na macOS smí UI měnit jen hlavní vlákno
        if state in ("recording", "transcribing"):
            self._show(state)
        elif self.overlay:
            self.overlay.hide()

    def _error(self, message_key):
        if self.cfg["sounds"]:
            plat.beep("error")
        self._show("error", t(message_key))

    # --- nahrávání ---------------------------------------------------------
    def _audio_callback(self, indata, frames, time_info, status):
        mono = indata[:, 0].copy()
        self.chunks.append(mono)
        rms = float(np.sqrt(np.mean(mono**2)))
        self.levels.append(min(1.0, (rms * 14) ** 0.8))
        if len(self.chunks) * 800 >= MAX_RECORDING_SECONDS * SAMPLE_RATE and not self._stopping:
            self._stopping = True
            log.info("Nahrávání ukončeno po %d minutách", MAX_RECORDING_SECONDS // 60)
            threading.Thread(target=self.stop_recording, daemon=True).start()

    def start_recording(self):
        with self.lock:
            if self.state != "idle":
                return
            self.chunks = []
            self.levels.clear()
            self._stopping = False
            self.started_at = datetime.now()
            try:
                self.target = plat.foreground_window()
                self.target_id = plat.foreground_id()
            except Exception:
                log.exception("Nepodařilo se zjistit aktivní okno")
                self.target, self.target_id = ("", ""), None
            try:
                self.stream = sd.InputStream(
                    samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=800,
                    callback=self._audio_callback,
                )
                self.stream.start()
            except Exception:
                log.exception("Mikrofon není dostupný")
                self.stream = None
                self._error("overlay.no_mic")
                return
            if self.cfg["duck_audio"]:
                self.ducker.duck()
            self.set_state("recording")
        if self.cfg["sounds"]:
            plat.beep("start")

    def _close_stream(self):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            log.exception("Nepodařilo se zavřít mikrofon")
        self.stream = None
        self.ducker.restore()

    def stop_recording(self):
        with self.lock:
            if self.state != "recording":
                return
            self._close_stream()
            self.set_state("transcribing")
            audio = np.concatenate(self.chunks) if self.chunks else np.zeros(0, dtype=np.float32)
            job = (audio, self.started_at, self.target, self.target_id)
        if self.cfg["sounds"]:
            plat.beep("stop")
        threading.Thread(target=self._process, args=job, daemon=True).start()

    def abort_recording(self):
        """Zkratka byla jen součástí jiné kombinace (např. Ctrl+C) – nahrávku zahodíme."""
        with self.lock:
            if self.state != "recording":
                return
            self._close_stream()
            self.set_state("idle")
        log.info("Nahrávání zrušeno – během držení zkratky byla stisknuta jiná klávesa")

    def _process(self, audio, started_at, target, target_id):
        message = None
        try:
            duration = len(audio) / SAMPLE_RATE
            if duration < 0.3:
                log.info("Příliš krátká nahrávka (%.2fs), ignoruji", duration)
                return
            if not has_speech(audio):
                peak = float(np.abs(audio).max()) if len(audio) else 0.0
                rms = float(np.sqrt(np.mean(audio**2))) if len(audio) else 0.0
                log.info("V nahrávce (%.1fs) není řeč, ignoruji (špička %.3f, RMS %.4f)", duration, peak, rms)
                return
            t0 = time.time()
            text = self.transcriber.transcribe(audio)
            log.info("Přepis %.1fs audia za %.1fs, %d znaků", duration, time.time() - t0, len(text))
            if not text or is_hallucination(text):
                log.info("Prázdný přepis nebo typická halucinace Whisperu, nic nevkládám")
                return
            pasted = self.paste(text + (" " if self.cfg["trailing_space"] else ""), target_id)
            if not pasted:
                message = "overlay.copied"
            if self.cfg["history"]:
                engine = "groq" if self.transcriber.uses_groq() else self.cfg["model"]
                title = target[1] if self.cfg["store_titles"] else ""
                history.save(started_at, text, target[0], title, duration, engine)
        except GroqError as e:
            log.warning("Groq: %s", e)
            message = e.message_key
        except Exception:
            log.exception("Přepis selhal")
            message = "overlay.failed"
        finally:
            self.set_state("idle")
            if message == "overlay.copied":
                self._show("error", t(message, paste=plat.PASTE_HINT))
            elif message:
                self._error(message)
            self._maybe_reload_engine()

    def paste(self, text, target_id):
        """Vloží text přes schránku. Když se mezitím změnilo aktivní okno, jen ho nechá ve schránce."""
        if target_id is not None and plat.foreground_id() != target_id:
            log.info("Aktivní okno se během přepisu změnilo, text zůstává ve schránce")
            plat.set_clipboard(text)
            return False
        previous = plat.get_clipboard()  # None = ve schránce nebyl text (obrázek, soubor) – neobnovujeme
        plat.set_clipboard(text)
        seq = plat.clipboard_seq()
        plat.wait_modifiers_released()  # držený Win/Ctrl by z Ctrl+V udělal jinou zkratku
        plat.paste()
        # Pomalejší aplikace (Electron, vzdálená plocha) čtou schránku se zpožděním.
        time.sleep(0.8)
        if previous is not None and plat.clipboard_seq() == seq:
            plat.set_clipboard(previous, private=False)
        return True

    # --- zkratky (volá je jedno vlákno správce zkratek, v pořadí stisků) ----------------------
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
        last_prune = 0.0
        while True:
            time.sleep(1)
            if time.time() - last_prune > PRUNE_EVERY_SECONDS:
                last_prune = time.time()
                self._prune()
            self._handle_update_request()
            try:
                mtime = config.CONFIG_PATH.stat().st_mtime
                if mtime == self.config_mtime:
                    continue
                self.config_mtime = mtime
                config.invalidate_key_cache()  # klíč mohl změnit proces okna aplikace
                new = config.load_config()
            except Exception:
                log.exception("Nepodařilo se načíst config.json")
                continue
            with self.lock:
                old = self.cfg
                # Celý slovník vyměníme naráz, ať ostatní vlákna nikdy nevidí rozpracovaný stav.
                self.cfg = new
                self.transcriber.cfg = new
                if self.transcriber.needs_reload():
                    self.reload_engine = True
            i18n.set_lang(new["ui_language"])
            self._ensure_extras()
            self.hotkeys.set_hotkeys(new["hotkeys"])
            plat.run_on_main(self.icon.update_menu)
            log.info("Nastavení aktualizováno, zkratky: %s (%s)", new["hotkeys"], new["mode"])
            if new["history_days"] != old["history_days"]:
                self._prune()
            self._maybe_reload_engine()

    def _prune(self):
        try:
            n = history.prune(self.cfg["history_days"])
            if n:
                log.info("Smazáno %d starých záznamů historie", n)
        except Exception:
            log.exception("Promazání historie selhalo")

    def _maybe_reload_engine(self):
        """Změnu přepisu (Groq ↔ lokální model) provedeme, až aplikace nic nenahrává ani nepřepisuje."""
        with self.lock:
            if not self.reload_engine or self.state != "idle":
                return
            self.reload_engine = False
            self.set_state("loading")
        self._load_engine()

    def _load_engine(self):
        try:
            self.transcriber.load()
        except Exception:
            log.exception("Nepodařilo se načíst model")
            self.set_state("error")
            return False
        self.set_state("idle")
        return True

    # --- aktualizace ------------------------------------------------------------
    def _update_loop(self):
        time.sleep(UPDATE_FIRST_DELAY)
        while True:
            if self.cfg["check_updates"]:
                self.check_update()
            time.sleep(UPDATE_EVERY_SECONDS)

    def check_update(self):
        try:
            self.update = updater.check()
            updater.write_state(latest=self.update, checked=datetime.now().isoformat(timespec="minutes"))
        except Exception:
            log.warning("Kontrola aktualizací se nepovedla", exc_info=True)
            updater.write_state(latest=self.update, error=True)
            return
        plat.run_on_main(self.icon.update_menu)
        if self.update and self._notified != self.update["version"]:
            self._notified = self.update["version"]
            log.info("Je k dispozici verze %s", self.update["version"])
            self._notify(t("notify.update.body", v=self.update["version"]), t("notify.update.title"))

    def _notify(self, text, title="Diktovátko"):
        try:
            self.icon.notify(text, title)
        except Exception:
            log.info("Systémové oznámení nejde zobrazit: %s", text)

    def _handle_update_request(self):
        if not updater.REQUEST_FILE.exists():
            return
        try:
            action = updater.REQUEST_FILE.read_text(encoding="utf-8").strip()
        finally:
            updater.REQUEST_FILE.unlink(missing_ok=True)
        if action == "check":
            self.check_update()
        elif action == "install":
            threading.Thread(target=self.install_update, daemon=True).start()

    def install_update(self):
        if updater.is_dev_checkout():
            self._notify(t("notify.dev"))
            return
        if not self.update:
            self.check_update()
            if not self.update:
                return
        version = self.update["version"]
        with self.lock:
            if self.state in ("recording", "transcribing"):
                return  # aktualizace nepřeruší rozpracované diktování, uživatel to zkusí znovu
            self.set_state("loading")
        self._notify(t("notify.updating", v=version))
        try:
            updater.install(version)
        except Exception:
            log.exception("Aktualizace na %s selhala", version)
            self.set_state("idle")
            self._notify(t("notify.update.fail"))
            return
        updater.write_state(latest=None, installed=version)
        updater.restart()
        self.quit()

    # --- běh ---------------------------------------------------------------
    def _init(self, icon):
        icon.visible = True
        self._prune()
        threading.Thread(target=self._watch_config, daemon=True).start()
        threading.Thread(target=self._update_loop, daemon=True).start()
        updater.write_state(latest=None)
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
            out, n = history.export(start, end, lang=i18n.lang())
            log.info("Export %s–%s: %d záznamů", start, end, n)
            plat.open_path(out)
        except Exception:
            log.exception("Export selhal")

    def open_exports(self):
        history.EXPORT_DIR.mkdir(exist_ok=True)
        plat.open_path(history.EXPORT_DIR)

    def quit(self):
        self.ducker.restore_now()
        self.hotkeys.stop()
        self.icon.stop()

    def run(self):
        self.icon.run(setup=self._init)


if __name__ == "__main__":
    if "--after-update" in sys.argv:
        time.sleep(3)  # předchozí instance se po aktualizaci ještě ukončuje
    plat.init_process()
    try:
        App().run()
    except Exception:
        log.exception("Neočekávaná chyba")
        sys.exit(1)
