from __future__ import annotations

import sys

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.widgets import ToggleSwitch, _button
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

def _build_ai_context_group(window) -> QGroupBox:
    group = QGroupBox(_('Contesto AI avanzato'))
    layout = QVBoxLayout(group)
    description = QLabel(
        _(
            'Queste impostazioni non sono mostrate nella modalità super semplice, '
            'ma continuano a essere applicate quando abilitate.'
        )
    )
    description.setWordWrap(True)
    layout.addWidget(description)

    window.include_custom_prompts_check = ToggleSwitch(_('Includi le istruzioni personalizzate nel Super-Report'))
    window.include_custom_prompts_check.toggled.connect(window.set_custom_prompts_enabled)
    layout.addWidget(window.include_custom_prompts_check)

    layout.addWidget(QLabel(_('Prompt globale')))
    window.global_prompt_edit = QPlainTextEdit()
    window.global_prompt_edit.setPlaceholderText(_('Convenzioni, lingua, vincoli architetturali e preferenze valide per tutti i progetti...'))
    window.global_prompt_edit.setMaximumHeight(120)
    layout.addWidget(window.global_prompt_edit)
    global_row = QHBoxLayout()
    global_row.addWidget(_button(_('Salva prompt globale'), window.save_global_prompt))
    global_row.addStretch(1)
    layout.addLayout(global_row)

    layout.addWidget(QLabel(_('Prompt del progetto corrente')))
    project_description = QLabel(_('Il prompt del progetto viene salvato in .bridgai/project.json nel workspace selezionato.'))
    project_description.setWordWrap(True)
    layout.addWidget(project_description)
    window.project_prompt_edit = QPlainTextEdit()
    window.project_prompt_edit.setPlaceholderText(_('Istruzioni specifiche del workspace selezionato...'))
    window.project_prompt_edit.setMaximumHeight(120)
    layout.addWidget(window.project_prompt_edit)
    project_row = QHBoxLayout()
    window.save_project_prompt_button = _button(_('Salva prompt progetto'), window.save_current_project_prompt)
    project_row.addWidget(window.save_project_prompt_button)
    project_row.addStretch(1)
    layout.addLayout(project_row)

    layout.addWidget(QLabel(_('File esclusi dal Super-Report')))
    ignore_description = QLabel(
        _(
            'Modifica .bridgai/ignore senza uscire da BridgAI. Usa un glob per riga, '
            'per esempio dist/, *.sqlite o docs/generated/**.'
        )
    )
    ignore_description.setWordWrap(True)
    layout.addWidget(ignore_description)
    window.project_ignore_edit = QPlainTextEdit()
    window.project_ignore_edit.setPlaceholderText(_('Un glob per riga; le righe vuote e quelle che iniziano con # vengono ignorate.'))
    window.project_ignore_edit.setMaximumHeight(140)
    layout.addWidget(window.project_ignore_edit)
    ignore_row = QHBoxLayout()
    window.save_project_ignore_button = _button(_('Salva file esclusi'), window.save_current_project_ignore)
    window.reload_project_ignore_button = _button(_('Ricarica file esclusi'), window.reload_current_project_ignore)
    ignore_row.addWidget(window.save_project_ignore_button)
    ignore_row.addWidget(window.reload_project_ignore_button)
    ignore_row.addStretch(1)
    layout.addLayout(ignore_row)
    return group


def _build_browser_extension_group(window) -> QGroupBox:
    group = QGroupBox(_('Automazione browser'))
    layout = QVBoxLayout(group)

    description = QLabel(
        _(
            'L’estensione Chrome è facoltativa: quando è disattivata BridgAI mantiene '
            'esattamente il flusso manuale corrente. Quando è attiva può inviare il report, '
            'ricevere la risposta, gestire #scarica e rilevare lo ZIP finale. '
            'L’estensione funziona correttamente solo quando il server Web BridgAI è avviato.'
        )
    )
    description.setWordWrap(True)
    layout.addWidget(description)

    window.browser_extension_enabled_check = ToggleSwitch(
        _('Abilita integrazione con estensione Chrome')
    )
    window.browser_extension_enabled_check.toggled.connect(
        window.set_browser_extension_enabled
    )
    layout.addWidget(window.browser_extension_enabled_check)

    window.browser_extension_auto_send_check = ToggleSwitch(
        _('Invia automaticamente la richiesta preparata')
    )
    window.browser_extension_auto_receive_check = ToggleSwitch(
        _('Acquisisci automaticamente la risposta')
    )
    window.browser_extension_auto_export_check = ToggleSwitch(
        _('Gestisci automaticamente le richieste #scarica')
    )
    window.browser_extension_auto_download_check = ToggleSwitch(
        _('Rileva e scarica automaticamente lo ZIP finale')
    )
    window.browser_extension_option_checks = [
        window.browser_extension_auto_send_check,
        window.browser_extension_auto_receive_check,
        window.browser_extension_auto_export_check,
        window.browser_extension_auto_download_check,
    ]
    for check in window.browser_extension_option_checks:
        check.toggled.connect(lambda _checked: window.save_browser_extension_settings())
        layout.addWidget(check)

    download_hint = QLabel(
        _(
            'La sottocartella degli ZIP si configura nelle opzioni dell’estensione Chrome. '
            'Quando l’estensione è attiva, BridgAI usa automaticamente la stessa cartella; '
            'quando viene disattivata torna alla cartella Download standard.'
        )
    )
    download_hint.setWordWrap(True)
    layout.addWidget(download_hint)

    endpoint_row = QHBoxLayout()
    endpoint_row.addWidget(QLabel(_('Servizio locale:')))
    window.browser_extension_endpoint_edit = QLineEdit()
    window.browser_extension_endpoint_edit.setReadOnly(True)
    endpoint_row.addWidget(window.browser_extension_endpoint_edit, 1)
    layout.addLayout(endpoint_row)

    token_row = QHBoxLayout()
    token_row.addWidget(QLabel(_('Token estensione:')))
    window.browser_extension_token_edit = QLineEdit()
    window.browser_extension_token_edit.setReadOnly(True)
    window.browser_extension_token_edit.setEchoMode(QLineEdit.Password)
    token_row.addWidget(window.browser_extension_token_edit, 1)
    token_row.addWidget(_button(_('Copia token'), window.copy_browser_extension_token))
    layout.addLayout(token_row)

    window.browser_extension_status_label = QLabel(_('Estensione non rilevata.'))
    window.browser_extension_status_label.setWordWrap(True)
    window.browser_extension_status_label.setProperty('class', 'infoBanner')
    layout.addWidget(window.browser_extension_status_label)

    actions = QHBoxLayout()
    actions.addWidget(_button(_('Apri cartella estensione'), window.open_browser_extension_folder))
    if sys.platform == 'win32':
        actions.addWidget(
            _button(
                _('Avvia server Web per l’estensione'),
                window.start_browser_extension_web_server,
            )
        )
    actions.addWidget(_button(_('Verifica connessione'), window.verify_browser_extension_connection))
    actions.addStretch(1)
    layout.addLayout(actions)

    warning = QLabel(
        _(
            'Gli aggiornamenti non vengono mai applicati automaticamente: il pulsante '
            '“Applica aggiornamento” resta sempre sotto il controllo dell’utente.'
        )
    )
    warning.setWordWrap(True)
    layout.addWidget(warning)
    return group

def build_advanced_tab(window) -> QWidget:
    page = QWidget()
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    scroll_area = QScrollArea()
    scroll_area.setObjectName('advancedScrollArea')
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QScrollArea.NoFrame)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    content = QWidget()
    content.setObjectName('advancedScrollContent')
    layout = QVBoxLayout(content)
    layout.setContentsMargins(18, 14, 18, 18)
    layout.setSpacing(14)
    layout.addWidget(_build_ai_context_group(window))
    window.browser_extension_settings_group = _build_browser_extension_group(window)
    layout.addWidget(window.browser_extension_settings_group)
    layout.addWidget(QLabel(_('Skill interne disponibili')))
    window.skills_table = QTableWidget(0, 4)
    window.skills_table.setHorizontalHeaderLabels(['ID', _('Nome'), _('Permessi'), _('Descrizione')])
    window.skills_table.horizontalHeader().setStretchLastSection(True)
    layout.addWidget(window.skills_table)
    layout.addWidget(_button(_('Aggiorna sessioni'), window._refresh_sessions))
    window.sessions_table = QTableWidget(0, 6)
    window.sessions_table.setHorizontalHeaderLabels([_('Sessione'), _('Operazione'), _('Stato'), _('File'), _('Test'), _('Data')])
    window.sessions_table.horizontalHeader().setStretchLastSection(True)
    window.sessions_table.setSelectionBehavior(QTableWidget.SelectRows)
    window.sessions_table.setSelectionMode(QTableWidget.SingleSelection)
    window.sessions_table.itemSelectionChanged.connect(window.show_selected_session)
    layout.addWidget(window.sessions_table)
    window.session_details_edit = QPlainTextEdit()
    window.session_details_edit.setReadOnly(True)
    window.session_details_edit.setPlaceholderText(_('Seleziona una sessione per visualizzare file e verifiche.'))
    window.session_details_edit.setMinimumHeight(140)
    layout.addWidget(window.session_details_edit)
    layout.addStretch(1)
    scroll_area.setWidget(content)
    page_layout.addWidget(scroll_area)
    return page
