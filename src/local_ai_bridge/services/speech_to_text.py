from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any


class SpeechToTextError(RuntimeError):
    """Raised when microphone capture or transcription cannot be completed."""


@dataclass
class MicrophoneRecorder:
    sample_rate: int = 16_000
    channels: int = 1
    _stream: Any = field(default=None, init=False, repr=False)
    _frames: list[bytes] = field(default_factory=list, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        if self.is_recording:
            return
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise SpeechToTextError(
                "Dipendenza audio mancante. Reinstalla il programma per aggiungere 'sounddevice'."
            ) from exc

        with self._lock:
            self._frames.clear()

        def callback(indata, _frames, _time, status) -> None:
            if status:
                pass
            with self._lock:
                self._frames.append(bytes(indata))

        try:
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=callback,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise SpeechToTextError(f"Impossibile avviare il microfono: {exc}") from exc

    def stop(self) -> bytes:
        stream = self._stream
        self._stream = None
        if stream is None:
            return b""
        try:
            stream.stop()
            stream.close()
        except Exception as exc:
            raise SpeechToTextError(f"Errore durante l'arresto del microfono: {exc}") from exc
        with self._lock:
            return b"".join(self._frames)

    def cancel(self) -> None:
        try:
            self.stop()
        except SpeechToTextError:
            pass
        with self._lock:
            self._frames.clear()


def transcribe_google(pcm_data: bytes, sample_rate: int = 16_000, language: str = "it-IT") -> str:
    """Transcribe signed 16-bit mono PCM using SpeechRecognition's Google backend."""
    if not pcm_data:
        raise SpeechToTextError("Nessun audio registrato.")
    try:
        import speech_recognition as sr
    except ImportError as exc:
        raise SpeechToTextError(
            "Dipendenza di trascrizione mancante. Reinstalla il programma per aggiungere 'SpeechRecognition'."
        ) from exc

    recognizer = sr.Recognizer()
    audio = sr.AudioData(pcm_data, sample_rate, 2)
    try:
        text = recognizer.recognize_google(audio, language=language)
    except sr.UnknownValueError as exc:
        raise SpeechToTextError(
            "Non è stato possibile comprendere l'audio. Riprova parlando più vicino al microfono."
        ) from exc
    except sr.RequestError as exc:
        raise SpeechToTextError(f"Servizio di trascrizione non raggiungibile: {exc}") from exc
    return text.strip()


def merge_task_text(existing: str, transcript: str) -> str:
    existing = existing.rstrip()
    transcript = transcript.strip()
    if not existing:
        return transcript
    if not transcript:
        return existing
    return f"{existing}\n{transcript}"
