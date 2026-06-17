from __future__ import annotations
from local_ai_bridge.i18n import tr as _
from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCheckBox, QComboBox, QFileSystemModel, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSplitter, QTabWidget, QTableWidget, QTreeView, QVBoxLayout, QWidget

def build_central_ui(window) -> QSplitter:
    splitter = QSplitter(Qt.Horizontal)
    window.project_panel = QWidget()
    left = window.project_panel
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(6, 6, 3, 6)
    left_layout.addWidget(QLabel(_('File del progetto')))
    window.file_model = QFileSystemModel(window)
    window.file_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
    window.file_tree = QTreeView()
    window.file_tree.setModel(window.file_model)
    window.file_tree.doubleClicked.connect(window._tree_double_clicked)
    for column in range(1, 4):
        window.file_tree.hideColumn(column)
    left_layout.addWidget(window.file_tree)
    splitter.addWidget(left)
    window.tabs = QTabWidget()
    window.workflow_tab = build_workflow_tab(window)
    window.changes_tab = build_changes_tab(window)
    window.tests_tab = build_tests_tab(window)
    window.advanced_tab = build_advanced_tab(window)
    window.settings_tab = build_settings_tab(window)
    window.tabs.addTab(window.workflow_tab, _('1. Report e risposta AI'))
    window.tabs.addTab(window.changes_tab, _('2. ZIP, diff e applicazione'))
    window.tabs.addTab(window.tests_tab, _('3. Test, Git e GitHub'))
    window.tabs.addTab(window.advanced_tab, _('Avanzato'))
    window.tabs.addTab(window.settings_tab, _('Impostazioni'))
    splitter.addWidget(window.tabs)
    splitter.setSizes([320, 1060])
    return splitter

def _button(label: str, callback, role: str = 'secondary') -> QPushButton:
    button = QPushButton(label)
    button.setProperty('role', role)
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(callback)
    return button



class ProviderButton(QPushButton):
    def __init__(self, label: str, callback, dot_color: str | None = None) -> None:
        super().__init__(label)
        self.setProperty('role', 'secondary')
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet('padding-right: 30px;')
        self.clicked.connect(callback)
        self._provider_dot_color = QColor(dot_color) if dot_color else None

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        color = self._provider_dot_color or self.palette().color(self.foregroundRole())
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        radius = 5
        center_x = self.width() - 16
        center_y = self.height() // 2
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)


def _provider_button(label: str, callback, dot_color: str | None = None) -> ProviderButton:
    return ProviderButton(label, callback, dot_color)

def _step_header(number: str, title: str, description: str) -> QWidget:
    container = QWidget()
    container.setProperty('class', 'stepHeader')
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    badge = QLabel(number)
    badge.setProperty('class', 'stepBadge')
    badge.setAlignment(Qt.AlignCenter)
    badge.setFixedSize(34, 34)
    row.addWidget(badge, 0, Qt.AlignTop)
    text_box = QVBoxLayout()
    text_box.setSpacing(2)
    heading = QLabel(title)
    heading.setProperty('class', 'stepTitle')
    detail = QLabel(description)
    detail.setProperty('class', 'stepDescription')
    detail.setWordWrap(True)
    text_box.addWidget(heading)
    text_box.addWidget(detail)
    row.addLayout(text_box, 1)
    container.badge_label = badge
    container.title_label = heading
    container.description_label = detail
    return container

def build_workflow_tab(window) -> QWidget:
    page = QWidget()
    page.setObjectName('workflowPage')
    layout = QVBoxLayout(page)
    layout.setContentsMargins(22, 18, 22, 22)
    layout.setSpacing(16)

    window.simple_welcome = QLabel(_('Cosa vuoi fare oggi?'))
    window.simple_welcome.setProperty('class', 'pageTitle')
    layout.addWidget(window.simple_welcome)
    window.simple_subtitle = QLabel(_('Descrivi il risultato che vuoi ottenere. BridgAI preparerà tutto il necessario per dialogare con la tua AI.'))
    window.simple_subtitle.setProperty('class', 'pageSubtitle')
    window.simple_subtitle.setWordWrap(True)
    layout.addWidget(window.simple_subtitle)

    task_group = QGroupBox()
    task_group.setProperty('class', 'card')
    window.task_group = task_group
    task_layout = QVBoxLayout(task_group)
    task_layout.setContentsMargins(18, 16, 18, 18)
    task_layout.setSpacing(12)
    task_layout.addWidget(_step_header('1', _('Descrivi la richiesta'), _('Scrivi con parole semplici cosa vuoi creare, correggere o migliorare.')))
    window.task_edit = QPlainTextEdit()
    window.task_edit.setPlaceholderText(_('Ad esempio: rendi più semplice la schermata iniziale e usa pulsanti più chiari...'))
    window.task_edit.setMaximumHeight(120)
    window.task_edit.setProperty('class', 'largeInput')
    task_layout.addWidget(window.task_edit)
    report_buttons = QHBoxLayout()
    window.report_button = _button(_('Prepara per l’AI'), window.generate_report, 'primary')
    report_buttons.addWidget(window.report_button)
    window.simple_chatgpt_button = _provider_button(
        _('Continua su ChatGPT'),
        lambda: window.open_external_ai(window.settings.chatgpt_url),
    )
    window.simple_claude_button = _provider_button(
        _('Continua su Claude'),
        lambda: window.open_external_ai(window.settings.claude_url),
        '#e58a2b',
    )
    window.simple_gemini_button = _provider_button(
        _('Continua su Gemini'),
        window.open_gemini,
        '#6c63ff',
    )
    window.simple_report_buttons = [
        window.simple_chatgpt_button,
        window.simple_claude_button,
        window.simple_gemini_button,
    ]
    for button in window.simple_report_buttons:
        report_buttons.addWidget(button)
    actions = ((_('Copia report'), window.copy_report), (_('Salva report'), window.save_report), (_('Apri ChatGPT'), lambda: window._open_web(window.settings.chatgpt_url)), (_('Apri Claude'), lambda: window._open_web(window.settings.claude_url)), (_('Apri Gemini'), window.open_gemini))
    window.report_extra_buttons = []
    for label, callback in actions:
        button = _button(label, callback)
        window.report_extra_buttons.append(button)
        report_buttons.addWidget(button)
    report_buttons.addStretch(1)
    window.speech_button = _button('🎙', window.open_speech_dialog, 'icon')
    window.speech_button.setAccessibleName(_('Dettatura'))
    window.speech_button.setToolTip(_('Detta il task tramite microfono'))
    report_buttons.addWidget(window.speech_button)
    task_layout.addLayout(report_buttons)
    layout.addWidget(task_group)

    window.report_edit = QPlainTextEdit()
    window.report_edit.setReadOnly(True)
    window.report_edit.setPlaceholderText(_('Il Super-Report apparirà qui.'))
    layout.addWidget(window.report_edit, 3)
    window.report_edit.textChanged.connect(window._auto_copy_report_in_simple_mode)

    response_group = QGroupBox()
    response_group.setProperty('class', 'card')
    window.response_group = response_group
    response_layout = QVBoxLayout(response_group)
    response_layout.setContentsMargins(18, 16, 18, 18)
    response_layout.setSpacing(12)
    window.response_step_header = _step_header('2', _('Incolla la risposta dell’AI'), _('Torna qui e incolla tutto il messaggio ricevuto, senza modificarlo.'))
    response_layout.addWidget(window.response_step_header)
    window.response_edit = QPlainTextEdit()
    window.response_edit.setPlaceholderText(_('Incolla qui la risposta completa dell’AI...'))
    window.response_edit.setProperty('class', 'largeInput')
    response_layout.addWidget(window.response_edit, 2)
    form = QFormLayout()
    window.target_edit = QLineEdit()
    window.target_edit.setPlaceholderText(_('es. src/app.py — necessario per patch o file completo'))
    form.addRow(_('File target:'), window.target_edit)
    window.target_form = form
    response_layout.addLayout(form)
    response_buttons = QHBoxLayout()
    response_actions = ((_('Analizza risposta'), window.analyze_response), (_('Esporta file #scarica'), window.export_requested_files), (_('Apri cartella #scarica'), window.open_download_folder), (_('Prepara patch'), window.prepare_patch), (_('Prepara file completo'), window.prepare_full_file))
    window.response_action_buttons = []
    for label, callback in response_actions:
        button = _button(label, callback)
        window.response_action_buttons.append(button)
        response_buttons.addWidget(button)
    window.simple_paste_response_button = _button(_('Incolla'), window.paste_response_from_clipboard, 'primary')
    window.simple_prepare_files_button = _button(_('Prepara i file richiesti'), window.export_requested_files, 'primary')
    window.simple_response_buttons = [
        window.simple_paste_response_button,
        window.simple_prepare_files_button,
    ]
    for button in window.simple_response_buttons:
        response_buttons.addWidget(button)
    window.simple_apply_zip_button = _button(_('Applica aggiornamento'), window.apply_latest_zip, 'success')
    response_buttons.addWidget(window.simple_apply_zip_button)
    window.simple_patch_directory_button = _button(_('Scegli cartella aggiornamenti'), window.choose_update_zip_directory)
    response_buttons.addWidget(window.simple_patch_directory_button)
    response_buttons.addStretch(1)
    response_layout.addLayout(response_buttons)
    layout.addWidget(response_group, 2)

    window.simple_finish_hint = QLabel(_('3  Quando ricevi uno ZIP dall’AI, salvalo nella cartella scelta e premi “Applica aggiornamento”. Prima dell’applicazione verrà sempre mostrata un’anteprima.'))
    window.simple_finish_hint.setProperty('class', 'infoBanner')
    window.simple_finish_hint.setWordWrap(True)
    layout.addWidget(window.simple_finish_hint)

    gemini_result_group = QGroupBox()
    gemini_result_group.setProperty('class', 'card')
    window.gemini_result_group = gemini_result_group
    gemini_result_layout = QVBoxLayout(gemini_result_group)
    gemini_result_layout.setContentsMargins(18, 16, 18, 18)
    gemini_result_layout.setSpacing(12)
    gemini_result_layout.addWidget(
        _step_header(
            '3',
            _('Incolla il codice restituito da Gemini'),
            _('Copia l’intera risposta: BridgAI riconoscerà i percorsi e i blocchi SEARCH/REPLACE.'),
        )
    )
    window.gemini_result_edit = QPlainTextEdit()
    window.gemini_result_edit.setPlaceholderText(_('Incolla qui la risposta completa di Gemini con percorsi e blocchi SEARCH/REPLACE...'))
    window.gemini_result_edit.setProperty('class', 'largeInput')
    gemini_result_layout.addWidget(window.gemini_result_edit, 2)
    gemini_result_buttons = QHBoxLayout()
    gemini_result_buttons.addWidget(_button(_('Incolla risposta Gemini'), window.paste_gemini_result_from_clipboard, 'primary'))
    gemini_result_buttons.addWidget(_button(_('Prepara anteprima modifiche'), window.prepare_gemini_plan, 'primary'))
    gemini_result_buttons.addStretch(1)
    gemini_result_layout.addLayout(gemini_result_buttons)
    layout.addWidget(gemini_result_group, 2)
    return page

def build_changes_tab(window) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    source_group = QGroupBox(_('Cartella ZIP delle modifiche'))
    window.change_source_group = source_group
    source_layout = QVBoxLayout(source_group)
    folder_row = QHBoxLayout()
    window.update_zip_directory_edit = QLineEdit()
    window.update_zip_directory_edit.setReadOnly(True)
    window.update_zip_directory_edit.setPlaceholderText(_('Seleziona la cartella in cui vengono scaricati gli ZIP delle modifiche...'))
    window.update_zip_directory_edit.setText(window.settings.update_zip_directory)
    folder_row.addWidget(window.update_zip_directory_edit, 1)
    folder_row.addWidget(_button(_('Imposta cartella'), window.choose_update_zip_directory))
    folder_row.addWidget(_button(_('Applica ultimo'), window.apply_latest_zip))
    source_layout.addLayout(folder_row)
    zip_row = QHBoxLayout()
    window.zip_path_edit = QLineEdit()
    window.zip_path_edit.setPlaceholderText(_('Trascina uno ZIP qui o selezionalo...'))
    zip_row.addWidget(window.zip_path_edit, 1)
    zip_row.addWidget(_button(_('Sfoglia ZIP'), window.choose_zip))
    zip_row.addWidget(_button(_('Analizza ZIP'), window.inspect_selected_zip))
    source_layout.addLayout(zip_row)
    layout.addWidget(source_group)
    window.plan_table = QTableWidget(0, 4)
    window.plan_table.setHorizontalHeaderLabels([_('Target'), _('Tipo'), _('Dimensione'), _('Hash nuovo')])
    window.plan_table.horizontalHeader().setStretchLastSection(True)
    layout.addWidget(window.plan_table, 1)
    window.diff_edit = QPlainTextEdit()
    window.diff_edit.setReadOnly(True)
    window.diff_edit.setPlaceholderText(_("L'anteprima diff apparirà qui. Nessun file viene scritto durante l'analisi."))
    layout.addWidget(window.diff_edit, 4)
    buttons = QHBoxLayout()
    window.apply_button = _button(_('Applica piano'), window.apply_current_plan)
    window.apply_button.setEnabled(False)
    buttons.addWidget(window.apply_button)
    window.change_rollback_button = _button(_('Rollback ultimo batch'), window.rollback_latest)
    buttons.addWidget(window.change_rollback_button)
    window.change_clear_button = _button(_('Azzera piano'), window.clear_plan)
    buttons.addWidget(window.change_clear_button)
    buttons.addStretch(1)
    layout.addLayout(buttons)
    return page

def build_tests_tab(window) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    test_group = QGroupBox(_('Controlli del progetto'))
    test_buttons = QHBoxLayout(test_group)
    test_buttons.addWidget(_button(_('Esegui test rilevati'), window.run_tests))
    test_buttons.addStretch(1)
    layout.addWidget(test_group)
    git_group = QGroupBox(_('Git locale'))
    git_buttons = QHBoxLayout(git_group)
    for label, callback in ((_('Inizializza Git'), window.initialize_git_repository), (_('Prepara e crea commit'), window.prepare_git_commit), (_('Git status'), window.show_git_status), (_('Git diff'), window.show_git_diff), (_('Remote'), window.show_git_remotes)):
        git_buttons.addWidget(_button(label, callback))
    git_buttons.addStretch(1)
    layout.addWidget(git_group)
    github_group = QGroupBox('GitHub')
    github_layout = QVBoxLayout(github_group)
    github_layout.addWidget(QLabel(_("L'account è gestito da GitHub CLI: le credenziali non vengono salvate nel workspace.")))
    account_buttons = QHBoxLayout()
    for label, callback in ((_('Stato account'), window.show_github_status), (_('Aggiungi account'), window.add_github_account), (_('Cambia account'), window.switch_github_account)):
        account_buttons.addWidget(_button(label, callback))
    account_buttons.addStretch(1)
    github_layout.addLayout(account_buttons)
    repository_buttons = QHBoxLayout()
    for label, callback in ((_('Crea repository GitHub'), window.create_github_repository), (_('Collega repository esistente'), window.connect_existing_github_repository), (_('Push branch corrente'), window.push_to_github)):
        repository_buttons.addWidget(_button(label, callback))
    repository_buttons.addStretch(1)
    github_layout.addLayout(repository_buttons)
    layout.addWidget(github_group)
    window.test_output = QPlainTextEdit()
    window.test_output.setReadOnly(True)
    window.test_output.setPlaceholderText(_('Risultati di test, Git e GitHub...'))
    layout.addWidget(window.test_output, 1)
    return page

def build_advanced_tab(window) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.addWidget(QLabel(_('Skill interne disponibili')))
    window.skills_table = QTableWidget(0, 4)
    window.skills_table.setHorizontalHeaderLabels(['ID', _('Nome'), _('Permessi'), _('Descrizione')])
    window.skills_table.horizontalHeader().setStretchLastSection(True)
    layout.addWidget(window.skills_table, 2)
    layout.addWidget(_button(_('Aggiorna sessioni'), window._refresh_sessions))
    window.sessions_table = QTableWidget(0, 6)
    window.sessions_table.setHorizontalHeaderLabels([_('Sessione'), _('Operazione'), _('Stato'), _('File'), _('Test'), _('Data')])
    window.sessions_table.horizontalHeader().setStretchLastSection(True)
    window.sessions_table.setSelectionBehavior(QTableWidget.SelectRows)
    window.sessions_table.setSelectionMode(QTableWidget.SingleSelection)
    window.sessions_table.itemSelectionChanged.connect(window.show_selected_session)
    layout.addWidget(window.sessions_table, 2)
    window.session_details_edit = QPlainTextEdit()
    window.session_details_edit.setReadOnly(True)
    window.session_details_edit.setPlaceholderText(_('Seleziona una sessione per visualizzare file e verifiche.'))
    layout.addWidget(window.session_details_edit, 2)
    return page

def build_settings_tab(window) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    interface_group = QGroupBox(_('Interfaccia'))
    interface_layout = QVBoxLayout(interface_group)
    window.simple_mode_check = QCheckBox(_('Modalità super semplice'))
    window.simple_mode_check.setToolTip(_('Mostra un flusso guidato e mantiene le funzioni avanzate nascoste.'))
    window.simple_mode_check.setChecked(window.settings.simple_mode)
    window.simple_mode_check.toggled.connect(window._save_simple_mode)
    interface_layout.addWidget(window.simple_mode_check)
    window.dark_mode_check = QCheckBox(_('Modalità scura'))
    window.dark_mode_check.setToolTip(_('Usa colori scuri e ad alto contrasto in tutta l’interfaccia.'))
    window.dark_mode_check.setChecked(window.settings.dark_mode)
    window.dark_mode_check.toggled.connect(window.set_dark_mode)
    interface_layout.addWidget(window.dark_mode_check)
    restart_row = QHBoxLayout()
    window.simple_restart_button = _button(_('Riavvia BridgAI'), window.restart_application)
    restart_row.addWidget(window.simple_restart_button)
    restart_row.addStretch(1)
    interface_layout.addLayout(restart_row)
    layout.addWidget(interface_group)
    window.simple_mode_settings_group = interface_group
    window.advanced_settings_groups = []

    updates_group = QGroupBox(_('Cartella aggiornamenti'))
    window.update_zip_settings_group = updates_group
    updates_layout = QVBoxLayout(updates_group)
    updates_description = QLabel(_('Cartella in cui il programma cerca gli ZIP ricevuti dall’AI.'))
    updates_description.setWordWrap(True)
    updates_layout.addWidget(updates_description)
    updates_row = QHBoxLayout()
    window.settings_update_zip_directory_edit = QLineEdit()
    window.settings_update_zip_directory_edit.setReadOnly(True)
    window.settings_update_zip_directory_edit.setPlaceholderText(_('Nessuna cartella selezionata'))
    window.settings_update_zip_directory_edit.setText(window.settings.update_zip_directory)
    updates_row.addWidget(window.settings_update_zip_directory_edit, 1)
    updates_row.addWidget(_button(_('Cambia cartella'), window.choose_update_zip_directory))
    updates_layout.addLayout(updates_row)
    layout.addWidget(updates_group)

    projects_group = QGroupBox(_('Progetti della Web UI'))
    projects_layout = QVBoxLayout(projects_group)
    projects_description = QLabel(
        _(
            'La Web UI mostrerà come progetti tutte le cartelle di primo livello '
            'contenute nella root selezionata. La root può essere modificata solo da questo programma.'
        )
    )
    projects_description.setWordWrap(True)
    projects_layout.addWidget(projects_description)
    projects_root_row = QHBoxLayout()
    window.web_workspace_root_edit = QLineEdit()
    window.web_workspace_root_edit.setReadOnly(True)
    window.web_workspace_root_edit.setPlaceholderText(_('Nessuna cartella root configurata'))
    projects_root_row.addWidget(window.web_workspace_root_edit, 1)
    projects_root_row.addWidget(_button(_('Scegli root progetti'), window.choose_web_workspace_root))
    projects_root_row.addWidget(_button(_('Rimuovi'), window.clear_web_workspace_root))
    projects_layout.addLayout(projects_root_row)
    layout.addWidget(projects_group)
    window.project_root_settings_group = projects_group

    web_group = QGroupBox(_('Interfaccia web locale'))
    web_layout = QVBoxLayout(web_group)
    web_layout.addWidget(QLabel(_('L’interfaccia web resta spenta finché non la avvii manualmente.')))
    web_row = QHBoxLayout()
    window.web_port_edit = QLineEdit()
    window.web_port_edit.setPlaceholderText('8765')
    window.web_port_edit.setMaximumWidth(100)
    web_row.addWidget(QLabel(_('Porta:')))
    web_row.addWidget(window.web_port_edit)
    window.web_open_browser_check = QCheckBox(_('Apri il browser dopo l’avvio'))
    web_row.addWidget(window.web_open_browser_check)
    web_row.addWidget(_button(_('Avvia'), window.start_web_interface_from_settings))
    web_row.addWidget(_button(_('Ferma'), window.stop_web_interface_from_settings))
    web_row.addStretch(1)
    web_layout.addLayout(web_row)
    window.web_remote_access_check = QCheckBox(_('Consenti accesso dalla rete (ascolta su tutte le interfacce)'))
    web_layout.addWidget(window.web_remote_access_check)
    credentials_form = QFormLayout()
    window.web_username_edit = QLineEdit()
    window.web_username_edit.setPlaceholderText(_('es. admin'))
    window.web_password_edit = QLineEdit()
    window.web_password_edit.setEchoMode(QLineEdit.Password)
    window.web_password_edit.setPlaceholderText(_('Lascia vuoto per mantenere la password attuale'))
    credentials_form.addRow(_('Username:'), window.web_username_edit)
    credentials_form.addRow(_('Password:'), window.web_password_edit)
    web_layout.addLayout(credentials_form)
    warning = QLabel(_('L’accesso remoto richiede username e password. Per Internet usa sempre HTTPS tramite reverse proxy.'))
    warning.setWordWrap(True)
    web_layout.addWidget(warning)
    layout.addWidget(web_group)
    window.advanced_settings_groups.append(web_group)

    language_group = QGroupBox(_("Lingua interfaccia"))
    language_layout = QFormLayout(language_group)
    window.language_combo = QComboBox()
    window.language_combo.addItem(_("Italiano"), "it")
    window.language_combo.addItem(_("English"), "en")
    index = window.language_combo.findData(window.settings.language)
    window.language_combo.setCurrentIndex(max(0, index))
    window.language_combo.currentIndexChanged.connect(window.save_interface_language)
    language_layout.addRow(_("Lingua:"), window.language_combo)
    layout.addWidget(language_group)
    window.advanced_settings_groups.append(language_group)

    temp_group = QGroupBox(_('File temporanei gestiti'))
    temp_layout = QVBoxLayout(temp_group)
    temp_layout.addWidget(QLabel(_('ZIP esportati con #scarica, ZIP importati per gli aggiornamenti e futuri file patch vengono conservati in una cartella dedicata e pulibile in sicurezza.')))
    row = QHBoxLayout()
    window.temp_directory_edit = QLineEdit()
    window.temp_directory_edit.setReadOnly(True)
    row.addWidget(window.temp_directory_edit, 1)
    row.addWidget(_button(_('Scegli cartella base'), window.choose_temp_directory))
    row.addWidget(_button(_('Apri cartella'), window.open_temp_directory))
    temp_layout.addLayout(row)
    cleanup_row = QHBoxLayout()
    cleanup_row.addWidget(_button(_('Pulisci file temporanei'), window.clean_temp_directory))
    cleanup_row.addStretch(1)
    temp_layout.addLayout(cleanup_row)
    layout.addWidget(temp_group)
    window.advanced_settings_groups.append(temp_group)
    drive_group = QGroupBox(_('Utilizzo Gemini'))
    drive_layout = QVBoxLayout(drive_group)
    drive_description = QLabel(_('La modalità Gemini sostituisce ChatGPT e Claude nel flusso semplice. BridgAI crea lo ZIP dei file richiesti nella cartella Drive, la cui sincronizzazione resta affidata al client ufficiale Google Drive. Gemini restituisce poi testo con percorsi e blocchi SEARCH/REPLACE, analizzato localmente prima dell’applicazione.'))
    drive_description.setWordWrap(True)
    drive_layout.addWidget(drive_description)
    window.gemini_drive_enabled_check = QCheckBox(_('Abilita modalità Gemini con Google Drive'))
    window.gemini_drive_enabled_check.toggled.connect(window.set_gemini_drive_enabled)
    drive_layout.addWidget(window.gemini_drive_enabled_check)
    drive_path_row = QHBoxLayout()
    window.gemini_drive_path_edit = QLineEdit()
    window.gemini_drive_path_edit.setPlaceholderText(_('es. G:\\Il mio Drive\\LocalAIBridge oppure una cartella Drive su macOS'))
    window.gemini_drive_path_edit.editingFinished.connect(window.save_gemini_drive_path)
    drive_path_row.addWidget(window.gemini_drive_path_edit, 1)
    drive_path_row.addWidget(_button(_('Sfoglia'), window.choose_gemini_drive_directory))
    drive_layout.addLayout(drive_path_row)
    download_row = QHBoxLayout()
    download_row.addWidget(_button(_('Scarica Google Drive per PC'), window.open_google_drive_download))
    download_row.addStretch(1)
    drive_layout.addLayout(download_row)
    layout.addWidget(drive_group)
    window.gemini_drive_settings_group = drive_group
    layout.addStretch(1)
    window.refresh_web_settings()
    window.refresh_temp_settings()
    window.refresh_gemini_drive_settings()
    return page
