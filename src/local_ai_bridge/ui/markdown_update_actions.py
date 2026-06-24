from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.services.markdown_exchange import parse_markdown_response
from local_ai_bridge.services.temp_storage import latest_markdown_file, managed_subdir
from local_ai_bridge.services.text_file_operations import inspect_text_file_operations


class MarkdownUpdateActionsMixin:

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

    def _set_text_update_path(self, path: Path) -> None:
        selected = path.expanduser()
        self.text_update_path_edit.setText(str(selected))
        self.text_update_path_edit.setToolTip(str(selected))
        self._show_status(
            _('File Markdown di aggiornamento selezionato: {name}').format(
                name=selected.name
            )
        )

    def choose_text_update_file(self) -> None:
        selected, _selected_filter = QFileDialog.getOpenFileName(
            self,
            _('Scegli il file Markdown di aggiornamento'),
            str(self._markdown_download_directory()),
            _('File Markdown o testo (*.md *.txt)'),
        )
        if selected:
            self._set_text_update_path(Path(selected))

    def _read_text_update_file(self, path: Path) -> str:
        source = path.expanduser().resolve(strict=True)
        if not source.is_file() or source.suffix.casefold() not in {'.md', '.txt'}:
            raise ValueError(
                _('Seleziona un file di aggiornamento con estensione .md o .txt.')
            )
        raw = source.read_bytes()
        if not raw:
            raise ValueError(_('Il file Markdown di aggiornamento è vuoto.'))
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError(
                _('Il file Markdown di aggiornamento non è codificato in UTF-8.')
            ) from exc
        if not text.strip():
            raise ValueError(_('Il file Markdown di aggiornamento è vuoto.'))
        return text

    def analyze_selected_text_update_file(self) -> None:
        raw_path = self.text_update_path_edit.text().strip()
        if not raw_path:
            QMessageBox.warning(
                self,
                _('File Markdown richiesto'),
                _('Seleziona o trascina prima un file .md o .txt.'),
            )
            return
        try:
            text = self._read_text_update_file(Path(raw_path))
        except Exception as exc:
            QMessageBox.critical(self, _('Lettura file di aggiornamento fallita'), str(exc))
            return
        self.text_result_edit.setPlainText(text)
        self._inspect_text_update_text(text)

    def paste_text_result_from_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        self.text_result_edit.setPlainText(text)
        self.text_result_edit.setFocus()
        self._show_status(_('Risposta Markdown incollata dagli appunti.'))

    def _inspect_text_update_text(self, text: str) -> bool:
        workspace = self._require_workspace()
        if not workspace:
            return False
        if not text.strip():
            QMessageBox.warning(
                self,
                _('Risposta Markdown richiesta'),
                _('Incolla prima le operazioni complete restituite dall’AI.'),
            )
            return False
        try:
            snapshot = (
                managed_subdir(self.settings.temp_directory, 'patches')
                / 'latest_text_file_operations.md'
            )
            snapshot.write_text(text, encoding='utf-8')
            plan = inspect_text_file_operations(workspace, text)
            self.display_plan(plan)
            summary = plan.metadata.get('import_summary', {})
            self._show_status(
                _(
                    'File Markdown analizzato: {files} file, {create} creati, {replace} sostituiti, {delete} eliminati.'
                ).format(
                    files=summary.get('files', len(plan.changes)),
                    create=summary.get('create', 0),
                    replace=summary.get('replace', 0),
                    delete=summary.get('delete', 0),
                )
            )
            return True
        except Exception as exc:
            QMessageBox.critical(self, _('File Markdown di aggiornamento non valido'), str(exc))
            return False

    def prepare_text_result_plan(self) -> None:
        self._inspect_text_update_text(self.text_result_edit.toPlainText())

    def paste_gemini_result_from_clipboard(self) -> None:
        self.paste_text_result_from_clipboard()

    def prepare_gemini_plan(self) -> None:
        self.prepare_text_result_plan()
