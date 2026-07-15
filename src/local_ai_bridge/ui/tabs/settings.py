from __future__ import annotations

import sys

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.tabs.ai_assistant import build_ai_assistant_settings_group
from local_ai_bridge.ui.widgets import ToggleSwitch, _button
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def _section(title: str) -> tuple[QWidget, QVBoxLayout]:
    section = QWidget()
    section_layout = QVBoxLayout(section)
    section_layout.setContentsMargins(0, 0, 0, 0)
    section_layout.setSpacing(8)

    title_label = QLabel(_(title))
    title_font = title_label.font()
    title_font.setBold(True)
    title_label.setFont(title_font)
    section_layout.addWidget(title_label)
    return section, section_layout


def _wrapped_label(text: str) -> QLabel:
    label = QLabel(_(text))
    label.setWordWrap(True)
    return label


def build_settings_tab(window) -> QWidget:
    page = QWidget()
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)

    scroll_area = QScrollArea()
    scroll_area.setObjectName("settingsScrollArea")
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QScrollArea.NoFrame)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    content = QWidget()
    content.setObjectName("settingsScrollContent")
    layout = QVBoxLayout(content)
    layout.setContentsMargins(18, 14, 18, 18)
    layout.setSpacing(14)

    window.advanced_settings_groups = []

    interface_group = QGroupBox(_('Interfaccia'))
    interface_layout = QVBoxLayout(interface_group)

    mode_section, mode_layout = _section('Modalità principale')
    mode_layout.addWidget(
        _wrapped_label(
            'Scegli tra il flusso per lo sviluppo software e l’assistente guidato per '
            'documenti, presentazioni, PDF, immagini e altri lavori con l’AI.'
        )
    )
    mode_form = QFormLayout()
    window.primary_mode_combo = QComboBox()
    window.primary_mode_combo.addItem(_('Sviluppo software'), 'development')
    window.primary_mode_combo.addItem(_('Assistente Attività AI'), 'operations')
    window.primary_mode_combo.currentIndexChanged.connect(window.save_primary_mode)
    mode_form.addRow(_('Modalità:'), window.primary_mode_combo)
    mode_layout.addLayout(mode_form)
    interface_layout.addWidget(mode_section)

    window.simple_mode_check = ToggleSwitch(_('Modalità super semplice'))
    window.simple_mode_check.setToolTip(
        _('Mostra un flusso guidato e mantiene le funzioni avanzate nascoste.')
    )
    window.simple_mode_check.setChecked(window.settings.simple_mode)
    window.simple_mode_check.toggled.connect(window._save_simple_mode)
    interface_layout.addWidget(window.simple_mode_check)

    preferred_ai_section, preferred_ai_layout = _section('AI Web preferita')
    preferred_ai_layout.addWidget(
        _wrapped_label(
            'Scegli il servizio usato normalmente nella modalità super semplice. '
            'La preferenza viene salvata e riproposta a ogni avvio.'
        )
    )
    preferred_ai_form = QFormLayout()
    window.preferred_web_ai_combo = QComboBox()
    window.preferred_web_ai_combo.addItem('ChatGPT', 'chatgpt')
    window.preferred_web_ai_combo.addItem('Claude', 'claude')
    window.preferred_web_ai_combo.addItem('Gemini', 'gemini')
    window.preferred_web_ai_combo.addItem('DeepSeek', 'deepseek')
    window.preferred_web_ai_combo.addItem(_('Personalizzato'), 'custom')
    window.preferred_web_ai_combo.currentIndexChanged.connect(
        lambda index: window.set_preferred_web_ai(
            window.preferred_web_ai_combo.itemData(index)
        )
    )
    preferred_ai_form.addRow(_('Seleziona modello preferito:'), window.preferred_web_ai_combo)
    preferred_ai_layout.addLayout(preferred_ai_form)
    window.preferred_web_ai_flow_label = _wrapped_label(
        'ChatGPT e Claude usano ZIP → ZIP; Gemini usa ZIP → File Markdown di aggiornamento; '
        'DeepSeek usa Markdown → File Markdown di aggiornamento. Con Personalizzato scegli il flusso.'
    )
    preferred_ai_layout.addWidget(window.preferred_web_ai_flow_label)
    wizard_row = QHBoxLayout()
    window.reopen_initial_setup_button = _button(
        _('Avvia di nuovo la configurazione iniziale'),
        window.reopen_initial_setup,
    )
    window.reopen_initial_setup_button.setToolTip(
        _('Rivedi le scelte iniziali senza ripristinare le altre preferenze.')
    )
    wizard_row.addWidget(window.reopen_initial_setup_button)
    wizard_row.addStretch(1)
    preferred_ai_layout.addLayout(wizard_row)
    window.simple_force_web_server_button = _button(
        _('Avvia server web forzato (Windows)'),
        window.start_windows_direct_web_server_from_settings,
    )
    window.simple_force_web_server_button.setToolTip(
        _('Avvia web_server_force_win.bat in una console separata sulla porta 8765.')
    )
    window.simple_force_web_server_button.setVisible(sys.platform == 'win32')
    preferred_ai_layout.addWidget(window.simple_force_web_server_button)
    preferred_ai_section.setVisible(window.settings.simple_mode)
    window.simple_mode_check.toggled.connect(preferred_ai_section.setVisible)
    interface_layout.addWidget(preferred_ai_section)
    window.preferred_web_ai_settings_group = preferred_ai_section

    window.dark_mode_check = ToggleSwitch(_('Tema scuro'))
    window.dark_mode_check.setToolTip(
        _('Usa colori scuri e ad alto contrasto in tutta l’interfaccia.')
    )
    window.dark_mode_check.setChecked(window.settings.dark_mode)
    window.dark_mode_check.toggled.connect(window.set_dark_mode)
    interface_layout.addWidget(window.dark_mode_check)

    language_section, language_layout = _section('Lingua interfaccia')
    language_form = QFormLayout()
    window.language_combo = QComboBox()
    window.language_combo.addItem(_('Italiano'), 'it')
    window.language_combo.addItem(_('English'), 'en')
    index = window.language_combo.findData(window.settings.language)
    window.language_combo.setCurrentIndex(max(0, index))
    window.language_combo.currentIndexChanged.connect(window.save_interface_language)
    language_form.addRow(_('Lingua:'), window.language_combo)
    language_layout.addLayout(language_form)
    interface_layout.addWidget(language_section)

    restart_row = QHBoxLayout()
    window.simple_restart_button = _button(_('Riavvia BridgAI'), window.restart_application)
    restart_row.addWidget(window.simple_restart_button)
    restart_row.addStretch(1)
    interface_layout.addLayout(restart_row)
    layout.addWidget(interface_group)
    window.simple_mode_settings_group = interface_group

    folders_group = QGroupBox(_('Cartelle'))
    folders_layout = QVBoxLayout(folders_group)

    updates_section, updates_layout = _section('Cartella aggiornamenti')
    updates_layout.addWidget(
        _wrapped_label('Cartella in cui il programma cerca gli ZIP ricevuti dall’AI.')
    )
    updates_row = QHBoxLayout()
    window.settings_update_zip_directory_edit = QLineEdit()
    window.settings_update_zip_directory_edit.setReadOnly(True)
    window.settings_update_zip_directory_edit.setPlaceholderText(
        _('Nessuna cartella selezionata')
    )
    window.settings_update_zip_directory_edit.setText(window.settings.update_zip_directory)
    updates_row.addWidget(window.settings_update_zip_directory_edit, 1)
    updates_row.addWidget(_button(_('Cambia cartella'), window.choose_update_zip_directory))
    updates_layout.addLayout(updates_row)
    folders_layout.addWidget(updates_section)

    external_context_section, external_context_layout = _section('Contesti aggiuntivi per il Super-Report')
    external_context_layout.addWidget(
        _wrapped_label(
            'Aggiungi una cartella per riga per mostrare al progetto corrente altri progetti o '
            'librerie locali. Questi percorsi vengono inclusi nel Super-Report solo come riferimento '
            'di lettura: le modifiche applicabili restano nel workspace corrente.'
        )
    )
    window.external_context_paths_edit = QPlainTextEdit()
    window.external_context_paths_edit.setObjectName('externalContextPathsEdit')
    window.external_context_paths_edit.setPlaceholderText(
        _('es. /home/max/progetti/altro-progetto')
    )
    window.external_context_paths_edit.setMinimumHeight(86)
    external_context_layout.addWidget(window.external_context_paths_edit)
    external_context_row = QHBoxLayout()
    external_context_row.addWidget(
        _button(_('Aggiungi cartella'), window.add_external_context_directory)
    )
    external_context_row.addWidget(
        _button(_('Salva contesti'), window.save_external_context_paths)
    )
    external_context_row.addWidget(
        _button(_('Svuota'), window.clear_external_context_paths)
    )
    external_context_row.addStretch(1)
    external_context_layout.addLayout(external_context_row)
    folders_layout.addWidget(external_context_section)
    window.external_context_settings_section = external_context_section

    temp_section, temp_layout = _section('Cartella file temporanei')
    temp_layout.addWidget(
        _wrapped_label(
            'ZIP esportati con #scarica, ZIP importati per gli aggiornamenti e futuri '
            'file patch vengono conservati in una cartella dedicata e pulibile in sicurezza.'
        )
    )
    temp_row = QHBoxLayout()
    window.temp_directory_edit = QLineEdit()
    window.temp_directory_edit.setReadOnly(True)
    temp_row.addWidget(window.temp_directory_edit, 1)
    temp_row.addWidget(_button(_('Scegli cartella base'), window.choose_temp_directory))
    temp_row.addWidget(_button(_('Apri cartella'), window.open_temp_directory))
    temp_layout.addLayout(temp_row)
    cleanup_row = QHBoxLayout()
    cleanup_row.addWidget(_button(_('Pulisci file temporanei'), window.clean_temp_directory))
    cleanup_row.addStretch(1)
    temp_layout.addLayout(cleanup_row)
    folders_layout.addWidget(temp_section)
    window.advanced_settings_groups.append(temp_section)

    layout.addWidget(folders_group)
    window.update_zip_settings_group = folders_group
    window.update_zip_settings_section = updates_section

    window.ai_assistant_settings_group = build_ai_assistant_settings_group(window)
    layout.addWidget(window.ai_assistant_settings_group)

    web_group = QGroupBox(_('Interfaccia Web UI'))
    web_group_layout = QVBoxLayout(web_group)

    local_web_section, web_layout = _section('Interfaccia web locale')
    web_layout.addWidget(
        _wrapped_label(
            'Puoi avviare l’interfaccia web manualmente oppure automaticamente ai prossimi '
            'avvii di BridgAI.'
        )
    )
    window.web_auto_start_check = ToggleSwitch(
        _('Avvia automaticamente il server web all’avvio di BridgAI')
    )
    web_layout.addWidget(window.web_auto_start_check)
    web_row = QHBoxLayout()
    window.web_port_edit = QLineEdit()
    window.web_port_edit.setPlaceholderText('8765')
    window.web_port_edit.setMaximumWidth(100)
    web_row.addWidget(QLabel(_('Porta:')))
    web_row.addWidget(window.web_port_edit)
    window.web_open_browser_check = ToggleSwitch(_('Apri il browser dopo l’avvio'))
    web_row.addWidget(window.web_open_browser_check)
    web_row.addWidget(_button(_('Avvia'), window.start_web_interface_from_settings))
    web_row.addWidget(_button(_('Ferma'), window.stop_web_interface_from_settings))
    web_row.addStretch(1)
    web_layout.addLayout(web_row)

    diagnostics_section, diagnostics_layout = _section('Console e log di diagnostica')
    diagnostics_layout.addWidget(
        _wrapped_label(
            'Su Windows BridgAI e il server web vengono avviati senza finestre terminale. '
            'Puoi riattivarle per il prossimo avvio oppure aprire i log in qualsiasi momento.'
        )
    )
    window.windows_show_diagnostic_consoles_check = ToggleSwitch(
        _('Mostra le console di diagnostica su Windows')
    )
    window.windows_show_diagnostic_consoles_check.setToolTip(
        _('La modifica si applica al prossimo avvio di BridgAI e ai successivi avvii del server web.')
    )
    window.windows_show_diagnostic_consoles_check.setVisible(sys.platform == 'win32')
    window.windows_show_diagnostic_consoles_check.toggled.connect(
        window.set_windows_diagnostic_consoles
    )
    diagnostics_layout.addWidget(window.windows_show_diagnostic_consoles_check)
    diagnostic_buttons = QHBoxLayout()
    diagnostic_buttons.addWidget(_button(_('Apri log applicazione'), window.open_desktop_log))
    diagnostic_buttons.addWidget(_button(_('Apri log server web'), window.open_web_server_log))
    diagnostic_buttons.addWidget(_button(_('Apri cartella log'), window.open_logs_directory))
    diagnostic_buttons.addStretch(1)
    diagnostics_layout.addLayout(diagnostic_buttons)
    web_layout.addWidget(diagnostics_section)

    window.web_remote_access_check = ToggleSwitch(
        _('Consenti accesso dalla rete (ascolta su tutte le interfacce)')
    )
    web_layout.addWidget(window.web_remote_access_check)
    credentials_form = QFormLayout()
    window.web_username_edit = QLineEdit()
    window.web_username_edit.setPlaceholderText(_('es. admin'))
    window.web_password_edit = QLineEdit()
    window.web_password_edit.setEchoMode(QLineEdit.Password)
    window.web_password_edit.setPlaceholderText(
        _('Lascia vuoto per mantenere la password attuale')
    )
    credentials_form.addRow(_('Username:'), window.web_username_edit)
    credentials_form.addRow(_('Password:'), window.web_password_edit)
    web_layout.addLayout(credentials_form)

    two_factor_section, two_factor_layout = _section('Autenticazione a due fattori')
    window.web_totp_status_label = _wrapped_label('2FA non configurata.')
    two_factor_layout.addWidget(window.web_totp_status_label)
    two_factor_row = QHBoxLayout()
    window.web_totp_configure_button = _button(
        _('Configura o rigenera 2FA'), window.configure_web_two_factor
    )
    window.web_totp_disable_button = _button(
        _('Disabilita 2FA'), window.disable_web_two_factor
    )
    two_factor_row.addWidget(window.web_totp_configure_button)
    two_factor_row.addWidget(window.web_totp_disable_button)
    two_factor_row.addStretch(1)
    two_factor_layout.addLayout(two_factor_row)
    window.web_totp_local_bypass_check = ToggleSwitch(
        _('Non richiedere il codice 2FA ai dispositivi della rete locale privata')
    )
    window.web_totp_local_bypass_check.setToolTip(
        _(
            'Username e password restano obbligatori. La deroga vale per loopback, reti private '
            'RFC1918, link-local e IPv6 ULA. Dietro Nginx vengono accettati gli header del client '
            'solo quando il proxy è sulla stessa macchina.'
        )
    )
    two_factor_layout.addWidget(window.web_totp_local_bypass_check)
    two_factor_layout.addWidget(
        _wrapped_label(
            'Per accessi Internet la 2FA resta obbligatoria. Il server riconosce la rete locale '
            'dall’indirizzo client; con Nginx configura X-Forwarded-For e mantieni la porta '
            'interna non esposta pubblicamente.'
        )
    )
    web_layout.addWidget(two_factor_section)

    web_layout.addWidget(
        _wrapped_label(
            'L’accesso remoto richiede username e password. Per Internet usa sempre HTTPS '
            'tramite reverse proxy.'
        )
    )
    web_group_layout.addWidget(local_web_section)

    projects_section, projects_layout = _section('Cartella progetti Web UI')
    projects_layout.addWidget(
        _wrapped_label(
            'La Web UI mostrerà come progetti tutte le cartelle di primo livello contenute '
            'nella root selezionata. La root può essere modificata solo da questo programma.'
        )
    )
    projects_root_row = QHBoxLayout()
    window.web_workspace_root_edit = QLineEdit()
    window.web_workspace_root_edit.setReadOnly(True)
    window.web_workspace_root_edit.setPlaceholderText(
        _('Nessuna cartella root configurata')
    )
    projects_root_row.addWidget(window.web_workspace_root_edit, 1)
    projects_root_row.addWidget(
        _button(_('Scegli root progetti'), window.choose_web_workspace_root)
    )
    projects_root_row.addWidget(_button(_('Rimuovi'), window.clear_web_workspace_root))
    projects_layout.addLayout(projects_root_row)
    projects_layout.addWidget(
        _button(_('Genera report batch progetti'), window.create_web_workspace_batch_reports)
    )
    web_group_layout.addWidget(projects_section)

    layout.addWidget(web_group)
    window.project_root_settings_group = projects_section
    window.advanced_settings_groups.append(web_group)

    other_models_group = QGroupBox(_('Formati di scambio con AI Web'))
    other_models_layout = QVBoxLayout(other_models_group)
    other_models_layout.addWidget(
        _wrapped_label(
            'ZIP → ZIP è il flusso consigliato ed è l’unico verificato come pienamente funzionante. '
            'Usa i formati Markdown solo come alternativa: soprattutto per le modifiche in modalità '
            'patch, il risultato potrebbe non funzionare sempre.'
        )
    )

    requested_files_section, requested_files_layout = _section(
        'Formato dei file richiesti'
    )
    requested_files_layout.addWidget(
        _wrapped_label(
            'Stabilisce cosa produce BridgAI quando l’AI risponde con #scarica.'
        )
    )
    window.requested_files_format_combo = QComboBox()
    window.requested_files_format_combo.addItem(_('ZIP — consigliato'), 'zip')
    window.requested_files_format_combo.addItem(
        _('Markdown — per AI senza supporto ZIP'), 'markdown'
    )
    window.requested_files_format_combo.currentIndexChanged.connect(
        lambda index: window.set_requested_files_format(
            window.requested_files_format_combo.itemData(index)
        )
    )
    requested_files_layout.addWidget(window.requested_files_format_combo)
    requested_files_layout.addWidget(
        _wrapped_label(
            'Il Markdown contiene percorsi e contenuti completi dei file testuali; i file binari '
            'vengono segnalati ma non incorporati.'
        )
    )
    other_models_layout.addWidget(requested_files_section)
    window.markdown_exchange_settings_group = requested_files_section

    update_format_section, update_format_layout = _section(
        'Formato delle modifiche proposte'
    )
    update_format_layout.addWidget(
        _wrapped_label(
            'Stabilisce cosa deve restituire l’AI dopo aver ricevuto il contesto.'
        )
    )
    window.update_format_combo = QComboBox()
    window.update_format_combo.addItem(_('ZIP — consigliato'), 'zip')
    window.update_format_combo.addItem(_('File Markdown di aggiornamento'), 'text')
    window.update_format_combo.currentIndexChanged.connect(
        lambda index: window.set_update_format(
            window.update_format_combo.itemData(index)
        )
    )
    update_format_layout.addWidget(window.update_format_combo)
    update_format_layout.addWidget(
        _wrapped_label(
            'Con il file Markdown di aggiornamento BridgAI richiede operazioni CREATE, REPLACE e DELETE, '
            'mostra il diff e applica lo stesso piano transazionale usato dagli ZIP.'
        )
    )
    other_models_layout.addWidget(update_format_section)
    window.textual_file_operations_settings_group = update_format_section

    compatibility_button = QToolButton()
    compatibility_button.setObjectName('aiWebCompatibilityButton')
    compatibility_button.setText(_('Compatibilità con le AI Web'))
    compatibility_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    compatibility_button.setArrowType(Qt.RightArrow)
    compatibility_button.setCheckable(True)
    compatibility_button.setAccessibleName(_('Compatibilità con le AI Web'))
    other_models_layout.addWidget(compatibility_button)

    compatibility_panel = QWidget()
    compatibility_panel.setObjectName('aiWebCompatibilityPanel')
    compatibility_layout = QVBoxLayout(compatibility_panel)
    compatibility_layout.setContentsMargins(8, 4, 8, 8)
    compatibility_layout.setSpacing(8)
    compatibility_layout.addWidget(
        _wrapped_label(
            'Il formato dei file richiesti è distinto dal formato delle modifiche proposte.'
        )
    )
    compatibility_table = QLabel(
        _(
            '<table cellspacing="0" cellpadding="6">'
            '<tr><th>AI Web</th><th>Formato dei file richiesti</th>'
            '<th>Formato delle modifiche proposte</th></tr>'
            '<tr><td><b>ChatGPT</b></td><td>ZIP o Markdown</td><td>ZIP o Markdown</td></tr>'
            '<tr><td><b>Claude</b></td><td>ZIP o Markdown</td><td>ZIP o Markdown</td></tr>'
            '<tr><td><b>Gemini Pro</b></td><td>ZIP o Markdown</td><td>Markdown</td></tr>'
            '<tr><td><b>DeepSeek</b></td><td>Markdown</td><td>Markdown</td></tr>'
            '<tr><td><b>Perplexity</b></td><td>Markdown consigliato</td><td>Markdown</td></tr>'
            '<tr><td><b>Microsoft Copilot</b></td><td>Markdown</td><td>Markdown</td></tr>'
            '</table>'
        )
    )
    compatibility_table.setObjectName('aiWebCompatibilityTable')
    compatibility_table.setTextFormat(Qt.RichText)
    compatibility_table.setWordWrap(True)
    compatibility_layout.addWidget(compatibility_table)
    compatibility_layout.addWidget(
        _wrapped_label(
            'ZIP → ZIP è il percorso raccomandato e testato. Le modalità Markdown aumentano la '
            'compatibilità con alcune AI Web, ma non offrono la stessa garanzia operativa; in '
            'particolare, le patch Markdown potrebbero non essere applicabili in tutti i casi.'
        )
    )
    compatibility_panel.setVisible(False)
    compatibility_button.toggled.connect(compatibility_panel.setVisible)
    compatibility_button.toggled.connect(
        lambda expanded: compatibility_button.setArrowType(
            Qt.DownArrow if expanded else Qt.RightArrow
        )
    )
    other_models_layout.addWidget(compatibility_panel)
    window.ai_web_compatibility_button = compatibility_button
    window.ai_web_compatibility_panel = compatibility_panel

    gemini_section, drive_layout = _section('Trasporto ZIP per Gemini')
    drive_layout.addWidget(
        _wrapped_label(
            'Google Drive è soltanto un canale di trasferimento per gli ZIP destinati a Gemini. '
            'Non cambia il formato delle modifiche e viene ignorato quando i file richiesti sono '
            'esportati come Markdown.'
        )
    )
    window.gemini_drive_enabled_check = ToggleSwitch(
        _('Salva gli ZIP dei file richiesti nella cartella Google Drive')
    )
    window.gemini_drive_enabled_check.toggled.connect(window.set_gemini_drive_enabled)
    drive_layout.addWidget(window.gemini_drive_enabled_check)
    drive_path_row = QHBoxLayout()
    window.gemini_drive_path_edit = QLineEdit()
    window.gemini_drive_path_edit.setPlaceholderText(
        _('es. G:\\Il mio Drive\\LocalAIBridge oppure una cartella Drive su macOS')
    )
    window.gemini_drive_path_edit.editingFinished.connect(window.save_gemini_drive_path)
    drive_path_row.addWidget(window.gemini_drive_path_edit, 1)
    drive_path_row.addWidget(_button(_('Sfoglia'), window.choose_gemini_drive_directory))
    drive_layout.addLayout(drive_path_row)
    download_row = QHBoxLayout()
    download_row.addWidget(
        _button(_('Scarica Google Drive per PC'), window.open_google_drive_download)
    )
    download_row.addStretch(1)
    drive_layout.addLayout(download_row)
    other_models_layout.addWidget(gemini_section)
    window.gemini_drive_settings_group = gemini_section

    layout.addWidget(other_models_group)
    window.other_llm_settings_group = other_models_group

    layout.addStretch(1)
    scroll_area.setWidget(content)
    page_layout.addWidget(scroll_area)
    window.settings_scroll_area = scroll_area
    window.refresh_primary_mode_settings()
    window.refresh_prompt_settings()
    window.refresh_web_settings()
    window.refresh_temp_settings()
    window.refresh_external_context_settings()
    window.refresh_ai_assistant_settings()
    window.refresh_gemini_drive_settings()
    window.refresh_preferred_web_ai_settings()
    window.refresh_markdown_exchange_settings()
    window.refresh_textual_file_operations_settings()
    return page
