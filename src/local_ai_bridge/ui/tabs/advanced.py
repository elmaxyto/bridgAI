from __future__ import annotations

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.widgets import ToggleSwitch, _button
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
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
