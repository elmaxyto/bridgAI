from __future__ import annotations
from local_ai_bridge.i18n import tr as _
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
from local_ai_bridge.services.git import git_remote_url, push_current_branch
from local_ai_bridge.services.github import GitHubRepository, connect_github_repository, create_github_repository, github_auth_status, github_cli_available, github_login_command, github_setup_git, github_switch_account, list_github_accounts, list_github_repositories
from local_ai_bridge.ui.command_dialog import InteractiveCommandDialog

class GitHubActionsMixin:

    def show_github_status(self) -> None:
        self._run_background(github_auth_status, self._show_tool_output, _('Verifica account GitHub...'))

    def add_github_account(self) -> None:
        if not self._ensure_github_cli():
            return
        program, arguments = github_login_command()
        dialog = InteractiveCommandDialog(_('Aggiungi account GitHub'), program, arguments, "Segui il flusso mostrato qui sotto. GitHub CLI aprirà il browser per autorizzare l'account e conserverà le credenziali fuori dal workspace. Se compare una domanda, scrivi la risposta nel campo in basso.", self)
        dialog.exec()
        if dialog.exit_code == 0:
            self._run_background(github_setup_git, self._show_tool_output, _('Configurazione credenziali Git...'))

    def switch_github_account(self) -> None:
        if not self._ensure_github_cli():
            return
        self._run_background(list_github_accounts, self._choose_github_account, _('Caricamento account GitHub...'))

    def _choose_github_account(self, accounts: list[str]) -> None:
        if not accounts:
            QMessageBox.information(self, _('Nessun account'), _('Nessun account GitHub configurato. Usa prima Aggiungi account.'))
            return
        selected, accepted = QInputDialog.getItem(self, _('Cambia account GitHub'), _('Account attivo:'), accounts, 0, False)
        if accepted and selected:
            self._run_background(lambda: self._switch_and_setup_github_account(selected), self._show_tool_output, _('Cambio account GitHub...'))

    def _switch_and_setup_github_account(self, username: str) -> str:
        switch_output = github_switch_account(username)
        setup_output = github_setup_git()
        return switch_output + '\n\n' + setup_output

    def create_github_repository(self) -> None:
        workspace = self._require_workspace()
        if workspace is None or not self._ensure_github_cli():
            return
        name = self._ask_repository_name(workspace)
        if name is None:
            return
        visibility = self._ask_repository_visibility()
        if visibility is None:
            return
        description, accepted = QInputDialog.getText(self, _('Descrizione repository'), _('Descrizione opzionale:'), QLineEdit.Normal, '')
        if not accepted:
            return
        push = QMessageBox.question(self, _('Push iniziale'), 'Inviare subito a GitHub i commit locali già esistenti?\n\nIl programma non aggiunge file e non crea commit automaticamente.') == QMessageBox.Yes
        label = _('pubblico') if visibility == 'public' else _('privato')
        if QMessageBox.question(self, _('Conferma creazione'), f"Creare il repository GitHub '{name}' come {label}?\n\nPush iniziale: {('sì' if push else 'no')}") != QMessageBox.Yes:
            return
        self._run_background(lambda: create_github_repository(workspace, name, visibility=visibility, description=description, push=push), self._show_tool_output, _('Creazione repository GitHub...'))

    def _ask_repository_name(self, workspace: Path) -> str | None:
        name, accepted = QInputDialog.getText(self, _('Crea repository GitHub'), _('Nome repository (oppure proprietario/nome):'), QLineEdit.Normal, workspace.name)
        return name.strip() if accepted and name.strip() else None

    def _ask_repository_visibility(self) -> str | None:
        label, accepted = QInputDialog.getItem(self, _('Visibilità repository'), _('Visibilità:'), [_('Privato'), _('Pubblico')], 0, False)
        if not accepted:
            return None
        return 'public' if label == _('Pubblico') else 'private'

    def connect_existing_github_repository(self) -> None:
        workspace = self._require_workspace()
        if workspace is None or not self._ensure_github_cli():
            return
        self._run_background(list_github_repositories, lambda repositories: self._choose_repository_to_connect(workspace, repositories), _('Caricamento repository GitHub...'))

    def _choose_repository_to_connect(self, workspace: Path, repositories: list[GitHubRepository]) -> None:
        display_to_slug = {repository.display_name: repository.name_with_owner for repository in repositories}
        selected, accepted = QInputDialog.getItem(self, _('Collega repository GitHub'), _('Scegli un repository oppure scrivi proprietario/nome o un URL GitHub:'), list(display_to_slug), 0, True)
        if not accepted or not selected.strip():
            return
        repository = display_to_slug.get(selected, selected.strip())
        replace = self._confirm_remote_link(workspace, repository)
        if replace is None:
            return
        self._run_background(lambda: connect_github_repository(workspace, repository, replace_existing=replace), self._show_tool_output, _('Collegamento repository GitHub...'))

    def _confirm_remote_link(self, workspace: Path, repository: str) -> bool | None:
        existing = git_remote_url(workspace, 'origin')
        if existing:
            answer = QMessageBox.warning(self, _('Remote origin già presente'), f'Origin è attualmente:\n{existing}\n\nSostituirlo con {repository}?\n\nNon verranno eseguiti pull, merge o push.', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            return True if answer == QMessageBox.Yes else None
        answer = QMessageBox.question(self, _('Conferma collegamento'), f'Collegare il workspace a {repository} come remote origin?\n\nNon verranno eseguiti pull, merge o push.')
        return False if answer == QMessageBox.Yes else None

    def push_to_github(self) -> None:
        workspace = self._require_workspace()
        if workspace is None:
            return
        answer = QMessageBox.warning(self, _('Conferma push'), 'Verrà inviato il branch Git corrente al remote origin.\n\nControlla prima Git status e Git diff. Continuare?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self._run_background(lambda: push_current_branch(workspace), self._show_tool_output, _('Push del branch corrente...'))

    def _ensure_github_cli(self) -> bool:
        if github_cli_available():
            return True
        answer = QMessageBox.information(self, _('GitHub CLI richiesta'), "Per autenticare l'account e creare repository serve GitHub CLI (gh).\n\nAprire la pagina ufficiale di installazione?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl('https://cli.github.com/'))
        return False
