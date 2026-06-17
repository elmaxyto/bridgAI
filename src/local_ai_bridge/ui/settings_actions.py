from __future__ import annotations
from local_ai_bridge.i18n import tr as _
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMessageBox
from local_ai_bridge.services.temp_storage import clean_managed_temp, configured_temp_root
from local_ai_bridge.web.launcher import start_web_interface, stop_web_interface
from local_ai_bridge.web.security import hash_password
GOOGLE_DRIVE_DOWNLOAD_URL = 'https://support.google.com/drive/answer/7329379'

class SettingsActionsMixin:
    def set_dark_mode(self, enabled: bool) -> None:
        self.settings.dark_mode = bool(enabled)
        self.settings_store.save(self.settings)
        self.apply_theme()
        self._show_status(_('Modalità scura attivata.') if enabled else _('Modalità chiara attivata.'))

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



    def refresh_web_settings(self) -> None:
        self.web_open_browser_check.blockSignals(True)
        self.web_open_browser_check.setChecked(self.settings.web_open_browser)
        self.web_open_browser_check.blockSignals(False)
        self.web_port_edit.setText(str(self.settings.web_port))
        self.web_workspace_root_edit.setText(self.settings.web_workspace_root)
        self.web_remote_access_check.setChecked(self.settings.web_remote_access)
        self.web_username_edit.setText(self.settings.web_username)
        self.web_password_edit.clear()

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
        self.settings.web_port = port
        self.settings.web_open_browser = self.web_open_browser_check.isChecked()
        self.settings.web_remote_access = remote_access
        self.settings.web_username = username
        self.settings.web_auto_start = False
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

    def set_gemini_drive_enabled(self, enabled: bool) -> None:
        self.settings.gemini_drive_enabled = enabled
        self.settings.gemini_drive_path = self.gemini_drive_path_edit.text().strip()
        self.settings_store.save(self.settings)
        self.apply_simple_mode()
        state = 'abilitata' if enabled else 'disabilitata'
        self._show_status(f'Modalità Gemini con Google Drive {state}.')

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
