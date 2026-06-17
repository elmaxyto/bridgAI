from __future__ import annotations
from local_ai_bridge.i18n import tr as _
from PySide6.QtWidgets import QInputDialog, QMessageBox, QPlainTextEdit, QTableWidgetItem
from local_ai_bridge.services.git import create_commit, generate_commit_message, git_diff, git_init, git_remotes, git_status

class ToolActionsMixin:

    def run_tests(self) -> None:
        if not self._require_workspace():
            return
        self._run_background(lambda: self.registry.execute('tests.run', self._context()), lambda result: self._handle_skill_text_result(result, self.test_output), _('Esecuzione controlli e test...'))

    def show_git_status(self) -> None:
        workspace = self._require_workspace()
        if workspace:
            self._run_background(lambda: git_status(workspace), self._show_tool_output, _('Lettura stato Git...'))

    def show_git_diff(self) -> None:
        workspace = self._require_workspace()
        if workspace:
            self._run_background(lambda: git_diff(workspace), self._show_tool_output, _('Lettura Git diff...'))

    def show_git_remotes(self) -> None:
        workspace = self._require_workspace()
        if workspace:
            self._run_background(lambda: git_remotes(workspace), self._show_tool_output, _('Lettura remote Git...'))

    def prepare_git_commit(self) -> None:
        workspace = self._require_workspace()
        if workspace is None:
            return

        def show_draft(message: str) -> None:
            edited, accepted = QInputDialog.getMultiLineText(
                self, _('Messaggio di commit'),
                _('Rivedi il messaggio. Solo dopo la conferma verranno eseguiti git add e git commit.'),
                message,
            )
            if not accepted or not edited.strip():
                return
            answer = QMessageBox.question(
                self, _('Conferma commit'),
                _('Tutte le modifiche correnti del workspace verranno aggiunte all’indice e incluse nel commit. Procedere?'),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                self._run_background(
                    lambda: create_commit(workspace, edited), self._show_tool_output, _('Creazione commit Git...')
                )

        self._run_background(
            lambda: generate_commit_message(workspace, self.session_manager),
            show_draft, _('Generazione messaggio di commit...')
        )

    def initialize_git_repository(self) -> None:
        workspace = self._require_workspace()
        if workspace is None:
            return
        answer = QMessageBox.question(self, _('Inizializza Git'), "Verrà creato il repository Git locale nel workspace.\n\nNessun file verrà aggiunto all'indice e nessun commit verrà creato. Continuare?")
        if answer != QMessageBox.Yes:
            return
        self._run_background(lambda: git_init(workspace), self._show_tool_output, _('Inizializzazione repository Git...'))

    def _show_tool_output(self, text: str) -> None:
        self.test_output.setPlainText(str(text))
        self._show_status(_('Operazione Git/GitHub completata.'))

    def _handle_skill_text_result(self, result, target: QPlainTextEdit) -> None:
        if not result.ok:
            QMessageBox.critical(self, _('Skill fallita'), result.message)
            return
        target.setPlainText(str(result.data))
        self._show_status(result.message)

    def _refresh_skills(self) -> None:
        specs = self.registry.list_specs()
        self.skills_table.setRowCount(len(specs))
        for row, spec in enumerate(specs):
            values = (spec.skill_id, spec.name, ', '.join(sorted(spec.permissions)), spec.description)
            for column, value in enumerate(values):
                self.skills_table.setItem(row, column, QTableWidgetItem(value))

    def _refresh_sessions(self) -> None:
        if not hasattr(self, 'sessions_table'):
            return
        records = list(self.session_manager.iter_for_workspace(self.workspace)) if self.workspace else []
        self._session_records = [record for _, record in records]
        self.sessions_table.setRowCount(len(records))
        for row, (_, record) in enumerate(records):
            test_state = self._session_test_state(record)
            values = (record.session_id, record.operation, record.status, str(len(record.files)), test_state, record.created_at)
            for column, value in enumerate(values):
                self.sessions_table.setItem(row, column, QTableWidgetItem(value))
        if not records and hasattr(self, 'session_details_edit'):
            self.session_details_edit.clear()

    def _session_test_state(self, record) -> str:
        if not record.test_results:
            return _('Non eseguiti')
        failures = sum(item.get('status') in {'failed', 'timeout', 'error'} for item in record.test_results)
        return _('Superati') if failures == 0 else f'{failures} non superati'

    def show_selected_session(self) -> None:
        row = self.sessions_table.currentRow()
        if row < 0 or row >= len(getattr(self, '_session_records', [])):
            return
        record = self._session_records[row]
        lines = [
            f'Sessione: {record.session_id}',
            f'Operazione: {record.operation}',
            f'Stato: {record.status}',
            f'Data: {record.created_at}',
            f'Origine: {record.source or "-"}',
            f'Messaggio commit: {record.commit_message or "-"}',
            '',
            f'File ({len(record.files)}):',
        ]
        for item in record.files:
            lines.append(f"- {item.get('action', 'write')}: {item.get('target', '?')}")
        lines.extend(['', 'Verifica post-applicazione:'])
        if not record.test_results:
            lines.append('- Non eseguita')
        else:
            for result in record.test_results:
                lines.append(
                    f"- {result.get('name', '?')}: {result.get('status', '?')} "
                    f"({float(result.get('duration_seconds', 0)):.1f}s)"
                )
        if record.error:
            lines.extend(['', f'Errore: {record.error}'])
        self.session_details_edit.setPlainText('\n'.join(lines))

    def _save_simple_mode(self, checked: bool) -> None:
        self.settings.simple_mode = checked
        self.settings_store.save(self.settings)
        self.apply_simple_mode()
        state = _('attivata') if checked else _('disattivata')
        self._show_status(f"{_('Modalità super semplice')} {state}.")
