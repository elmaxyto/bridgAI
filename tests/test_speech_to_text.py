from __future__ import annotations

import subprocess
import sys
import types

import pytest

from local_ai_bridge.services import speech_to_text


class _FakeProcess:
    def __init__(self, returncode: int = 0, output: bytes = b"flac", error: bytes = b"") -> None:
        self.returncode = returncode
        self._output = output
        self._error = error
        self.input_data: bytes | None = None

    def communicate(self, data: bytes):
        self.input_data = data
        return self._output, self._error


def test_flac_encoder_redirects_all_standard_handles(monkeypatch) -> None:
    captured: dict[str, object] = {}
    process = _FakeProcess()

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return process

    monkeypatch.setattr(speech_to_text.subprocess, "Popen", fake_popen)

    result = speech_to_text._encode_flac_safely("flac-tool", b"wav-data")

    assert result == b"flac"
    assert process.input_data == b"wav-data"
    assert captured["command"] == [
        "flac-tool",
        "--stdout",
        "--totally-silent",
        "--best",
        "-",
    ]
    kwargs = captured["kwargs"]
    assert kwargs["stdin"] is subprocess.PIPE
    assert kwargs["stdout"] is subprocess.PIPE
    assert kwargs["stderr"] is subprocess.PIPE
    assert kwargs["close_fds"] is True


def test_sounddevice_import_guard_skips_stderr_duplication_on_windows_gui(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "sounddevice", raising=False)
    monkeypatch.setattr(speech_to_text.os, "name", "nt")
    monkeypatch.setattr(speech_to_text.sys, "stderr", None)
    original_dup = speech_to_text.os.dup
    fake_module = types.ModuleType("sounddevice")

    def fake_import_module(name: str):
        assert name == "sounddevice"
        with pytest.raises(OSError):
            speech_to_text.os.dup(2)
        monkeypatch.setitem(sys.modules, name, fake_module)
        return fake_module

    monkeypatch.setattr(speech_to_text.importlib, "import_module", fake_import_module)

    assert speech_to_text._import_sounddevice() is fake_module
    assert speech_to_text.os.dup is original_dup


def _fake_speech_recognition_module(recognize_google):
    module = types.ModuleType("speech_recognition")

    class AudioData:
        def __init__(self, frame_data: bytes, sample_rate: int, sample_width: int) -> None:
            self.frame_data = frame_data
            self.sample_rate = sample_rate
            self.sample_width = sample_width

        def get_wav_data(self, convert_rate=None, convert_width=None) -> bytes:
            return b"wav-data"

    class Recognizer:
        def recognize_google(self, audio, language: str):
            return recognize_google(audio, language)

    class UnknownValueError(Exception):
        pass

    class RequestError(Exception):
        pass

    module.AudioData = AudioData
    module.Recognizer = Recognizer
    module.UnknownValueError = UnknownValueError
    module.RequestError = RequestError
    module.get_flac_converter = lambda: "flac-tool"
    return module


def test_google_transcription_uses_safe_flac_audio(monkeypatch) -> None:
    encoded: dict[str, object] = {}

    def fake_encode(converter: str, wav_data: bytes) -> bytes:
        encoded["converter"] = converter
        encoded["wav_data"] = wav_data
        return b"safe-flac"

    def recognize_google(audio, language: str) -> str:
        assert language == "it-IT"
        assert audio.get_flac_data(convert_rate=16_000, convert_width=2) == b"safe-flac"
        return "  testo dettato  "

    module = _fake_speech_recognition_module(recognize_google)
    monkeypatch.setitem(sys.modules, "speech_recognition", module)
    monkeypatch.setattr(speech_to_text, "_encode_flac_safely", fake_encode)

    result = speech_to_text.transcribe_google(b"pcm", sample_rate=16_000)

    assert result == "testo dettato"
    assert encoded == {"converter": "flac-tool", "wav_data": b"wav-data"}


def test_google_transcription_converts_winerror_50_to_actionable_error(monkeypatch) -> None:
    error = OSError("Richiesta non supportata")
    error.winerror = 50

    def recognize_google(_audio, _language: str) -> str:
        raise error

    module = _fake_speech_recognition_module(recognize_google)
    monkeypatch.setitem(sys.modules, "speech_recognition", module)

    with pytest.raises(speech_to_text.SpeechToTextError) as exc_info:
        speech_to_text.transcribe_google(b"pcm")

    message = str(exc_info.value)
    assert "Windows" in message
    assert "conversione dell'audio" in message


def test_merge_task_text_keeps_existing_text() -> None:
    assert speech_to_text.merge_task_text("prima\n", " seconda ") == "prima\nseconda"
