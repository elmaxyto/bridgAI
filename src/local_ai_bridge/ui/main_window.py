from __future__ import annotations
from local_ai_bridge.i18n import configure_language, tr as _
from datetime import datetime
from pathlib import Path
from typing import Callable
from PySide6.QtCore import QModelIndex, QThreadPool, QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QWidget,
)
from local_ai_bridge import __version__
from local_ai_bridge.core.models import ChangePlan
from local_ai_bridge.core.sessions import SessionManager
from local_ai_bridge.core.settings import AppSettings, SettingsStore, app_data_dir
from local_ai_bridge.core.skills import SkillContext, SkillRegistry
from local_ai_bridge.services.apply import ApplyService
from local_ai_bridge.web.launcher import stop_web_interface
from local_ai_bridge.skills.builtins import register_builtin_skills
from local_ai_bridge.ui.browser_extension_actions import BrowserExtensionActionsMixin
from local_ai_bridge.ui.change_actions import ChangeActionsMixin
from local_ai_bridge.ui.github_actions import GitHubActionsMixin
from local_ai_bridge.ui.layouts import build_central_ui
from local_ai_bridge.ui.recent_projects import RecentProjectsMixin
from local_ai_bridge.ui.theme import application_style
from local_ai_bridge.ui.system_actions import SystemActionsMixin
from local_ai_bridge.ui.settings_actions import SettingsActionsMixin
from local_ai_bridge.ui.tool_actions import ToolActionsMixin
from local_ai_bridge.ui.workflow_actions import WorkflowActionsMixin
from local_ai_bridge.ui.workers import FunctionWorker


SIMPLE_MODE_WIDTH = 800
SIMPLE_MODE_HEIGHT = 900


def _project_display_name(path: Path) -> str:
    return path.name or str(path)




def _validated_project_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError(_('Inserisci un nome per il nuovo progetto.'))
    if name in {'.', '..'} or '/' in name or '\\' in name:
        raise ValueError(_('Il nome del progetto non può contenere separatori di percorso.'))
    return name


def _reset_project_ui(window) -> None:
    """Clear project-specific inputs and previews when switching workspace."""
    for name in (
        'task_edit',
        'report_edit',
        'response_edit',
        'markdown_result_edit',
        'gemini_result_edit',
        'target_edit',
        'zip_path_edit',
        'diff_edit',
        'session_details_edit',
    ):
        widget = getattr(window, name, None)
        if widget is not None:
            widget.clear()

    plan_table = getattr(window, 'plan_table', None)
    if plan_table is not None:
        plan_table.setRowCount(0)

    preset_combo = getattr(window, 'prompt_preset_combo', None)
    if preset_combo is not None:
        preset_combo.setCurrentIndex(0)

    window.current_plan = None
    window._last_auto_copied_report = None
    window._browser_extension_seen_response_id = ''
    window._browser_extension_seen_update_path = ''
    pre_apply_summary = getattr(window, 'pre_apply_summary', None)
    if pre_apply_summary is not None:
        pre_apply_summary.setText(_('La checklist pre-applicazione apparirà dopo l’analisi del piano.'))

    apply_button = getattr(window, 'apply_button', None)
    if apply_button is not None:
        apply_button.setEnabled(False)


class MainWindow(WorkflowActionsMixin, BrowserExtensionActionsMixin, ChangeActionsMixin, SystemActionsMixin, SettingsActionsMixin, GitHubActionsMixin, ToolActionsMixin, RecentProjectsMixin, QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f'BridgAI {__version__}')
        self.resize(1380, 900)
        self.setAcceptDrops(True)
        self.settings_store = SettingsStore()
        self.settings: AppSettings = self.settings_store.load()
        self.apply_theme()
        configure_language(self.settings.language)
        self.workspace: Path | None = None
        self.current_plan: ChangePlan | None = None
        self._session_records = []
        self.thread_pool = QThreadPool.globalInstance()
        self._active_workers: list[FunctionWorker] = []
        self.web_process = None
        self.session_manager = SessionManager()
        self.apply_service = ApplyService(self.session_manager)
        self.registry = SkillRegistry()
        register_builtin_skills(self.registry)
        self._build_toolbar()
        self.setCentralWidget(build_central_ui(self))
        self.setStatusBar(QStatusBar(self))
        self._show_status(_('Pronto. Seleziona una cartella di lavoro.'))
        self._load_last_workspace()
        self._refresh_skills()
        self._refresh_sessions()
        self._browser_extension_seen_response_id = ''
        self._browser_extension_seen_update_path = ''
        self.browser_extension_timer = QTimer(self)
        self.browser_extension_timer.setInterval(1500)
        self.browser_extension_timer.timeout.connect(self.poll_browser_extension)
        self.browser_extension_timer.start()
        self.refresh_browser_extension_settings()
        QTimer.singleShot(0, self._start_browser_extension_if_enabled)
        self.apply_simple_mode()


    def apply_theme(self) -> None:
        self.setStyleSheet(application_style(bool(self.settings.dark_mode)))

    def apply_simple_mode(self) -> None:
        simple = bool(self.settings.simple_mode)
        gemini_simple = simple and bool(self.settings.gemini_drive_enabled)
        markdown_simple = simple and bool(self.settings.markdown_exchange_mode)
        if simple:
            if self.isFullScreen() or self.isMaximized():
                self.showNormal()
            self.resize(SIMPLE_MODE_WIDTH, SIMPLE_MODE_HEIGHT)
        else:
            self.showMaximized()
        self.project_panel.setVisible(not simple)
        changes_index = self.tabs.indexOf(self.changes_tab)
        tests_index = self.tabs.indexOf(self.tests_tab)
        publication_index = self.tabs.indexOf(self.publication_tab)
        advanced_index = self.tabs.indexOf(self.advanced_tab)
        if changes_index >= 0:
            self.tabs.setTabVisible(changes_index, not simple or gemini_simple or markdown_simple)
            self.tabs.setTabText(
                changes_index,
                _('Anteprima e applicazione')
                if gemini_simple or markdown_simple else _('2. ZIP, diff e applicazione'),
            )
        if publication_index >= 0:
            self.tabs.setTabVisible(publication_index, True)
            self.tabs.setTabText(publication_index, _('Pubblicazione'))
        for index in (tests_index, advanced_index):
            if index >= 0:
                self.tabs.setTabVisible(index, not simple)
        workflow_index = self.tabs.indexOf(self.workflow_tab)
        settings_index = self.tabs.indexOf(self.settings_tab)
        if workflow_index >= 0:
            self.tabs.setTabText(workflow_index, _('Assistente') if simple else _('1. Report e risposta AI'))
        if settings_index >= 0:
            self.tabs.setTabText(settings_index, _('Preferenze') if simple else _('Impostazioni'))
        self.simple_welcome.setVisible(simple)
        self.simple_subtitle.setVisible(simple)
        self.simple_finish_hint.setVisible(simple and not markdown_simple)
        if gemini_simple:
            finish_hint = _('Dopo la creazione dello ZIP, in Gemini premi “+”, scegli “Aggiungi da Drive”, apri “Recenti” e seleziona il file più recente.')
        elif markdown_simple:
            finish_hint = _('3  Carica il file Markdown nell’AI, incolla qui il documento modificato e premi “Analizza risposta”. Controlla sempre l’anteprima prima di applicare.')
        else:
            finish_hint = _('3  Quando ricevi uno ZIP dall’AI, salvalo nella cartella scelta e premi “Applica aggiornamento”. Prima dell’applicazione verrà sempre mostrata un’anteprima.')
        self.simple_finish_hint.setText(finish_hint)
        self.report_edit.setVisible(not simple)
        self.prompt_preset_label.setVisible(not simple)
        self.prompt_preset_combo.setVisible(not simple)
        for button in self.report_extra_buttons:
            button.setVisible(not simple)
        self.simple_chatgpt_button.setVisible(simple and not gemini_simple)
        self.simple_claude_button.setVisible(simple and not gemini_simple)
        self.simple_gemini_button.setVisible(gemini_simple)
        if gemini_simple:
            response_title = _('Incolla la richiesta di file di Gemini')
            response_description = _('Copia la risposta con la riga #scarica, poi prepara lo ZIP da aggiungere alla chat tramite Google Drive.')
            response_placeholder = _('Incolla qui la risposta di Gemini che contiene #scarica...')
        elif markdown_simple:
            response_title = _('Incolla la richiesta di file dell’AI')
            response_description = _('Copia la risposta con la riga #scarica, poi prepara il Markdown da caricare nella chat.')
            response_placeholder = _('Incolla qui la risposta dell’AI che contiene #scarica...')
        else:
            response_title = _('Incolla la risposta dell’AI')
            response_description = _('Torna qui e incolla tutto il messaggio ricevuto, senza modificarlo.')
            response_placeholder = _('Incolla qui la risposta completa dell’AI...')
        self.response_step_header.title_label.setText(response_title)
        self.response_step_header.description_label.setText(response_description)
        self.response_edit.setPlaceholderText(response_placeholder)
        self.simple_prepare_files_button.setText(
            _('Prepara ZIP su Google Drive')
            if gemini_simple else _('Prepara Markdown')
            if markdown_simple else _('Prepara i file richiesti')
        )
        self.gemini_result_group.setVisible(gemini_simple)
        self.markdown_result_group.setVisible(markdown_simple)
        self.target_edit.setVisible(not simple)
        label = self.target_form.labelForField(self.target_edit)
        if label is not None:
            label.setVisible(not simple)
        for button in self.response_action_buttons:
            button.setVisible(not simple)
        for button in self.simple_response_buttons:
            button.setVisible(simple)
        self.simple_apply_zip_button.setVisible(simple and not gemini_simple and not markdown_simple)
        self.simple_patch_directory_button.setVisible(
            simple and not gemini_simple and not markdown_simple
            and not bool(self.settings.update_zip_directory.strip())
        )
        self.update_zip_settings_group.setVisible(not gemini_simple and not markdown_simple)
        self.other_llm_settings_group.setVisible(not simple)
        self.change_source_group.setVisible(not gemini_simple)
        self.change_rollback_button.setVisible(not gemini_simple)
        self.restart_action.setVisible(not simple)
        self.simple_restart_button.setVisible(simple)
        for group in getattr(self, 'advanced_settings_groups', []):
            group.setVisible(not simple)
        self.gemini_drive_settings_group.setVisible(not simple or not markdown_simple)
        self.markdown_exchange_settings_group.setVisible(not simple or markdown_simple)
        if gemini_simple:
            self.report_button.setText(_('Prepara per Gemini'))
        else:
            self.report_button.setText(_('Prepara richiesta per l’AI') if simple else _('Genera Super-Report'))
        allowed_simple_tabs = (
            (self.workflow_tab, self.publication_tab, self.settings_tab, self.changes_tab)
            if gemini_simple or markdown_simple
            else (self.workflow_tab, self.publication_tab, self.settings_tab)
        )
        if simple and self.tabs.currentWidget() not in allowed_simple_tabs:
            self.tabs.setCurrentWidget(self.workflow_tab)

    def _auto_copy_report_in_simple_mode(self) -> None:
        if not self.settings.simple_mode:
            return
        report = self.report_edit.toPlainText()
        if not report.strip() or report == getattr(self, '_last_auto_copied_report', None):
            return
        QApplication.clipboard().setText(report)
        self._last_auto_copied_report = report
        self._show_status(_('Super-Report generato e copiato automaticamente.'))

    def _build_toolbar(self) -> None:
        toolbar = QToolBar(_('Principale'), self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_action = QAction(_('Nuovo progetto…'), self)
        new_action.setToolTip(_('Crea una nuova cartella di progetto vuota e la apre in BridgAI.'))
        new_action.triggered.connect(self.create_workspace)
        toolbar.addAction(new_action)

        open_action = QAction(_('Apri progetto…'), self)
        open_action.setToolTip(_('Seleziona una cartella di progetto già esistente.'))
        open_action.triggered.connect(self.choose_workspace)
        toolbar.addAction(open_action)

        self.add_recent_projects_widget(toolbar)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel(_('Progetto: ')))
        self.workspace_label = QLabel(_('Nessuno'))
        workspace_font = self.workspace_label.font()
        workspace_font.setBold(True)
        self.workspace_label.setFont(workspace_font)
        self.workspace_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        toolbar.addWidget(self.workspace_label)

        self.open_folder_action = QAction(_('Apri cartella'), self)
        self.open_folder_action.setToolTip(_('Apre il progetto corrente nel file manager senza cambiarlo.'))
        self.open_folder_action.setEnabled(False)
        self.open_folder_action.triggered.connect(self.open_workspace_folder)
        toolbar.addAction(self.open_folder_action)

        self.restart_action = QAction(_('Riavvia'), self)
        self.restart_action.triggered.connect(self.restart_application)
        toolbar.addAction(self.restart_action)

        toolbar_spacer = QWidget(self)
        toolbar_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(toolbar_spacer)

        credits_action = QAction(_('Crediti'), self)
        credits_action.triggered.connect(self.show_credits)
        toolbar.addAction(credits_action)

    def show_credits(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(_('Crediti'))
        box.setIcon(QMessageBox.Information)
        box.setText(_('BridgAI è stato realizzato da Massimo Slomp.'))
        website_button = box.addButton(_('Visita il sito'), QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() is website_button:
            QDesktopServices.openUrl(QUrl('https://www.massimoslomp.com'))

    def _context(self) -> SkillContext:
        return SkillContext(workspace=self.workspace)

    def _require_workspace(self) -> Path | None:
        if self.workspace is None:
            QMessageBox.warning(self, _('Workspace richiesto'), _('Seleziona prima una cartella di lavoro.'))
            return None
        return self.workspace

    def create_workspace(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        initial = self.settings.last_workspace or str(Path.home())
        parent = QFileDialog.getExistingDirectory(self, _('Scegli dove creare il nuovo progetto'), initial)
        if not parent:
            return

        name, accepted = QInputDialog.getText(
            self,
            _('Nuovo progetto'),
            _('Nome del progetto:'),
        )
        if not accepted:
            return

        try:
            project_name = _validated_project_name(name)
            project_path = Path(parent) / project_name
            project_path.mkdir(exist_ok=False)
        except FileExistsError:
            QMessageBox.warning(
                self,
                _('Progetto già esistente'),
                _('Esiste già una cartella con questo nome. Usa “Apri progetto…” oppure scegli un altro nome.'),
            )
            return
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, _('Impossibile creare il progetto'), str(exc))
            return

        self.set_workspace(project_path)
        self._show_status(_('Nuovo progetto creato: {name}').format(name=project_name))

    def choose_workspace(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        selected = QFileDialog.getExistingDirectory(
            self,
            _('Apri progetto'),
            self.settings.last_workspace or str(Path.home()),
        )
        if selected:
            self.set_workspace(Path(selected))

    def set_workspace(self, path: Path) -> None:
        try:
            path = path.expanduser().resolve(strict=True)
            if not path.is_dir():
                raise ValueError(_('Il percorso non è una directory.'))
        except Exception as exc:
            QMessageBox.critical(self, _('Workspace non valido'), str(exc))
            return
        previous_workspace = self.workspace
        workspace_changed = previous_workspace != path
        if workspace_changed:
            _reset_project_ui(self)
        self.workspace = path
        project_name = _project_display_name(path)
        self.workspace_label.setText(project_name)
        self.workspace_label.setToolTip(str(path))
        self.open_folder_action.setEnabled(True)
        self.file_tree.setRootIndex(self.file_model.setRootPath(str(path)))
        self.settings.last_workspace = str(path)
        self._remember_recent_workspace(path)
        self.refresh_prompt_settings()
        if not workspace_changed:
            self.current_plan = None
            self.apply_button.setEnabled(False)
        self._refresh_sessions()
        self.refresh_publication_tab()
        if workspace_changed and previous_workspace is not None:
            self._show_status(
                _('Progetto caricato: {name} — contenuti della sessione precedente azzerati.').format(
                    name=project_name
                )
            )
        else:
            self._show_status(_('Percorso progetto: {path}').format(path=path))

    def _load_last_workspace(self) -> None:
        if self.settings.last_workspace:
            candidate = Path(self.settings.last_workspace)
            if candidate.is_dir():
                self.set_workspace(candidate)

    def _tree_double_clicked(self, index: QModelIndex) -> None:
        path = Path(self.file_model.filePath(index))
        if self.workspace and path.is_file():
            try:
                self.target_edit.setText(path.resolve().relative_to(self.workspace).as_posix())
            except ValueError:
                pass

    def _run_background(self, function: Callable, on_result: Callable, status: str, on_finished: Callable | None=None) -> None:
        self._show_status(status)
        worker = FunctionWorker(function)
        self._active_workers.append(worker)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(self._background_error)
        worker.signals.finished.connect(lambda current=worker, callback=on_finished: self._finish_worker(current, callback))
        self.thread_pool.start(worker)

    def _finish_worker(self, worker: FunctionWorker, callback: Callable | None) -> None:
        try:
            if callback is not None:
                callback()
        finally:
            if worker in self._active_workers:
                self._active_workers.remove(worker)

    def _background_error(self, traceback_text: str) -> None:
        self._show_status(_('Operazione fallita.'))
        short = traceback_text.strip().splitlines()[-1] if traceback_text.strip() else _('Errore sconosciuto')
        log_path = self._write_error_log(traceback_text)
        message = short
        if log_path is not None:
            message += f'\n\nDettagli salvati in:\n{log_path}'
        else:
            message += '\n\nDettagli disponibili nella console.'
        QMessageBox.critical(self, _('Errore'), message)
        print(traceback_text, flush=True)

    def _write_error_log(self, traceback_text: str) -> Path | None:
        try:
            log_dir = app_data_dir() / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / 'errors.log'
            with log_path.open('a', encoding='utf-8') as stream:
                stream.write('\n' + '=' * 80 + '\n')
                stream.write(datetime.now().isoformat(timespec='seconds') + '\n')
                stream.write(traceback_text.rstrip() + '\n')
            return log_path
        except OSError:
            return None

    def _show_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if any((url.toLocalFile().lower().endswith('.zip') for url in event.mimeData().urls())):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.zip'):
                self.zip_path_edit.setText(path)
                self.tabs.setCurrentIndex(1)
                self.inspect_selected_zip()
                event.acceptProposedAction()
                return

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings_store.save(self.settings)
        if self.settings.web_stop_on_exit:
            stop_web_interface(self.web_process)
        super().closeEvent(event)
