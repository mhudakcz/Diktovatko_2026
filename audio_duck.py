"""Windows: ztlumení zvuku ostatních aplikací (Spotify, prohlížeč, videa…) během nahrávání.

Windows si hlasitost jednotlivých aplikací pamatuje natrvalo. Aby po pádu Diktovátka
nezůstal třeba Spotify na 10 %, původní hlasitosti se během ztlumení zapisují do
.ducked.json a při dalším startu se obnoví (restore_leftover).
"""

import json
import logging
import os
import queue
import threading
from pathlib import Path

log = logging.getLogger("diktovatko")
STATE_FILE = Path(__file__).resolve().parent / ".ducked.json"


class AudioDucker:
    def __init__(self, level=0.1):
        self.level = level  # na kolik původní hlasitosti ztlumit (0 = úplně ztlumit)
        self.saved = {}  # pid -> [(SimpleAudioVolume, název procesu, původní hlasitost)]
        self.jobs = queue.Queue()
        # COM operace běží v jednom vlákně, aby nezdržovaly start nahrávání.
        threading.Thread(target=self._worker, daemon=True).start()

    def duck(self):
        self.jobs.put(self._duck)

    def restore(self):
        self.jobs.put(self._restore)

    def restore_now(self, timeout=2):
        done = threading.Event()
        self.jobs.put(lambda: (self._restore(), done.set()))
        done.wait(timeout)

    def restore_leftover(self):
        self.jobs.put(self._restore_leftover)

    def _worker(self):
        import comtypes

        comtypes.CoInitialize()
        while True:
            job = self.jobs.get()
            try:
                job()
            except Exception:
                log.exception("Ztlumení zvuku selhalo")

    def _duck(self):
        from pycaw.pycaw import AudioUtilities

        if self.saved:
            return
        own = os.getpid()
        for s in AudioUtilities.GetAllSessions():
            if not s.Process or s.ProcessId == own:
                continue
            vol = s.SimpleAudioVolume
            current = vol.GetMasterVolume()
            if current <= 0:
                continue
            self.saved.setdefault(s.ProcessId, []).append((vol, s.Process.name(), current))
            vol.SetMasterVolume(current * self.level, None)
        if self.saved:
            STATE_FILE.write_text(json.dumps(
                {name: v for items in self.saved.values() for _, name, v in items}), encoding="utf-8")

    def _restore(self):
        for items in self.saved.values():
            for vol, _, original in items:
                try:
                    vol.SetMasterVolume(original, None)
                except Exception:
                    pass  # aplikace se mezitím mohla zavřít
        self.saved.clear()
        STATE_FILE.unlink(missing_ok=True)

    def _restore_leftover(self):
        if not STATE_FILE.exists():
            return
        from pycaw.pycaw import AudioUtilities

        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except ValueError:
            saved = {}
        for s in AudioUtilities.GetAllSessions():
            if s.Process and s.Process.name() in saved:
                s.SimpleAudioVolume.SetMasterVolume(float(saved[s.Process.name()]), None)
        STATE_FILE.unlink(missing_ok=True)
        log.info("Obnovena hlasitost aplikací ztlumených před posledním ukončením")
