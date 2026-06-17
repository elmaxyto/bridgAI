from __future__ import annotations
from local_ai_bridge.i18n import tr as _
from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox
from local_ai_bridge.services.system import build_restart_command

class SystemActionsMixin:
    """Desktop actions that interact with the host operating system."""

    def open_workspace_folder(self) -> None:
        workspace = self._require_workspace()
        if workspace is None:
            return
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(workspace)))
        if not opened:
            QMessageBox.warning(self, _('Apertura cartella fallita'), f'Il file manager di sistema non ha aperto il workspace:\n{workspace}')
            return
        self._show_status(f'Cartella workspace aperta: {workspace}')

    def restart_application(self) -> None:
        answer = QMessageBox.question(self, _('Riavvia BridgAI'), _('Vuoi chiudere e riavviare BridgAI adesso?'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.settings_store.save(self.settings)
        command = build_restart_command()
        result = QProcess.startDetached(command.program, command.arguments, command.working_directory)
        started = result[0] if isinstance(result, tuple) else bool(result)
        if not started:
            QMessageBox.critical(self, _('Riavvio fallito'), _('Non è stato possibile avviare una nuova istanza. Il programma corrente resterà aperto.'))
            return
        self._show_status(_('Riavvio in corso...'))
        QApplication.quit()
