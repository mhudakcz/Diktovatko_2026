"""Ztlumení zvuku ostatních aplikací (Spotify, prohlížeč, videa…) během nahrávání."""

import logging
import os
import queue
import threading

log = logging.getLogger("diktovatko")


class AudioDucker:
    def __init__(self, level=0.1):
        self.level = level  # na kolik původní hlasitosti ztlumit (0 = úplně ztlumit)
        self.saved = {}  # pid -> [(SimpleAudioVolume, původní hlasitost)]
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
            self.saved.setdefault(s.ProcessId, []).append((vol, current))
            vol.SetMasterVolume(current * self.level, None)

    def _restore(self):
        for items in self.saved.values():
            for vol, original in items:
                try:
                    vol.SetMasterVolume(original, None)
                except Exception:
                    pass  # aplikace se mezitím mohla zavřít
        self.saved.clear()
