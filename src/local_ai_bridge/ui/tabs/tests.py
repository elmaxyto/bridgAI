from __future__ import annotations

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.widgets import _button
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

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
    github_layout.addWidget(QLabel(_('Modalità semplice: pubblica o aggiorna il progetto con un solo pulsante.')))
    simple_buttons = QHBoxLayout()
    window.simple_github_button = _button(_('Pubblica / Aggiorna GitHub'), window.simple_github_action, 'primary')
    simple_buttons.addWidget(window.simple_github_button)
    simple_buttons.addWidget(_button(_('Apri repository'), window.open_github_repository))
    simple_buttons.addStretch(1)
    github_layout.addLayout(simple_buttons)
    github_advanced = QGroupBox(_('Opzioni avanzate GitHub'))
    github_advanced_layout = QVBoxLayout(github_advanced)
    github_advanced_layout.addWidget(QLabel(_("L'account è gestito da GitHub CLI: le credenziali non vengono salvate nel workspace.")))
    account_buttons = QHBoxLayout()
    for label, callback in ((_('Stato account'), window.show_github_status), (_('Aggiungi account'), window.add_github_account), (_('Cambia account'), window.switch_github_account)):
        account_buttons.addWidget(_button(label, callback))
    account_buttons.addStretch(1)
    github_advanced_layout.addLayout(account_buttons)
    repository_buttons = QHBoxLayout()
    for label, callback in ((_('Crea repository GitHub'), window.create_github_repository), (_('Collega repository esistente'), window.connect_existing_github_repository), (_('Push branch corrente'), window.push_to_github)):
        repository_buttons.addWidget(_button(label, callback))
    repository_buttons.addStretch(1)
    github_advanced_layout.addLayout(repository_buttons)
    github_layout.addWidget(github_advanced)
    layout.addWidget(github_group)
    window.test_output = QPlainTextEdit()
    window.test_output.setReadOnly(True)
    window.test_output.setPlaceholderText(_('Risultati di test, Git e GitHub...'))
    layout.addWidget(window.test_output, 1)
    return page
