from __future__ import annotations

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.widgets import _button
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

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
    window.pre_apply_summary = QLabel(_('La checklist pre-applicazione apparirà dopo l’analisi del piano.'))
    window.pre_apply_summary.setWordWrap(True)
    window.pre_apply_summary.setProperty('class', 'preApplySummary')
    layout.addWidget(window.pre_apply_summary)
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
