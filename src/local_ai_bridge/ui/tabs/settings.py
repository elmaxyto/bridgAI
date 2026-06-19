from __future__ import annotations

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.widgets import ToggleSwitch, _button
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
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
    window.simple_mode_check = ToggleSwitch(_('Modalità super semplice'))
    window.simple_mode_check.setToolTip(
        _('Mostra un flusso guidato e mantiene le funzioni avanzate nascoste.')
    )
    window.simple_mode_check.setChecked(window.settings.simple_mode)
    window.simple_mode_check.toggled.connect(window._save_simple_mode)
    interface_layout.addWidget(window.simple_mode_check)

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
    web_group_layout.addWidget(projects_section)

    layout.addWidget(web_group)
    window.project_root_settings_group = projects_section
    window.advanced_settings_groups.append(web_group)

    other_models_group = QGroupBox(_('Altri modelli LLM (Beta)'))
    other_models_layout = QVBoxLayout(other_models_group)
    beta_warning = _wrapped_label(
        'Queste modalità sono in beta: il funzionamento non è garantito. Per il flusso più '
        'affidabile consigliamo ChatGPT o Claude. Puoi comunque provarle, controllando sempre '
        'con attenzione l’anteprima prima di applicare modifiche.'
    )
    beta_warning.setProperty('class', 'warningBanner')
    other_models_layout.addWidget(beta_warning)
    other_models_layout.addWidget(
        _wrapped_label(
            'Gemini e Markdown Exchange sono modalità alternative: attivandone una, l’altra '
            'viene disattivata automaticamente.'
        )
    )

    gemini_section, drive_layout = _section('Utilizzo Gemini')
    drive_layout.addWidget(
        _wrapped_label(
            'La modalità Gemini sostituisce ChatGPT e Claude nel flusso semplice. BridgAI crea '
            'lo ZIP dei file richiesti nella cartella Drive, la cui sincronizzazione resta '
            'affidata al client ufficiale Google Drive. Gemini restituisce poi testo con '
            'percorsi e blocchi SEARCH/REPLACE, analizzato localmente prima dell’applicazione.'
        )
    )
    window.gemini_drive_enabled_check = ToggleSwitch(
        _('Abilita modalità Gemini con Google Drive')
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

    markdown_section, markdown_layout = _section('Utilizzo Markdown')
    markdown_layout.addWidget(
        _wrapped_label('Attiva per usare file .md invece di ZIP con modelli come Perplexity')
    )
    window.markdown_exchange_mode_check = ToggleSwitch(
        _('Esporta file come Markdown / Importa risposta Markdown')
    )
    window.markdown_exchange_mode_check.setToolTip(
        _('I file binari vengono segnalati ma non incorporati nel documento Markdown.')
    )
    window.markdown_exchange_mode_check.toggled.connect(window.set_markdown_exchange_mode)
    markdown_layout.addWidget(window.markdown_exchange_mode_check)
    other_models_layout.addWidget(markdown_section)
    window.markdown_exchange_settings_group = markdown_section
    window.advanced_settings_groups.append(markdown_section)

    layout.addWidget(other_models_group)
    window.other_llm_settings_group = other_models_group

    layout.addStretch(1)
    scroll_area.setWidget(content)
    page_layout.addWidget(scroll_area)
    window.settings_scroll_area = scroll_area
    window.refresh_prompt_settings()
    window.refresh_web_settings()
    window.refresh_temp_settings()
    window.refresh_gemini_drive_settings()
    window.refresh_markdown_exchange_settings()
    return page
