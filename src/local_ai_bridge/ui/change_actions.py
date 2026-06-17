from __future__ import annotations
from local_ai_bridge.i18n import tr as _
from pathlib import Path
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem
from local_ai_bridge.core.models import ChangePlan
from local_ai_bridge.services.archive import inspect_zip
from local_ai_bridge.services.temp_storage import latest_zip_file, managed_subdir, stage_import_zip
from local_ai_bridge.services.testing import format_test_results, run_detected_tests, test_results_to_dicts, test_summary


class DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document)
        self.added = QTextCharFormat()
        self.added.setBackground(QColor(46, 125, 50, 55))
        self.removed = QTextCharFormat()
        self.removed.setBackground(QColor(198, 40, 40, 55))
        self.hunk = QTextCharFormat()
        self.hunk.setBackground(QColor(21, 101, 192, 40))

    def highlightBlock(self, text: str) -> None:
        if text.startswith('+') and not text.startswith('+++'):
            self.setFormat(0, len(text), self.added)
        elif text.startswith('-') and not text.startswith('---'):
            self.setFormat(0, len(text), self.removed)
        elif text.startswith('@@'):
            self.setFormat(0, len(text), self.hunk)

class ChangeActionsMixin:

    def choose_update_zip_directory(self) -> None:
        current = self.settings.update_zip_directory.strip()
        start = current if current and Path(current).is_dir() else str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, _('Seleziona la cartella degli ZIP delle modifiche'), start)
        if not selected:
            return
        self.settings.update_zip_directory = selected
        self.settings_store.save(self.settings)
        self.update_zip_directory_edit.setText(selected)
        settings_edit = getattr(self, 'settings_update_zip_directory_edit', None)
        if settings_edit is not None:
            settings_edit.setText(selected)
        self.simple_patch_directory_button.setVisible(False)
        self._show_status(f'Cartella ZIP delle modifiche impostata: {selected}')
        if self.settings.simple_mode:
            QMessageBox.information(
                self,
                _('Cartella aggiornamenti impostata'),
                _('Puoi cambiare in qualsiasi momento la cartella da Preferenze.'),
            )

    def apply_latest_zip(self) -> None:
        configured = self.settings.update_zip_directory.strip()
        if not configured:
            QMessageBox.warning(self, _('Cartella ZIP non impostata'), _('Imposta prima la cartella che contiene gli ZIP delle modifiche.'))
            return
        latest = latest_zip_file(configured)
        if latest is None:
            QMessageBox.warning(self, _('Nessuno ZIP trovato'), f'Nella cartella configurata non è presente alcun file ZIP:\n{configured}')
            return
        self.zip_path_edit.setText(str(latest))
        self._show_status(f'Ultimo ZIP selezionato: {latest.name}')
        self.inspect_selected_zip()

    def choose_zip(self) -> None:
        start = managed_subdir(self.settings.temp_directory, 'imports')
        selected, _selected_filter = QFileDialog.getOpenFileName(self, _('Seleziona ZIP'), str(start), 'ZIP (*.zip)')
        if selected:
            self.zip_path_edit.setText(selected)
            self.inspect_selected_zip()

    def inspect_selected_zip(self) -> None:
        workspace = self._require_workspace()
        raw = self.zip_path_edit.text().strip()
        if not workspace or not raw:
            QMessageBox.warning(self, _('ZIP richiesto'), _('Seleziona o trascina un archivio ZIP.'))
            return

        def inspect_staged():
            staged = stage_import_zip(Path(raw), self.settings.temp_directory)
            return (staged, inspect_zip(workspace, staged))

        def show_staged(result):
            staged, plan = result
            self.zip_path_edit.setText(str(staged))
            if self.settings.simple_mode:
                self.current_plan = plan
                self.apply_current_plan()
            else:
                self.display_plan(plan)
        self._run_background(inspect_staged, show_staged, _('Analisi sicura dello ZIP...'))

    def display_plan(self, plan: ChangePlan) -> None:
        self.current_plan = plan
        if not hasattr(self, '_diff_highlighter'):
            self._diff_highlighter = DiffHighlighter(self.diff_edit.document())
        self.plan_table.setRowCount(len(plan.changes))
        for row, change in enumerate(plan.changes):
            values = (change.target, change.kind, str(change.size), (change.new_sha256 or '-')[:16])
            for column, value in enumerate(values):
                self.plan_table.setItem(row, column, QTableWidgetItem(value))
        warning_text = 'AVVISI:\n- ' + '\n- '.join(plan.warnings) + '\n\n' if plan.warnings else ''
        commit_message = plan.metadata.get('commit_message')
        commit_text = f"{_('Suggerimento commit incluso nello ZIP:')}\n{commit_message}\n\n" if commit_message else ''
        self.diff_edit.setPlainText(warning_text + commit_text + plan.diff)
        self.apply_button.setEnabled(True)
        self.tabs.setCurrentWidget(self.changes_tab)
        self._show_status(f'Piano pronto: {len(plan.changes)} file. Nessuna modifica ancora applicata.')

    def apply_current_plan(self) -> None:
        if self.current_plan is None:
            return
        if self.settings.simple_mode and self.settings.gemini_drive_enabled:
            names = '\n'.join((f'• {item.target}' for item in self.current_plan.changes[:20]))
            if len(self.current_plan.changes) > 20:
                names += f'\n• ... e altri {len(self.current_plan.changes) - 20} file'
            answer = QMessageBox.question(
                self,
                _('Applica piano'),
                _('Hai controllato l’anteprima? Verrà creato un backup e saranno modificati questi file:')
                + f'\n\n{names}\n\n'
                + _('Procedere con l’applicazione?'),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
        elif self.settings.simple_mode:
            answer = QMessageBox.question(
                self,
                _('Applica aggiornamento'),
                _("Vuoi applicare l'aggiornamento?"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
        else:
            names = '\n'.join((f'• {item.target}' for item in self.current_plan.changes[:20]))
            if len(self.current_plan.changes) > 20:
                names += f'\n• ... e altri {len(self.current_plan.changes) - 20} file'
            answer = QMessageBox.question(
                self,
                _('Conferma applicazione'),
                f'Verrà creato un backup persistente e applicato questo piano:\n\n{names}\n\nProcedere?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
        if answer == QMessageBox.Yes:
            plan = self.current_plan
            self._run_background(lambda: self.apply_service.apply(plan), self._after_apply, _('Applicazione transazionale in corso...'))

    def _after_apply(self, record) -> None:
        self._show_status(f'Applicazione completata. Sessione: {record.session_id}')
        self._refresh_sessions()
        if self.settings.simple_mode:
            workspace = Path(record.workspace)
            self._run_background(
                lambda: (record, run_detected_tests(workspace)),
                self._after_post_apply_tests,
                _('Verifica post-applicazione in corso...'),
            )
            return
        answer = QMessageBox.question(
            self,
            _('Applicazione completata'),
            f'File applicati: {len(record.files)}\nSessione backup: {record.session_id}'
            '\n\nEseguire ora i controlli e i test rilevati?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            workspace = Path(record.workspace)
            self.tabs.setCurrentIndex(2)
            self._run_background(
                lambda: (record, run_detected_tests(workspace)),
                self._after_post_apply_tests,
                _('Verifica post-applicazione in corso...'),
            )
        else:
            self.tabs.setCurrentIndex(3)

    def _after_post_apply_tests(self, payload) -> None:
        record, results = payload
        updated = self.session_manager.save_test_results(record, test_results_to_dicts(results))
        self._refresh_sessions()
        summary = test_summary(results)
        self._show_status(f'Verifica post-applicazione completata: {summary}.')
        if self.settings.simple_mode:
            failed = any(result.status in {'failed', 'timeout', 'error'} for result in results)
            unavailable = any(result.status == 'unavailable' for result in results)
            if failed:
                QMessageBox.warning(
                    self,
                    _('Aggiornamento applicato con avvisi'),
                    _('L’aggiornamento è stato applicato, ma uno o più controlli non sono stati superati. Apri la modalità avanzata per vedere i dettagli.'),
                )
            elif unavailable:
                QMessageBox.information(
                    self,
                    _('Aggiornamento completato'),
                    _('Aggiornamento applicato. Alcuni controlli opzionali non erano disponibili e sono stati saltati.'),
                )
            else:
                QMessageBox.information(
                    self,
                    _('Aggiornamento completato'),
                    _('Aggiornamento applicato correttamente.'),
                )
            return
        self.test_output.setPlainText(format_test_results(results))
        QMessageBox.information(
            self,
            _('Verifica post-applicazione'),
            f'Sessione: {updated.session_id}\nRisultato: {summary}',
        )

    def rollback_latest(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        answer = QMessageBox.question(self, _('Conferma rollback'), _("Ripristinare l'ultimo batch applicato a questo workspace?"), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self._run_background(lambda: self.apply_service.rollback_latest(workspace), self._after_rollback, _('Rollback in corso...'))

    def _after_rollback(self, record) -> None:
        QMessageBox.information(self, _('Rollback completato'), f'Sessione ripristinata: {record.session_id}')
        self._refresh_sessions()
        self._show_status(_('Rollback completato.'))

    def clear_plan(self) -> None:
        self.current_plan = None
        self.plan_table.setRowCount(0)
        self.diff_edit.clear()
        self.apply_button.setEnabled(False)
        self._show_status(_('Piano azzerato.'))
