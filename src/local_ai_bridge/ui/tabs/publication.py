from __future__ import annotations

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.widgets import _button
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QHeaderView,
    QSizePolicy,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

def build_publication_tab(window) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)

    intro = QGroupBox(_('Pubblica il progetto'))
    intro_layout = QVBoxLayout(intro)
    title = QLabel(_('Metti il progetto su GitHub senza usare comandi Git.'))
    title.setWordWrap(True)
    intro_layout.addWidget(title)

    status_group = QGroupBox(_('Stato pubblicazione'))
    status_layout = QFormLayout(status_group)
    window.publication_account_status = QLabel(_('Controllo account…'))
    window.publication_repository_status = QLabel(_('Nessun progetto selezionato'))
    window.publication_changes_status = QLabel('—')
    window.publication_repository_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
    status_layout.addRow(_('Account GitHub:'), window.publication_account_status)
    status_layout.addRow(_('Repository:'), window.publication_repository_status)
    status_layout.addRow(_('Stato:'), window.publication_changes_status)
    intro_layout.addWidget(status_group)

    window.publication_create_group = QGroupBox(_('Prima pubblicazione'))
    create_form = QFormLayout(window.publication_create_group)
    window.publication_repo_name = QLineEdit()
    window.publication_repo_name.setPlaceholderText(_('nome-progetto'))
    window.publication_visibility = QComboBox()
    window.publication_visibility.addItem(_('Privata'), 'private')
    window.publication_visibility.addItem(_('Pubblica'), 'public')
    create_form.addRow(_('Nome repository:'), window.publication_repo_name)
    create_form.addRow(_('Visibilità:'), window.publication_visibility)
    intro_layout.addWidget(window.publication_create_group)

    primary_row = QHBoxLayout()
    window.publication_primary_button = _button(_('Crea e pubblica'), window.publish_from_publication_tab, 'primary')
    window.publication_open_button = _button(_('Apri il progetto su GitHub'), window.open_github_repository)
    window.publication_open_button.setEnabled(False)
    primary_row.addWidget(window.publication_primary_button)
    primary_row.addWidget(window.publication_open_button)
    primary_row.addStretch(1)
    intro_layout.addLayout(primary_row)

    secondary_row = QHBoxLayout()
    secondary_row.addWidget(_button(_('Accedi a GitHub'), window.add_github_account))
    secondary_row.addWidget(_button(_('Usa un progetto GitHub già esistente'), window.connect_existing_github_repository))
    secondary_row.addWidget(_button(_('Controlla di nuovo'), window.refresh_publication_tab))
    secondary_row.addStretch(1)
    intro_layout.addLayout(secondary_row)

    note = QLabel(_('Gli strumenti Git tecnici restano nella scheda “Test, Git e GitHub” e sono nascosti nella modalità semplice.'))
    note.setWordWrap(True)
    intro_layout.addWidget(note)
    layout.addWidget(intro)

    history_group = QGroupBox(_('Modifiche applicate a questo progetto'))
    history_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    history_layout = QVBoxLayout(history_group)

    history_header = QHBoxLayout()
    history_help = QLabel(_('Storico permanente del progetto aperto, salvato anche in BRIDGAI_HISTORY.md.'))
    history_help.setWordWrap(True)
    window.publication_history_summary = QLabel('—')
    window.publication_history_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    window.publication_history_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
    history_header.addWidget(history_help, 1)
    history_header.addWidget(window.publication_history_summary, 0)
    history_layout.addLayout(history_header)

    window.publication_applied_history = QTreeWidget()
    window.publication_applied_history.setColumnCount(5)
    window.publication_applied_history.setHeaderLabels([_('Quando'), _('Tipo'), _('Stato'), _('Messaggio'), _('File')])
    window.publication_applied_history.setRootIsDecorated(False)
    window.publication_applied_history.setAlternatingRowColors(True)
    window.publication_applied_history.setUniformRowHeights(True)
    window.publication_applied_history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    window.publication_applied_history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    window.publication_applied_history.setMinimumHeight(360)
    window.publication_applied_history.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    history_header_view = window.publication_applied_history.header()
    history_header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    history_header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    history_header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    history_header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    history_header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    history_layout.addWidget(window.publication_applied_history, 1)
    layout.addWidget(history_group, 1)

    return page
