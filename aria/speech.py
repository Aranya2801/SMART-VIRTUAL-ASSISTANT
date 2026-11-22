"""Text-to-speech and speech-to-text.

The old code called pyttsx3's runAndWait() from whichever thread wanted to
talk, including the reminder threads. pyttsx3 isn't thread safe, so a
reminder firing while the assistant was answering would hang or crash the
engine (on Windows it raised "run loop already started"). Now a single worker
thread owns the engine and everything else just puts text on a queue.
"""

from __future__ import annotations

import logging
import queue
import threading

log = logging.getLogger(__name__)


class ConsoleSpeaker:
    """Prints instead of speaking. Used in text mode and in tests."""

    def __init__(self, prefix: str = "ARIA: "):
        self.prefix = prefix
        self._lock = threading.Lock()
        self.history: list[str] = []

    def say(self, text: str) -> None:
        with self._lock:
            self.history.append(text)
            print(f"{self.prefix}{text}", flush=True)

    def wait(self) -> None:
        pass

    def close(self) -> None:
        pass


class TTSSpeaker(ConsoleSpeaker):
    def __init__(self, rate: int = 170, volume: float = 0.95, voice_index: int = 0):
        super().__init__()
        self._q: queue.Queue[str | None] = queue.Queue()
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._thread = threading.Thread(
            target=self._run, args=(rate, volume, voice_index), name="tts", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=10)
        if self._error:
            raise RuntimeError(f"could not start text-to-speech: {self._error}")

    def _run(self, rate, volume, voice_index):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            if 0 <= voice_index < len(voices):
                engine.setProperty("voice", voices[voice_index].id)
            engine.setProperty("rate", rate)
            engine.setProperty("volume", volume)
        except Exception as exc:  # no audio device, missing espeak, ...
            self._error = exc
            self._ready.set()
            return
        self._ready.set()
        while True:
            text = self._q.get()
            if text is None:
                self._q.task_done()
                break
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                log.exception("tts failed")
            finally:
                self._q.task_done()

    def say(self, text: str) -> None:
        super().say(text)
        self._q.put(text)

    def wait(self) -> None:
        """Block until everything queued so far has been spoken."""
        self._q.join()

    def close(self) -> None:
        self._q.put(None)
        self._thread.join(timeout=5)


class Listener:
    """Microphone -> text using the SpeechRecognition package."""

    def __init__(self, language: str = "en-IN", timeout: float = 8, phrase_limit: float = 12):
        import speech_recognition as sr

        self.sr = sr
        self.language = language
        self.timeout = timeout
        self.phrase_limit = phrase_limit
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 0.8
        self.recognizer.dynamic_energy_threshold = True
        self._mic = sr.Microphone()
        with self._mic as source:
            # calibrate once at start-up rather than before every utterance,
            # the old per-call 0.5 s calibration clipped the start of commands
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)

    def listen(self) -> str:
        sr = self.sr
        with self._mic as source:
            try:
                audio = self.recognizer.listen(source, timeout=self.timeout,
                                               phrase_time_limit=self.phrase_limit)
            except sr.WaitTimeoutError:
                return ""
        try:
            return self.recognizer.recognize_google(audio, language=self.language)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as exc:
            log.error("speech service unavailable: %s", exc)
            return ""
