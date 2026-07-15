from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from local_ai_bridge.ui.speech_dialog import SpeechDialog


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_insert_button_enables_when_transcript_is_present() -> None:
    _application()
    dialog = SpeechDialog()

    assert dialog.insert_button.isEnabled() is False

    dialog.preview.setPlainText("prova uno due tre")

    assert dialog.insert_button.isEnabled() is True
    dialog.close()


def test_insert_button_stays_disabled_while_recording() -> None:
    _application()
    dialog = SpeechDialog()
    dialog.preview.setPlainText("testo già trascritto")
    dialog.recorder._stream = object()

    dialog._sync_insert_state()

    assert dialog.insert_button.isEnabled() is False
    dialog.recorder._stream = None
    dialog.close()
