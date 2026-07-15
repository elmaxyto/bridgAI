from __future__ import annotations

import re
from pathlib import Path

from local_ai_bridge.core.superpowers import referenced_superpower_ids
from local_ai_bridge.ui.superpower_dialog import SuperpowerDialog
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from local_ai_bridge.core.prompt_presets import compose_task_with_preset
from local_ai_bridge.i18n import tr as _
from local_ai_bridge.services.exporting import parse_download_requests
from local_ai_bridge.services.markdown_exchange import export_files_to_markdown
from local_ai_bridge.services.patching import (
    inspect_full_file,
    inspect_gemini_response,
    inspect_patch,
)
from local_ai_bridge.services.speech_to_text import merge_task_text
from local_ai_bridge.services.temp_storage import managed_subdir
from local_ai_bridge.services.text_file_operations import inspect_text_file_operations
from local_ai_bridge.ui.markdown_update_actions import MarkdownUpdateActionsMixin
from local_ai_bridge.ui.speech_dialog import SpeechDialog

LEGACY_PATCH_MARKER = re.compile(r'<{7}\s*SEARCH', re.IGNORECASE)
GEMINI_URL = 'https://gemini.google.com/'


def gemini_drive_warning_required(enabled: bool) -> bool:
    return not enabled


class WorkflowActionsMixin(MarkdownUpdateActionsMixin):

    def _gemini_drive_directory(self) -> Path | None:
        if not self.settings.gemini_drive_enabled:
            return None
        raw_path = self.settings.gemini_drive_path.strip()
        if not raw_path:
            QMessageBox.warning(self, _('Cartella Google Drive richiesta'), _('Seleziona una cartella Google Drive nella scheda Impostazioni.'))
            return None
        directory = Path(raw_path).expanduser()
        if not directory.is_dir():
            QMessageBox.warning(self, _('Cartella Google Drive non disponibile'), f'La cartella configurata non esiste o non è accessibile:\n{directory}')
            return None
        return directory

    def open_speech_dialog(self) -> None:
        dialog = SpeechDialog(self)
        if dialog.exec() != SpeechDialog.Accepted:
            return
        transcript = dialog.transcript()
        if transcript:
            self.task_edit.setPlainText(merge_task_text(self.task_edit.toPlainText(), transcript))
            self.task_edit.setFocus()
            self._show_status(_('Trascrizione inserita nel task.'))

    def choose_superpowers(self) -> None:
        workspace = Path(self.settings.last_workspace) if self.settings.last_workspace else None
        current = set(referenced_superpower_ids(self.task_edit.toPlainText()))
        dialog = SuperpowerDialog(workspace, current, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_superpower_ids()
        text = self.task_edit.toPlainText()
        lines = [line for line in text.splitlines() if not line.strip().lower().startswith(("@superpower:", "@superpotere:"))]
        if selected:
            lines.extend(f"@superpower:{item}" for item in selected)
        self.task_edit.setPlainText("\n".join(lines).strip())
        self.superpower_summary.setText(
            _('{count} superpoteri selezionati').format(count=len(selected)) if selected
            else _('Nessun superpotere selezionato')
        )

    def generate_report(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        task = compose_task_with_preset(
            self.task_edit.toPlainText(),
            self.prompt_preset_combo.currentData(),
        )
        self.report_button.setEnabled(False)
        self.report_button.setText(_('Generazione...'))
        self.report_edit.setPlaceholderText(_('Scansione del progetto in corso...'))
        self._run_background(lambda: self.registry.execute('report.generate', self._context(), task=task), self._handle_report_result, _('Generazione Super-Report...'), self._report_finished)

    def _handle_report_result(self, result) -> None:
        self._handle_skill_text_result(result, self.report_edit)
        if not result.ok:
            return

        extension_queued = (
            False
            if self.settings.markdown_exchange_mode
            else self.queue_report_with_browser_extension(self.report_edit.toPlainText())
        )

        if self.settings.simple_mode:
            if extension_queued:
                message = _(
                    'La richiesta è stata affidata all’estensione Chrome. '
                    'I pulsanti e il flusso manuale restano comunque disponibili.'
                )
            elif self.settings.textual_file_operations_mode:
                message = _(
                    'Istruzioni copiate. L’AI dovrà restituire un file Markdown di aggiornamento da caricare nel passaggio 3.'
                )
            elif self.settings.markdown_exchange_mode:
                message = _(
                    'Istruzioni copiate. Le richieste #scarica verranno esportate come Markdown.'
                )
            else:
                message = _('Istruzioni per AI copiate. Incollale nella tua AI preferita.')
            QMessageBox.information(
                self,
                _('Istruzioni per AI esterna'),
                message,
            )
        if not extension_queued:
            self._show_status(_('Super-Report generato.'))

    def _report_finished(self) -> None:
        self.report_button.setEnabled(True)
        self.report_button.setText(
            _('Prepara per l’AI') if self.settings.simple_mode else _('Genera Super-Report')
        )

    def copy_report(self) -> None:
        text = self.report_edit.toPlainText()
        if not text:
            QMessageBox.information(self, _('Report'), _('Genera prima il Super-Report.'))
            return
        QApplication.clipboard().setText(text)
        self._show_status(_('Report copied negli appunti.'))

    def save_report(self) -> None:
        text = self.report_edit.toPlainText()
        workspace = self._require_workspace()
        if not workspace or not text:
            QMessageBox.information(self, _('Report'), _('Genera prima il Super-Report.'))
            return
        if self.settings.gemini_drive_enabled and not self.settings.markdown_exchange_mode:
            drive_directory = self._gemini_drive_directory()
            if drive_directory is None:
                return
            destination = drive_directory / 'AI_SUPER_REPORT.md'
            destination.write_text(text, encoding='utf-8')
            self._show_status(_('Salvato nella cartella Google Drive'))
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(self, _('Salva Super-Report'), str(workspace / 'AI_SUPER_REPORT.md'), _('Markdown (*.md);;Tutti i file (*)'))
        if destination:
            Path(destination).write_text(text, encoding='utf-8')
            self._show_status(f'Report salvato: {destination}')

    def _external_ai_url(self, url: str) -> str:
        return url

    def _open_web(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def open_ai_page(self, url: str) -> None:
        self._open_web(self._external_ai_url(url))

    def open_external_ai(self, url: str) -> None:
        text = self.report_edit.toPlainText()
        if not text:
            QMessageBox.information(self, _('Report'), _('Genera prima il Super-Report.'))
            return
        QApplication.clipboard().setText(text)
        self.open_ai_page(url)
        self._show_status(_('Istruzioni copiate: incollale nella chat appena aperta.'))

    def open_gemini(self) -> None:
        if not self.settings.markdown_exchange_mode:
            if gemini_drive_warning_required(self.settings.gemini_drive_enabled):
                QMessageBox.information(
                    self,
                    _('Google Drive richiesto per gli ZIP di Gemini'),
                    _(
                        'Per inviare ZIP a Gemini abilita Google Drive nelle Impostazioni, oppure scegli Markdown come formato dei file richiesti.'
                    ),
                )
                return
            if self._gemini_drive_directory() is None:
                return
        copied_instructions = False
        if self.settings.simple_mode:
            text = self.report_edit.toPlainText()
            if not text:
                QMessageBox.information(self, _('Report'), _('Genera prima il Super-Report.'))
                return
            QApplication.clipboard().setText(text)
            copied_instructions = True
        self._open_web(GEMINI_URL)
        self._show_status(
            _('Istruzioni copiate: incollale nella chat appena aperta.')
            if copied_instructions
            else _('Gemini aperto.')
        )

    def open_download_folder(self) -> None:
        directory = managed_subdir(self.settings.temp_directory, 'exports')
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
            QMessageBox.warning(self, _('Apertura cartella non riuscita'), f'Non è stato possibile aprire la cartella:\n{directory}')
            return
        self._show_status(f'Cartella #scarica aperta: {directory}')

    def paste_response_from_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        self.response_edit.setPlainText(text)
        self.response_edit.setFocus()
        self._show_status(_('Risposta incollata dagli appunti.'))

    def analyze_response(self) -> None:
        text = self.response_edit.toPlainText()
        requested = parse_download_requests(text)
        if requested:
            QMessageBox.information(
                self,
                _('Analisi risposta'),
                'File richiesti:\n- ' + '\n- '.join(requested),
            )
            return

        if self.settings.textual_file_operations_mode:
            workspace = self._require_workspace()
            if not workspace:
                return
            try:
                snapshot = (
                    managed_subdir(self.settings.temp_directory, 'patches')
                    / 'latest_text_file_operations.txt'
                )
                snapshot.write_text(text, encoding='utf-8')
                plan = inspect_text_file_operations(workspace, text)
                self.display_plan(plan)
                summary = plan.metadata.get('import_summary', {})
                self._show_status(
                    _(
                        'Operazioni file analizzate: {files} file, {create} creati, {replace} sostituiti, {delete} eliminati.'
                    ).format(
                        files=summary.get('files', len(plan.changes)),
                        create=summary.get('create', 0),
                        replace=summary.get('replace', 0),
                        delete=summary.get('delete', 0),
                    )
                )
            except Exception as exc:
                QMessageBox.critical(self, _('Risposta strutturata non valida'), str(exc))
            return

        if 'BRIDGAI:FILE' in text.upper():
            self._inspect_markdown_response_text(text)
            return

        if LEGACY_PATCH_MARKER.search(text):
            workspace = self._require_workspace()
            if not workspace:
                return
            try:
                target = self.target_edit.text().strip()
                plan = (
                    inspect_patch(workspace, target, text)
                    if target
                    else inspect_gemini_response(workspace, text)
                )
                self.display_plan(plan)
            except Exception as exc:
                QMessageBox.critical(self, _('Patch non valida'), str(exc))
            return

        QMessageBox.information(
            self,
            _('Analisi risposta'),
            _(
                'Nessuna richiesta #scarica o operazione su file completi rilevata. Verifica il formato selezionato nelle Impostazioni.'
            ),
        )

    def _export_requested_files_as_markdown(self, workspace: Path, requested: list[str]) -> None:
        try:
            destination = export_files_to_markdown(
                workspace,
                requested,
                managed_subdir(self.settings.temp_directory, 'exports'),
            )
            markdown = destination.read_text(encoding='utf-8')
            QApplication.clipboard().setText(markdown)
        except Exception as exc:
            QMessageBox.critical(self, _('Esportazione Markdown fallita'), str(exc))
            return
        if self.settings.simple_mode:
            QMessageBox.information(
                self,
                _('Markdown pronto'),
                _('Il Markdown è pronto e sostituirà quello precedente dello stesso progetto. Premi OK per aprire la cartella.\n\n{path}').format(path=destination),
            )
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(destination.parent))):
                QMessageBox.warning(
                    self,
                    _('Apertura cartella non riuscita'),
                    f'Non è stato possibile aprire la cartella:\n{destination.parent}',
                )
        else:
            QMessageBox.information(
                self,
                _('Markdown pronto'),
                _('Il documento Markdown è stato salvato e copiato negli appunti:\n{path}').format(path=destination),
            )
        self._show_status(_('File richiesti esportati come Markdown: {path}').format(path=destination))

    def export_requested_files(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        requested = parse_download_requests(self.response_edit.toPlainText())
        if not requested:
            QMessageBox.warning(self, '#scarica', _('Nessuna riga #scarica rilevata nella risposta.'))
            return
        if self.settings.markdown_exchange_mode:
            self._export_requested_files_as_markdown(workspace, requested)
            return
        if self.settings.gemini_drive_enabled:
            drive_directory = self._gemini_drive_directory()
            if drive_directory is None:
                return
            destination = str(drive_directory / f'{workspace.name}_ai_context.zip')
        elif self.settings.simple_mode:
            destination = str(managed_subdir(self.settings.temp_directory, 'exports') / f'{workspace.name}_ai_context.zip')
        else:
            destination, _selected_filter = QFileDialog.getSaveFileName(self, _('Salva ZIP dei file richiesti'), str(managed_subdir(self.settings.temp_directory, 'exports') / f'{workspace.name}_ai_context.zip'), 'ZIP (*.zip)')
            if not destination:
                return
            if not destination.lower().endswith('.zip'):
                destination += '.zip'
        self._run_background(lambda: self.registry.execute('files.export', self._context(), requested=requested, destination=destination), self._handle_export_result, _('Creazione ZIP di contesto...'))

    def prepare_patch(self) -> None:
        workspace = self._require_workspace()
        target = self.target_edit.text().strip()
        if not workspace or not target:
            QMessageBox.warning(self, _('Target richiesto'), _("Indica il file target o fai doppio clic nell'albero."))
            return
        try:
            patch_text = self.response_edit.toPlainText()
            snapshot = managed_subdir(self.settings.temp_directory, 'patches') / 'latest_search_replace.patch'
            snapshot.write_text(patch_text, encoding='utf-8')
            self.display_plan(inspect_patch(workspace, target, patch_text))
        except Exception as exc:
            QMessageBox.critical(self, _('Patch non valida'), str(exc))

    def prepare_full_file(self) -> None:
        workspace = self._require_workspace()
        target = self.target_edit.text().strip()
        if not workspace or not target:
            QMessageBox.warning(self, _('Target richiesto'), _('Indica il percorso relativo del file target.'))
            return
        try:
            content = self.response_edit.toPlainText()
            snapshot = managed_subdir(self.settings.temp_directory, 'patches') / 'latest_full_file.txt'
            snapshot.write_text(content, encoding='utf-8')
            self.display_plan(inspect_full_file(workspace, target, content))
        except Exception as exc:
            QMessageBox.critical(self, _('Contenuto non valido'), str(exc))

    def _handle_export_result(self, result) -> None:
        if not result.ok:
            QMessageBox.critical(self, _('Esportazione fallita'), result.message)
            return
        path = Path(result.data)
        if self.settings.gemini_drive_enabled:
            QMessageBox.information(
                self,
                _('ZIP pronto nella cartella Google Drive'),
                _(
                    'Attendi la sincronizzazione del client Google Drive, poi in Gemini premi “+”, scegli “Aggiungi da Drive”, apri “Recenti” e seleziona il file più recente:\n{name}'
                ).format(name=path.name),
            )
            self._show_status(_('Salvato nella cartella Google Drive'))
            return
        if self.settings.simple_mode:
            QMessageBox.information(
                self,
                _('File pronto'),
                _('Il file è pronto. Premi OK per aprire la cartella.'),
            )
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent))):
                QMessageBox.warning(
                    self,
                    _('Apertura cartella non riuscita'),
                    f'Non è stato possibile aprire la cartella:\n{path.parent}',
                )
        else:
            QMessageBox.information(self, _('ZIP creato'), f'Archivio creato:\n{path}')
        self._show_status(str(path))
