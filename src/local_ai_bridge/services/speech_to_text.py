from __future__ import annotations

import errno
import importlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


class SpeechToTextError(RuntimeError):
    """Raised when microphone capture or transcription cannot be completed."""


_SOUNDDEVICE_IMPORT_LOCK = Lock()


def _import_sounddevice():
    """Import sounddevice without corrupting stderr in Windows GUI processes.

    sounddevice temporarily duplicates file descriptor 2 while PortAudio is
    initialized.  In pythonw/frozen Windows applications that descriptor can be
    absent or unsuitable for duplication, which later breaks subprocess calls
    (notably SpeechRecognition's FLAC encoder) with ``WinError 50``.

    During the import we make the attempted duplication of fd 2 fail cleanly;
    sounddevice already treats that failure as a supported path and proceeds
    without redirecting PortAudio's diagnostics.
    """

    if "sounddevice" in sys.modules:
        return sys.modules["sounddevice"]

    needs_windows_guard = os.name == "nt" and (
        sys.stderr is None or getattr(sys, "frozen", False)
    )
    if not needs_windows_guard:
        return importlib.import_module("sounddevice")

    with _SOUNDDEVICE_IMPORT_LOCK:
        if "sounddevice" in sys.modules:
            return sys.modules["sounddevice"]

        original_dup = os.dup

        def guarded_dup(fd: int) -> int:
            if fd == 2:
                raise OSError(errno.EBADF, "stderr duplication disabled for Windows GUI mode")
            return original_dup(fd)

        os.dup = guarded_dup
        try:
            return importlib.import_module("sounddevice")
        finally:
            os.dup = original_dup


def _flac_subprocess_kwargs() -> dict[str, Any]:
    """Return subprocess options that never inherit broken GUI std handles."""

    kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "close_fds": True,
    }
    if os.name == "nt":
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup_info.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startup_info
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kwargs


def _encode_flac_safely(flac_converter: str, wav_data: bytes) -> bytes:
    """Encode WAV data while isolating the converter from invalid std handles."""

    command = [
        flac_converter,
        "--stdout",
        "--totally-silent",
        "--best",
        "-",
    ]
    try:
        process = subprocess.Popen(command, **_flac_subprocess_kwargs())
        flac_data, stderr = process.communicate(wav_data)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 50:
            raise SpeechToTextError(
                "Windows non ha consentito l'avvio del convertitore audio. "
                "Chiudi e riapri BridgAI, poi riprova la dettatura."
            ) from exc
        raise SpeechToTextError(f"Impossibile avviare il convertitore audio: {exc}") from exc

    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        suffix = f" Dettaglio: {detail}" if detail else ""
        raise SpeechToTextError(f"Conversione audio non riuscita.{suffix}")
    if not flac_data:
        raise SpeechToTextError("Il convertitore audio non ha prodotto dati utilizzabili.")
    return flac_data


def _speech_recognition_audio(sr, pcm_data: bytes, sample_rate: int):
    """Create AudioData with a Windows-safe FLAC conversion implementation."""

    class SafeAudioData(sr.AudioData):
        def get_flac_data(self, convert_rate=None, convert_width=None):
            if convert_width is not None:
                assert convert_width % 1 == 0 and 1 <= convert_width <= 3
            if self.sample_width > 3 and convert_width is None:
                convert_width = 3
            wav_data = self.get_wav_data(convert_rate, convert_width)
            return _encode_flac_safely(sr.get_flac_converter(), wav_data)

    return SafeAudioData(pcm_data, sample_rate, 2)


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
            sd = _import_sounddevice()
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
    audio = _speech_recognition_audio(sr, pcm_data, sample_rate)
    try:
        text = recognizer.recognize_google(audio, language=language)
    except SpeechToTextError:
        raise
    except sr.UnknownValueError as exc:
        raise SpeechToTextError(
            "Non è stato possibile comprendere l'audio. Riprova parlando più vicino al microfono."
        ) from exc
    except sr.RequestError as exc:
        raise SpeechToTextError(f"Servizio di trascrizione non raggiungibile: {exc}") from exc
    except OSError as exc:
        if getattr(exc, "winerror", None) == 50:
            raise SpeechToTextError(
                "Windows non ha consentito la conversione dell'audio. "
                "Chiudi e riapri BridgAI, poi riprova la dettatura."
            ) from exc
        raise SpeechToTextError(f"Errore di sistema durante la trascrizione: {exc}") from exc
    except Exception as exc:
        raise SpeechToTextError(f"Trascrizione non riuscita: {exc}") from exc
    return text.strip()


def merge_task_text(existing: str, transcript: str) -> str:
    existing = existing.rstrip()
    transcript = transcript.strip()
    if not existing:
        return transcript
    if not transcript:
        return existing
    return f"{existing}\n{transcript}"
