from __future__ import annotations

import platform
import threading

from local_ai_bridge.i18n import tr as _
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from local_ai_bridge.services.speech_to_text import (
    MicrophoneRecorder,
    SpeechToTextError,
    transcribe_google,
)


def system_dictation_hint(system_name: str | None = None) -> str:
    system_name = (system_name or platform.system()).lower()
    if system_name == "windows":
        return "Alternativa di sistema: fai clic nel campo di testo e premi Win + H per usare la digitazione vocale di Windows."
    if system_name == "darwin":
        return "Alternativa di sistema: fai clic nel campo di testo e usa la scorciatoia configurata in Impostazioni di Sistema > Tastiera > Dettatura."
    if system_name == "linux":
        return "Alternativa di sistema: usa la dettatura disponibile nel tuo ambiente desktop o nella tastiera virtuale. Su Linux scorciatoie e disponibilità variano."
    return "Alternativa di sistema: puoi usare la funzione di dettatura del sistema operativo direttamente nel campo di testo, se disponibile."


class _SpeechSignals(QObject):
    completed = Signal(str)
    failed = Signal(str)


class SpeechDialog(QDialog):
    def __init__(self, parent=None, language: str = "it-IT") -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Dettatura task"))
        self.setModal(True)
        self.resize(600, 470)
        self.setMinimumSize(500, 390)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.language = language
        self.recorder = MicrophoneRecorder()
        self.signals = _SpeechSignals(self)
        self.signals.completed.connect(self._transcription_ready)
        self.signals.failed.connect(self._transcription_failed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel(_("Parla, poi controlla il testo"))
        title.setProperty("class", "stepTitle")
        layout.addWidget(title)

        self.status_label = QLabel(_("Premi il microfono per iniziare."))
        self.status_label.setProperty("class", "stepDescription")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        note_frame = QFrame()
        note_frame.setProperty("class", "speechNote")
        note_layout = QVBoxLayout(note_frame)
        note_layout.setContentsMargins(12, 10, 12, 10)
        note_layout.setSpacing(5)
        google_note = QLabel(_("Dopo lo stop, l’audio viene inviato a Google Speech Recognition per la trascrizione."))
        google_note.setProperty("class", "muted")
        google_note.setWordWrap(True)
        note_layout.addWidget(google_note)
        system_note = QLabel(system_dictation_hint())
        system_note.setProperty("class", "muted")
        system_note.setWordWrap(True)
        note_layout.addWidget(system_note)
        layout.addWidget(note_frame)

        self.preview = QPlainTextEdit()
        self.preview.setPlaceholderText(_("La trascrizione apparirà qui. Potrai correggerla prima di inserirla."))
        self.preview.textChanged.connect(self._sync_insert_state)
        layout.addWidget(self.preview, 1)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.start_button = QPushButton("🎙")
        self.start_button.setProperty("role", "icon")
        self.start_button.setAccessibleName(_("Avvia dettatura"))
        self.start_button.setToolTip(_("Avvia dettatura"))
        self.start_button.clicked.connect(self.start_recording)
        controls.addWidget(self.start_button)

        self.stop_button = QPushButton(_("Interrompi e trascrivi"))
        self.stop_button.clicked.connect(self.stop_and_transcribe)
        self.stop_button.setEnabled(False)
        controls.addWidget(self.stop_button)
        controls.addStretch(1)

        cancel_button = QPushButton(_("Annulla"))
        cancel_button.clicked.connect(self.reject)
        controls.addWidget(cancel_button)

        self.insert_button = QPushButton(_("Inserisci nel task"))
        self.insert_button.setProperty("role", "primary")
        self.insert_button.clicked.connect(self.accept)
        self.insert_button.setEnabled(False)
        controls.addWidget(self.insert_button)
        layout.addLayout(controls)

    def transcript(self) -> str:
        return self.preview.toPlainText().strip()

    def _sync_insert_state(self) -> None:
        self.insert_button.setEnabled(bool(self.transcript()) and not self.recorder.is_recording())

    def start_recording(self) -> None:
        try:
            self.recorder.start()
        except SpeechToTextError as exc:
            QMessageBox.critical(self, _("Microfono non disponibile"), str(exc))
            return
        self.status_label.setText(_("Registrazione in corso… parla ora."))
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.insert_button.setEnabled(False)

    def stop_and_transcribe(self) -> None:
        self.stop_button.setEnabled(False)
        self.status_label.setText(_("Trascrizione in corso…"))
        try:
            audio = self.recorder.stop()
        except SpeechToTextError as exc:
            self._transcription_failed(str(exc))
            return
        threading.Thread(
            target=self._transcribe_worker,
            args=(audio,),
            daemon=True,
            name="speech-to-text",
        ).start()

    def _transcribe_worker(self, audio: bytes) -> None:
        try:
            text = transcribe_google(audio, self.recorder.sample_rate, self.language)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.completed.emit(text)

    def _transcription_ready(self, text: str) -> None:
        self.preview.setPlainText(text)
        self.status_label.setText(_("Trascrizione completata. Puoi correggerla prima di inserirla."))
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._sync_insert_state()

    def _transcription_failed(self, message: str) -> None:
        self.status_label.setText(_("Trascrizione non riuscita."))
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._sync_insert_state()
        QMessageBox.warning(self, _("Dettatura"), message)

    def reject(self) -> None:
        self.recorder.cancel()
        super().reject()

    def closeEvent(self, event) -> None:
        self.recorder.cancel()
        super().closeEvent(event)
