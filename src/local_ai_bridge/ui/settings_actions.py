from __future__ import annotations
from local_ai_bridge.i18n import tr as _
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMessageBox
from local_ai_bridge.core.project_prompts import (
    load_project_ignore,
    load_project_prompt,
    save_project_ignore,
    save_project_prompt,
)
from local_ai_bridge.services.temp_storage import clean_managed_temp, configured_temp_root
from local_ai_bridge.web.launcher import start_web_interface, stop_web_interface
from local_ai_bridge.web.security import hash_password
from local_ai_bridge.ui.totp_dialog import enroll_totp
GOOGLE_DRIVE_DOWNLOAD_URL = 'https://support.google.com/drive/answer/7329379'

class SettingsActionsMixin:
    def set_dark_mode(self, enabled: bool) -> None:
        self.settings.dark_mode = bool(enabled)
        self.settings_store.save(self.settings)
        self.apply_theme()
        self._show_status(_('Tema scuro attivato.') if enabled else _('Tema chiaro attivato.'))

    def save_interface_language(self) -> None:
        language = self.language_combo.currentData()
        if not isinstance(language, str) or language == self.settings.language:
            return
        self.settings.language = language
        self.settings_store.save(self.settings)
        answer = QMessageBox.question(
            self,
            _("Lingua interfaccia"),
            _("La nuova lingua sarà applicata dopo il riavvio."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.restart_application()


    def refresh_prompt_settings(self) -> None:
        self.include_custom_prompts_check.blockSignals(True)
        self.include_custom_prompts_check.setChecked(self.settings.include_custom_prompts)
        self.include_custom_prompts_check.blockSignals(False)
        self.global_prompt_edit.setPlainText(self.settings.global_prompt)
        project_prompt = load_project_prompt(self.workspace) if self.workspace else ""
        self.project_prompt_edit.setPlainText(project_prompt)
        self.project_prompt_edit.setEnabled(self.workspace is not None)
        self.save_project_prompt_button.setEnabled(self.workspace is not None)
        project_ignore = load_project_ignore(self.workspace) if self.workspace else ""
        self.project_ignore_edit.setPlainText(project_ignore)
        self.project_ignore_edit.setEnabled(self.workspace is not None)
        self.save_project_ignore_button.setEnabled(self.workspace is not None)
        self.reload_project_ignore_button.setEnabled(self.workspace is not None)

    def set_custom_prompts_enabled(self, enabled: bool) -> None:
        self.settings.include_custom_prompts = bool(enabled)
        self.settings_store.save(self.settings)
        self._show_status(_('Istruzioni personalizzate abilitate.') if enabled else _('Istruzioni personalizzate disabilitate.'))

    def save_global_prompt(self) -> None:
        self.settings.global_prompt = self.global_prompt_edit.toPlainText().strip()
        self.settings_store.save(self.settings)
        self._show_status(_('Prompt globale salvato.'))

    def save_current_project_prompt(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        try:
            save_project_prompt(workspace, self.project_prompt_edit.toPlainText())
        except OSError as exc:
            QMessageBox.critical(self, _('Salvataggio prompt fallito'), str(exc))
            return
        self._show_status(_('Prompt del progetto salvato.'))

    def save_current_project_ignore(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        try:
            save_project_ignore(workspace, self.project_ignore_edit.toPlainText())
        except OSError as exc:
            QMessageBox.critical(self, _('Salvataggio file esclusi fallito'), str(exc))
            return
        self._show_status(_('File esclusi dal Super-Report salvato.'))

    def reload_current_project_ignore(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        self.project_ignore_edit.setPlainText(load_project_ignore(workspace))
        self._show_status(_('File esclusi ricaricato.'))


    def refresh_web_settings(self) -> None:
        self.web_auto_start_check.blockSignals(True)
        self.web_auto_start_check.setChecked(self.settings.web_auto_start)
        self.web_auto_start_check.blockSignals(False)
        self.web_open_browser_check.blockSignals(True)
        self.web_open_browser_check.setChecked(self.settings.web_open_browser)
        self.web_open_browser_check.blockSignals(False)
        self.web_port_edit.setText(str(self.settings.web_port))
        self.web_workspace_root_edit.setText(self.settings.web_workspace_root)
        self.web_remote_access_check.setChecked(self.settings.web_remote_access)
        self.web_username_edit.setText(self.settings.web_username)
        self.web_password_edit.clear()
        self.web_totp_local_bypass_check.blockSignals(True)
        self.web_totp_local_bypass_check.setChecked(self.settings.web_totp_local_bypass)
        self.web_totp_local_bypass_check.blockSignals(False)
        enabled = bool(self.settings.web_totp_enabled and self.settings.web_totp_secret)
        self.web_totp_status_label.setText(
            _('2FA attiva. Codici di recupero disponibili: {count}').format(
                count=len(self.settings.web_totp_recovery_hashes)
            )
            if enabled else _('2FA non configurata.')
        )
        self.web_totp_disable_button.setEnabled(enabled)
        self.web_totp_local_bypass_check.setEnabled(enabled)


    def configure_web_two_factor(self) -> None:
        if not self.save_web_settings():
            return
        username = self.settings.web_username.strip()
        if not username or not self.settings.web_password_hash:
            QMessageBox.warning(
                self,
                _('Configurazione 2FA incompleta'),
                _('Configura e salva prima username e password della Web UI.'),
            )
            return
        enrollment = enroll_totp(self, username)
        if enrollment is None:
            return
        self.settings.web_totp_enabled = True
        self.settings.web_totp_secret = enrollment.secret
        self.settings.web_totp_last_counter = -1
        self.settings.web_totp_recovery_hashes = enrollment.recovery_hashes
        self.settings_store.save(self.settings)
        self.refresh_web_settings()
        self._show_status(_('Autenticazione a due fattori configurata. Riavvia la Web UI per applicarla.'))

    def disable_web_two_factor(self) -> None:
        if not self.settings.web_totp_enabled:
            return
        answer = QMessageBox.question(
            self,
            _('Disabilita 2FA'),
            _('Disabilitare l’autenticazione a due fattori per la Web UI?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.settings.web_totp_enabled = False
        self.settings.web_totp_secret = ''
        self.settings.web_totp_local_bypass = False
        self.settings.web_totp_last_counter = -1
        self.settings.web_totp_recovery_hashes = []
        self.settings_store.save(self.settings)
        self.refresh_web_settings()
        self._show_status(_('Autenticazione a due fattori disabilitata. Riavvia la Web UI per applicarla.'))

    def _stop_owned_web_interface_after_root_change(self) -> None:
        process = getattr(self, "web_process", None)
        if process is None:
            return
        stop_web_interface(process)
        self.web_process = None
        self._show_status(_('Interfaccia web arrestata: riavviala per applicare la nuova root progetti.'))

    def choose_web_workspace_root(self) -> None:
        current = self.settings.web_workspace_root.strip()
        start = current if current and Path(current).is_dir() else str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            self,
            _('Scegli la cartella root dei progetti'),
            start,
        )
        if not selected:
            return
        candidate = Path(selected).expanduser()
        if candidate.is_symlink():
            QMessageBox.warning(
                self,
                _('Cartella root non valida'),
                _('La cartella root dei progetti non può essere un link simbolico.'),
            )
            return
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            QMessageBox.warning(self, _('Cartella root non valida'), str(exc))
            return
        if not resolved.is_dir():
            QMessageBox.warning(
                self,
                _('Cartella root non valida'),
                _('Seleziona una cartella esistente.'),
            )
            return
        self.settings.web_workspace_root = str(resolved)
        self.settings_store.save(self.settings)
        self.refresh_web_settings()
        self._stop_owned_web_interface_after_root_change()
        self._show_status(_('Cartella root progetti impostata: {path}').format(path=resolved))

    def clear_web_workspace_root(self) -> None:
        if not self.settings.web_workspace_root:
            return
        answer = QMessageBox.question(
            self,
            _('Rimuovi cartella root progetti'),
            _(
                'Rimuovere la cartella root dei progetti? La Web UI non mostrerà più '
                'l’elenco dei progetti finché non ne verrà configurata un’altra.'
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.settings.web_workspace_root = ''
        self.settings_store.save(self.settings)
        self.refresh_web_settings()
        self._stop_owned_web_interface_after_root_change()
        self._show_status(_('Cartella root progetti rimossa.'))

    def save_web_settings(self) -> bool:
        try:
            port = int(self.web_port_edit.text().strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, _('Porta non valida'), _('La porta deve essere compresa tra 1 e 65535.'))
            self.web_port_edit.setText(str(self.settings.web_port))
            return False
        username = self.web_username_edit.text().strip()
        password = self.web_password_edit.text()
        remote_access = self.web_remote_access_check.isChecked()
        if password:
            try:
                password_hash = hash_password(password)
            except ValueError as exc:
                QMessageBox.warning(self, _('Password non valida'), str(exc))
                return False
            self.settings.web_password_hash = password_hash
            self.web_password_edit.clear()
        if remote_access and (not username or not self.settings.web_password_hash):
            QMessageBox.warning(
                self,
                _('Credenziali mancanti'),
                _('L’accesso dalla rete richiede username e password.'),
            )
            return False
        if self.settings.web_totp_enabled and (not username or not self.settings.web_password_hash):
            QMessageBox.warning(
                self,
                _('Configurazione 2FA incompleta'),
                _('La 2FA richiede username e password configurati.'),
            )
            return False
        self.settings.web_port = port
        self.settings.web_open_browser = self.web_open_browser_check.isChecked()
        self.settings.web_remote_access = remote_access
        self.settings.web_username = username
        self.settings.web_totp_local_bypass = (
            self.web_totp_local_bypass_check.isChecked()
            if self.settings.web_totp_enabled else False
        )
        self.settings.web_auto_start = self.web_auto_start_check.isChecked()
        self.settings_store.save(self.settings)
        return True

    def start_web_interface_from_settings(self) -> None:
        if not self.save_web_settings():
            return
        try:
            result = start_web_interface(
                self.settings.web_port,
                open_browser=self.settings.web_open_browser,
                workspace_root=self.settings.web_workspace_root or None,
                remote_access=self.settings.web_remote_access,
                username=self.settings.web_username or None,
                password_hash=self.settings.web_password_hash or None,
                totp_secret=(
                    self.settings.web_totp_secret
                    if self.settings.web_totp_enabled else None
                ),
                totp_local_bypass=self.settings.web_totp_local_bypass,
            )
        except Exception as exc:
            QMessageBox.critical(self, _('Avvio interfaccia web fallito'), str(exc))
            return
        if result.process is not None:
            self.web_process = result.process
        message = _('Interfaccia web già attiva.') if result.already_running else _('Interfaccia web avviata.')
        info_url = result.url
        if self.settings.web_remote_access:
            from local_ai_bridge.web.network import local_ipv4_addresses
            ips = local_ipv4_addresses()
            if ips:
                ips_str = ", ".join(f"http://{ip}:{self.settings.web_port}/" for ip in ips)
                info_url = f"{result.url} (Rete locale: {ips_str})"
        self._show_status(f'{message} {info_url}')
        QMessageBox.information(self, _('Interfaccia web'), f'{message}\n{info_url}')

    def stop_web_interface_from_settings(self) -> None:
        process = getattr(self, "web_process", None)
        if process is not None:
            stop_web_interface(process)
            self.web_process = None
            self._show_status(_('Interfaccia web arrestata.'))
            QMessageBox.information(self, _('Interfaccia web'), _('Interfaccia web arrestata.'))
        else:
            from local_ai_bridge.web.launcher import is_web_server_ready
            if is_web_server_ready(self.settings.web_port):
                QMessageBox.warning(
                    self,
                    _('Interfaccia web'),
                    _('L’interfaccia web è in esecuzione in un altro processo. Se hai cambiato impostazioni, chiudi l’altro processo o riavvia il computer per liberare la porta.')
                )
            else:
                QMessageBox.information(self, _('Interfaccia web'), _('L’interfaccia web non è attiva.'))

    def refresh_temp_settings(self) -> None:
        root = configured_temp_root(self.settings.temp_directory)
        self.temp_directory_edit.setText(str(root))

    def refresh_gemini_drive_settings(self) -> None:
        self.gemini_drive_enabled_check.blockSignals(True)
        self.gemini_drive_enabled_check.setChecked(self.settings.gemini_drive_enabled)
        self.gemini_drive_enabled_check.blockSignals(False)
        self.gemini_drive_path_edit.setText(self.settings.gemini_drive_path)

    def refresh_markdown_exchange_settings(self) -> None:
        self.markdown_exchange_mode_check.blockSignals(True)
        self.markdown_exchange_mode_check.setChecked(self.settings.markdown_exchange_mode)
        self.markdown_exchange_mode_check.blockSignals(False)

    def set_markdown_exchange_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        gemini_was_enabled = enabled and self.settings.gemini_drive_enabled
        self.settings.markdown_exchange_mode = enabled
        if gemini_was_enabled:
            self.settings.gemini_drive_enabled = False
            self.refresh_gemini_drive_settings()
        self.settings_store.save(self.settings)
        self.apply_simple_mode()
        if gemini_was_enabled:
            message = _(
                'Modalità Markdown Exchange attivata. Gemini è stata disattivata automaticamente.'
            )
        else:
            message = _(
                'Modalità Markdown Exchange attivata.'
                if enabled else 'Modalità Markdown Exchange disattivata.'
            )
        self._show_status(message)

    def set_gemini_drive_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        markdown_was_enabled = enabled and self.settings.markdown_exchange_mode
        self.settings.gemini_drive_enabled = enabled
        self.settings.gemini_drive_path = self.gemini_drive_path_edit.text().strip()
        if markdown_was_enabled:
            self.settings.markdown_exchange_mode = False
            self.refresh_markdown_exchange_settings()
        self.settings_store.save(self.settings)
        self.apply_simple_mode()
        if markdown_was_enabled:
            message = _(
                'Modalità Gemini attivata. Markdown Exchange è stata disattivata automaticamente.'
            )
        else:
            message = _(
                'Modalità Gemini attivata.' if enabled else 'Modalità Gemini disattivata.'
            )
        self._show_status(message)

    def save_gemini_drive_path(self) -> None:
        path = self.gemini_drive_path_edit.text().strip()
        self.settings.gemini_drive_path = path
        self.settings_store.save(self.settings)
        if path:
            self._show_status(f'Cartella Google Drive impostata: {path}')

    def choose_gemini_drive_directory(self) -> None:
        current = self.gemini_drive_path_edit.text().strip()
        start = current if current and Path(current).is_dir() else str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, _('Seleziona la cartella Google Drive per Gemini'), start)
        if not selected:
            return
        self.gemini_drive_path_edit.setText(selected)
        self.save_gemini_drive_path()

    def open_google_drive_download(self) -> None:
        if not QDesktopServices.openUrl(QUrl(GOOGLE_DRIVE_DOWNLOAD_URL)):
            QMessageBox.warning(self, _('Apertura fallita'), _('Impossibile aprire la pagina ufficiale di Google Drive per desktop.'))

    def choose_temp_directory(self) -> None:
        current = configured_temp_root(self.settings.temp_directory)
        selected = QFileDialog.getExistingDirectory(self, _('Scegli cartella base per i file temporanei'), str(current.parent))
        if not selected:
            return
        self.settings.temp_directory = selected
        self.settings_store.save(self.settings)
        self.refresh_temp_settings()
        self._show_status(f'Cartella temporanea impostata: {self.temp_directory_edit.text()}')

    def open_temp_directory(self) -> None:
        root = configured_temp_root(self.settings.temp_directory)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(root))):
            QMessageBox.warning(self, _('Apertura fallita'), f'Impossibile aprire:\n{root}')

    def clean_temp_directory(self) -> None:
        root = configured_temp_root(self.settings.temp_directory)
        answer = QMessageBox.question(self, _('Pulisci file temporanei'), f'Eliminare tutti i file gestiti da Local AI Bridge in:\n{root}?\n\nIl workspace e i backup delle sessioni non verranno toccati.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.clear_plan()
        result = clean_managed_temp(self.settings.temp_directory)
        self.zip_path_edit.clear()
        QMessageBox.information(self, _('Pulizia completata'), f'File rimossi: {result.files_removed}\nCartelle rimosse: {result.directories_removed}\nSpazio rilevato: {result.bytes_removed / 1024:.1f} KiB')
        self._show_status(_('Cartella temporanea pulita.'))
