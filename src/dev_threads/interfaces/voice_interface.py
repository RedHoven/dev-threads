"""Voice interface for dev-threads.

Uses SpeechRecognition for speech-to-text and pyttsx3 for text-to-speech.
The interface listens for a configurable wake word, then interprets the
following utterance as a dev-threads command.

Supported voice commands
------------------------
- "new thread <name> <goal>"          → threads new
- "list threads"                      → threads list
- "pause thread <id>"                 → threads pause
- "resume thread <id>"                → threads resume
- "kill thread <id>"                  → threads kill
- "switch to thread <id>"             → threads attach (prints context)
- "status" / "what's the status"      → threads list
- "stop listening"                    → exit voice mode
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from typing import Any

from dev_threads.config import get_settings
from dev_threads.orchestrator.orchestrator import Orchestrator
from dev_threads.threads.manager import ThreadNotFoundError

logger = logging.getLogger(__name__)


class VoiceInterface:
    """Listens for a wake word and dispatches voice commands.

    Requires optional dependencies:
        pip install SpeechRecognition pyttsx3
    These are declared in pyproject.toml but not imported at module level to
    avoid hard failures when audio hardware is unavailable.
    """

    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator
        self._settings = get_settings()
        self._wake_word: str = self._settings.voice_wake_word.lower()
        self._language: str = self._settings.voice_language
        self._running: bool = False
        self._tts_engine: Any = None  # pyttsx3 engine; initialised lazily

    # ── Public entry-point ────────────────────────────────────────────────────

    async def run(self) -> None:
        """Start the voice listener loop (blocking until stopped)."""
        try:
            import speech_recognition as sr  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "SpeechRecognition is not installed. "
                "Run: pip install SpeechRecognition"
            ) from exc

        self._init_tts()
        self._running = True
        recogniser = sr.Recognizer()
        mic = sr.Microphone()

        self._speak(f"Dev-threads voice interface active. Say {self._wake_word!r} to begin.")
        logger.info("Voice interface started. Wake word: %r", self._wake_word)

        loop = asyncio.get_event_loop()

        with mic as source:
            recogniser.adjust_for_ambient_noise(source)

        while self._running:
            try:
                audio = await loop.run_in_executor(
                    None, self._listen_once, recogniser, mic
                )
                if audio is None:
                    continue

                text = await loop.run_in_executor(
                    None,
                    lambda a=audio: recogniser.recognize_google(  # type: ignore[call-arg]
                        a, language=self._language
                    ),
                )
                text = text.lower().strip()
                logger.debug("Heard: %r", text)

                if self._wake_word in text:
                    # Strip the wake word and dispatch the remainder
                    utterance = text.replace(self._wake_word, "").strip()
                    if utterance:
                        await self._dispatch(utterance)
                    else:
                        self._speak("Yes? What would you like to do?")

            except Exception as exc:  # noqa: BLE001
                logger.debug("Voice recognition error: %s", exc)

    def stop(self) -> None:
        """Signal the voice loop to stop after the current iteration."""
        self._running = False

    # ── Command dispatcher ────────────────────────────────────────────────────

    async def _dispatch(self, utterance: str) -> None:
        logger.info("Voice command: %r", utterance)

        if re.search(r"stop (listening|voice|interface)", utterance):
            self._speak("Stopping voice interface.")
            self.stop()
            return

        if re.search(r"(list|show|status|what.s the status)", utterance):
            threads = self.orchestrator.list_threads()
            if not threads:
                self._speak("There are no active dev threads.")
            else:
                names = ", ".join(f"{t.name} ({t.status.value})" for t in threads)
                self._speak(f"Active threads: {names}.")
            return

        m = re.search(r"new thread\s+(\w+)\s+(.+)", utterance)
        if m:
            name, goal = m.group(1), m.group(2)
            self._speak(f"Starting new thread: {name}.")
            try:
                thread = await self.orchestrator.new_thread(name, goal)
                self._speak(f"Thread {name} is now running.")
                logger.info("Voice: created thread %s", thread.id)
            except Exception as exc:  # noqa: BLE001
                self._speak(f"Failed to start thread: {exc}")
            return

        for action_word, method in (
            ("pause", "pause_thread"),
            ("resume", "resume_thread"),
            ("kill", "kill_thread"),
        ):
            m = re.search(rf"{action_word} thread\s+(\S+)", utterance)
            if m:
                thread_id = m.group(1)
                self._speak(f"{action_word.capitalize()}ing thread {thread_id}.")
                try:
                    await getattr(self.orchestrator, method)(thread_id)
                    self._speak(f"Done.")
                except ThreadNotFoundError:
                    self._speak(f"Thread {thread_id} not found.")
                except Exception as exc:  # noqa: BLE001
                    self._speak(f"Error: {exc}")
                return

        m = re.search(r"switch to thread\s+(\S+)", utterance)
        if m:
            thread_id = m.group(1)
            try:
                ctx = self.orchestrator.get_context(thread_id)
                thread = self.orchestrator.get_thread(thread_id)
                summary = ctx.get("summary", f"Goal: {thread.goal}")
                self._speak(f"Switching to thread {thread.name}. {summary}")
            except ThreadNotFoundError:
                self._speak(f"Thread {thread_id} not found.")
            return

        self._speak("Sorry, I didn't understand that command.")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _listen_once(self, recogniser: Any, mic: Any) -> Any:  # noqa: ANN401
        """Blocking listen; returns an AudioData or None on timeout."""
        try:
            import speech_recognition as sr  # noqa: PLC0415

            with mic as source:
                return recogniser.listen(source, timeout=5, phrase_time_limit=10)
        except Exception:
            return None

    def _init_tts(self) -> None:
        try:
            import pyttsx3  # noqa: PLC0415

            self._tts_engine = pyttsx3.init()
        except Exception as exc:
            logger.warning("TTS unavailable: %s", exc)
            self._tts_engine = None

    def _speak(self, text: str) -> None:
        """Say *text* aloud (no-op if TTS engine is unavailable)."""
        logger.info("TTS: %s", text)
        if self._tts_engine is None:
            return
        try:
            self._tts_engine.say(text)
            self._tts_engine.runAndWait()
        except Exception as exc:
            logger.debug("TTS error: %s", exc)
