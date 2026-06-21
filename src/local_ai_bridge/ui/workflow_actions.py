from __future__ import annotations
from local_ai_bridge.i18n import tr as _
import re
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from local_ai_bridge.services.exporting import parse_download_requests
from local_ai_bridge.services.markdown_exchange import (
    export_files_to_markdown,
    parse_markdown_response,
)
from local_ai_bridge.core.prompt_presets import compose_task_with_preset
from local_ai_bridge.services.patching import (
    inspect_full_file,
    inspect_gemini_response,
    inspect_patch,
    parse_gemini_patch_response,
)
from local_ai_bridge.services.temp_storage import latest_markdown_file, managed_subdir
from local_ai_bridge.services.speech_to_text import merge_task_text
from local_ai_bridge.ui.speech_dialog import SpeechDialog
PATCH_MARKER = re.compile('<{7}\\s*SEARCH', re.IGNORECASE)
GEMINI_URL = 'https://gemini.google.com/'
GEMINI_REPORT_PROTOCOL = """
## Protocollo obbligatorio per Gemini

- Se ti servono file reali, rispondi prima con una sola riga `#scarica percorso/file1, percorso/file2`.
- Dopo che l’utente avrà allegato lo ZIP da Google Drive, non restituire uno ZIP di aggiornamento.
- Per ogni file da modificare scrivi una riga `FILE: percorso/relativo.ext`, seguita da uno o più blocchi:

```text
<<<<<<< SEARCH
testo esatto esistente
=======
testo sostitutivo
>>>>>>> REPLACE
```

- Ripeti `FILE: ...` prima dei blocchi del file successivo.
- Non omettere i percorsi e non usare patch abbreviate: BridgAI analizzerà localmente il testo e mostrerà il diff prima di applicarlo.
""".strip()


def gemini_drive_warning_required(enabled: bool) -> bool:
    return not enabled


class WorkflowActionsMixin:

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

        if self.settings.simple_mode and self.settings.gemini_drive_enabled:
            report = self.report_edit.toPlainText().rstrip()
            if GEMINI_REPORT_PROTOCOL not in report:
                self.report_edit.setPlainText(f'{report}\n\n{GEMINI_REPORT_PROTOCOL}\n')

        extension_queued = self.queue_report_with_browser_extension(
            self.report_edit.toPlainText()
        )

        if self.settings.simple_mode:
            if extension_queued:
                message = _(
                    'La richiesta è stata affidata all’estensione Chrome. '
                    'I pulsanti e il flusso manuale restano comunque disponibili.'
                )
            elif self.settings.gemini_drive_enabled:
                message = _('Istruzioni copiate. Ora premi “Continua su Gemini” e incollale nella chat.')
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
        if self.settings.simple_mode and self.settings.gemini_drive_enabled:
            self.report_button.setText(_('Prepara per Gemini'))
        else:
            self.report_button.setText(_('Prepara per l’AI') if self.settings.simple_mode else _('Genera Super-Report'))

    def copy_report(self) -> None:
        text = self.report_edit.toPlainText()
        if not text:
            QMessageBox.information(self, _('Report'), _('Genera prima il Super-Report.'))
            return
        QApplication.clipboard().setText(text)
        self._show_status(_('Report copiato negli appunti.'))

    def save_report(self) -> None:
        text = self.report_edit.toPlainText()
        workspace = self._require_workspace()
        if not workspace or not text:
            QMessageBox.information(self, _('Report'), _('Genera prima il Super-Report.'))
            return
        if self.settings.gemini_drive_enabled:
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

    def _open_web(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def open_external_ai(self, url: str) -> None:
        text = self.report_edit.toPlainText()
        if not text:
            QMessageBox.information(self, _('Report'), _('Genera prima il Super-Report.'))
            return
        QApplication.clipboard().setText(text)
        self._open_web(url)
        self._show_status(_('Istruzioni copiate: incollale nella chat appena aperta.'))

    def open_gemini(self) -> None:
        if gemini_drive_warning_required(self.settings.gemini_drive_enabled):
            QMessageBox.information(
                self,
                _('Google Drive richiesto per Gemini'),
                _('Per utilizzare Gemini in modo appropriato, abilita Google Drive nelle Impostazioni.'),
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

    def _markdown_download_directory(self) -> Path:
        configured = self.settings.update_zip_directory.strip()
        if configured:
            return Path(configured).expanduser()
        downloads = Path.home() / 'Downloads'
        return downloads if downloads.is_dir() else Path.home()

    def choose_markdown_download_directory(self) -> None:
        initial = self._markdown_download_directory()
        selected = QFileDialog.getExistingDirectory(
            self,
            _('Scegli la cartella dei Markdown scaricati'),
            str(initial),
        )
        if not selected:
            return
        self.settings.update_zip_directory = selected
        self.settings_store.save(self.settings)
        self._show_status(
            _('Cartella Markdown scaricati: {path}').format(path=selected)
        )

    def paste_markdown_result_from_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        self.markdown_result_edit.setPlainText(text)
        self.markdown_result_edit.setFocus()
        self._show_status(_('Risposta Markdown incollata dagli appunti.'))

    def _inspect_markdown_response_text(self, text: str) -> bool:
        workspace = self._require_workspace()
        if not workspace:
            return False
        if not text.strip():
            QMessageBox.warning(
                self,
                _('Risposta Markdown richiesta'),
                _('Incolla o seleziona prima il documento Markdown restituito dall’AI.'),
            )
            return False
        try:
            plan = parse_markdown_response(workspace, text)
            snapshot = managed_subdir(self.settings.temp_directory, 'patches') / 'latest_markdown_response.md'
            snapshot.write_text(text, encoding='utf-8')
            self.display_plan(plan)
        except Exception as exc:
            QMessageBox.critical(self, _('Risposta Markdown non valida'), str(exc))
            return False
        self._show_status(
            _('Risposta Markdown analizzata: {files} file.').format(files=len(plan.changes))
        )
        return True

    def prepare_pasted_markdown_response(self) -> None:
        self._inspect_markdown_response_text(self.markdown_result_edit.toPlainText())

    def _load_markdown_response(self, path: Path) -> None:
        try:
            source = path.expanduser().resolve(strict=True)
            if not source.is_file() or source.suffix.casefold() not in {'.md', '.markdown'}:
                raise ValueError(_('Il file selezionato non è un documento Markdown valido.'))
            text = source.read_text(encoding='utf-8-sig')
        except Exception as exc:
            QMessageBox.critical(self, _('Lettura Markdown fallita'), str(exc))
            return
        self.markdown_result_edit.setPlainText(text)
        if self._inspect_markdown_response_text(text):
            self._show_status(
                _('Markdown caricato da {path}. Controlla l’anteprima prima di applicare.').format(path=source)
            )

    def choose_markdown_response(self) -> None:
        selected, _selected_filter = QFileDialog.getOpenFileName(
            self,
            _('Scegli la risposta Markdown'),
            str(self._markdown_download_directory()),
            _('Markdown (*.md);;Tutti i file (*)'),
        )
        if selected:
            self._load_markdown_response(Path(selected))

    def apply_latest_markdown(self) -> None:
        directory = self._markdown_download_directory()
        latest = latest_markdown_file(directory)
        if latest is None:
            QMessageBox.warning(
                self,
                _('Nessun Markdown trovato'),
                _('Nessun file Markdown è stato trovato nella cartella:\n{path}').format(path=directory),
            )
            return
        self._load_markdown_response(latest)

    def paste_gemini_result_from_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        self.gemini_result_edit.setPlainText(text)
        self.gemini_result_edit.setFocus()
        self._show_status(_('Risposta Gemini incollata dagli appunti.'))

    def prepare_gemini_plan(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        text = self.gemini_result_edit.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, _('Risposta Gemini richiesta'), _('Incolla prima la risposta completa di Gemini.'))
            return
        try:
            snapshot = managed_subdir(self.settings.temp_directory, 'patches') / 'latest_gemini_response.txt'
            snapshot.write_text(text, encoding='utf-8')
            plan = inspect_gemini_response(workspace, text)
            self.display_plan(plan)
            summary = plan.metadata.get('import_summary', {})
            self._show_status(
                _('Risposta Gemini analizzata: {files} file, {blocks} blocchi, nessun blocco ignorato.').format(
                    files=summary.get('files', len(plan.changes)),
                    blocks=summary.get('blocks', plan.metadata.get('blocks', 0)),
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, _('Risposta Gemini non valida'), str(exc))

    def analyze_response(self) -> None:
        text = self.response_edit.toPlainText()
        if self.settings.markdown_exchange_mode and 'BRIDGAI:FILE' in text.upper():
            self._inspect_markdown_response_text(text)
            return

        requested = parse_download_requests(text)
        rows: list[str] = []
        if requested:
            rows.append('File richiesti:\n- ' + '\n- '.join(requested))
        if PATCH_MARKER.search(text):
            rows.append(_('Rilevata almeno una patch SEARCH/REPLACE.'))
        if not rows:
            rows.append(_('Nessun #scarica o blocco SEARCH/REPLACE rilevato. Puoi trattare il testo come file completo.'))
        QMessageBox.information(self, _('Analisi risposta'), '\n\n'.join(rows))

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
        self._show_status(_('Markdown Exchange esportato: {path}').format(path=destination))

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
