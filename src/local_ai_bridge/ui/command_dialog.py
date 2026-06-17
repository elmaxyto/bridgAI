from __future__ import annotations
from local_ai_bridge.i18n import tr as _
from PySide6.QtCore import QProcess
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

class InteractiveCommandDialog(QDialog):
    """Piccolo terminale incorporato per i flussi interattivi di GitHub CLI."""

    def __init__(self, title: str, program: str, arguments: list[str], instructions: str, parent: QWidget | None=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 480)
        self.exit_code: int | None = None
        layout = QVBoxLayout(self)
        label = QLabel(instructions)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(_("L'output del comando apparirà qui..."))
        layout.addWidget(self.output, 1)
        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(_('Rispondi a un eventuale prompt e premi Invio'))
        self.input_edit.returnPressed.connect(self._send_input)
        input_row.addWidget(self.input_edit, 1)
        self.send_button = QPushButton(_('Invio'))
        self.send_button.clicked.connect(self._send_input)
        input_row.addWidget(self.send_button)
        layout.addLayout(input_row)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.close_button = QPushButton(_('Chiudi'))
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)
        self.process.start(program, arguments)

    def _read_output(self) -> None:
        chunk = bytes(self.process.readAllStandardOutput()).decode(errors='replace')
        if chunk:
            cursor = self.output.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(chunk)
            self.output.setTextCursor(cursor)
            self.output.ensureCursorVisible()

    def _send_input(self) -> None:
        text = self.input_edit.text()
        if self.process.state() == QProcess.NotRunning:
            return
        self.process.write((text + '\n').encode())
        self.input_edit.clear()

    def _finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._read_output()
        self.exit_code = exit_code
        message = '\n\nOperazione completata.' if exit_code == 0 else f'\n\nComando terminato con codice {exit_code}.'
        self.output.appendPlainText(message)
        self.input_edit.setEnabled(False)
        self.send_button.setEnabled(False)
        self.close_button.setEnabled(True)

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            self.output.appendPlainText(_('Impossibile avviare il comando. Verifica che GitHub CLI sia installata.'))
            self.input_edit.setEnabled(False)
            self.send_button.setEnabled(False)
            self.close_button.setEnabled(True)

    def reject(self) -> None:
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
        super().reject()
