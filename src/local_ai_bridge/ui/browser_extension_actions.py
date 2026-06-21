from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.services.browser_extension import (
    browser_extension_directory,
    connection_snapshot,
    ensure_extension_token,
    mark_update_ready,
    queue_request,
)
from local_ai_bridge.services.temp_storage import latest_zip_file
from local_ai_bridge.web.launcher import (
    browser_extension_service_status,
    start_web_interface,
)


class BrowserExtensionActionsMixin:
    def _refresh_extension_managed_update_directory(self) -> None:
        try:
            persisted = self.settings_store.load().update_zip_directory
        except Exception:
            return
        if persisted == self.settings.update_zip_directory:
            return
        self.settings.update_zip_directory = persisted
        for name in ("update_zip_directory_edit", "settings_update_zip_directory_edit"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setText(persisted)

    def refresh_browser_extension_settings(self) -> None:
        self._refresh_extension_managed_update_directory()
        if not hasattr(self, "browser_extension_enabled_check"):
            return
        values = (
            ("browser_extension_enabled_check", self.settings.browser_extension_enabled),
            ("browser_extension_auto_send_check", self.settings.browser_extension_auto_send),
            ("browser_extension_auto_receive_check", self.settings.browser_extension_auto_receive),
            ("browser_extension_auto_export_check", self.settings.browser_extension_auto_export),
            ("browser_extension_auto_download_check", self.settings.browser_extension_auto_download),
        )
        for name, checked in values:
            widget = getattr(self, name)
            widget.blockSignals(True)
            widget.setChecked(bool(checked))
            widget.blockSignals(False)

        enabled = bool(self.settings.browser_extension_enabled)
        for check in self.browser_extension_option_checks:
            check.setEnabled(enabled)
        self.browser_extension_endpoint_edit.setText(
            f"http://127.0.0.1:{self.settings.web_port}/api/extension/status"
        )
        self.browser_extension_token_edit.setText(self.settings.browser_extension_token)

        snapshot = connection_snapshot()
        request = snapshot.get("request") or {}
        if not enabled:
            status = _("Automazione browser disattivata. Il flusso manuale resta invariato.")
        elif snapshot.get("connected"):
            version = snapshot.get("extension_version") or "?"
            request_status = request.get("message") or _("Nessuna richiesta in attesa.")
            status = _("Estensione connessa (versione {version}). {status}").format(
                version=version,
                status=request_status,
            )
        else:
            status = _(
                "Servizio pronto, estensione non rilevata. Configura porta e token nelle opzioni Chrome."
            )
        effective_directory = (
            self.settings.update_zip_directory.strip()
            or str(Path.home() / "Downloads")
        )
        status += " " + _("Cartella ZIP: {path}.").format(path=effective_directory)
        self.browser_extension_status_label.setText(status)

    def set_browser_extension_enabled(self, enabled: bool) -> None:
        self.settings.browser_extension_enabled = bool(enabled)
        if enabled:
            self.settings.browser_extension_token = ensure_extension_token(
                self.settings.browser_extension_token
            )
        else:
            self.settings.update_zip_directory = ""
            for name in ("update_zip_directory_edit", "settings_update_zip_directory_edit"):
                widget = getattr(self, name, None)
                if widget is not None:
                    widget.setText("")
        self.settings_store.save(self.settings)
        self.refresh_browser_extension_settings()
        if enabled:
            self.ensure_browser_extension_service(silent=True)
        self._show_status(
            _("Automazione browser attivata.")
            if enabled
            else _("Automazione browser disattivata.")
        )

    def save_browser_extension_settings(self) -> None:
        if not hasattr(self, "browser_extension_option_checks"):
            return
        self.settings.browser_extension_auto_send = (
            self.browser_extension_auto_send_check.isChecked()
        )
        self.settings.browser_extension_auto_receive = (
            self.browser_extension_auto_receive_check.isChecked()
        )
        self.settings.browser_extension_auto_export = (
            self.browser_extension_auto_export_check.isChecked()
        )
        self.settings.browser_extension_auto_download = (
            self.browser_extension_auto_download_check.isChecked()
        )
        self.settings_store.save(self.settings)

    def ensure_browser_extension_service(self, *, silent: bool = False) -> bool:
        if not self.settings.browser_extension_enabled:
            return False
        try:
            result = start_web_interface(
                self.settings.web_port,
                open_browser=False,
                workspace_root=self.settings.web_workspace_root or None,
                remote_access=self.settings.web_remote_access,
                username=self.settings.web_username or None,
                password_hash=self.settings.web_password_hash or None,
                totp_secret=(
                    self.settings.web_totp_secret
                    if self.settings.web_totp_enabled
                    else None
                ),
                totp_local_bypass=self.settings.web_totp_local_bypass,
            )
            if result.process is not None:
                self.web_process = result.process
            return True
        except Exception as exc:
            if not silent:
                QMessageBox.warning(
                    self,
                    _("Servizio estensione non disponibile"),
                    str(exc),
                )
            self._show_status(
                _("Servizio estensione non disponibile: {error}").format(error=exc)
            )
            return False

    def _start_browser_extension_if_enabled(self) -> None:
        if self.settings.browser_extension_enabled:
            self.ensure_browser_extension_service(silent=True)

    def copy_browser_extension_token(self) -> None:
        token = self.settings.browser_extension_token.strip()
        if not token:
            QMessageBox.information(
                self,
                _("Token estensione"),
                _("Abilita prima l’integrazione con l’estensione Chrome."),
            )
            return
        QApplication.clipboard().setText(token)
        self._show_status(_("Token dell’estensione copiato negli appunti."))

    def open_browser_extension_folder(self) -> None:
        directory = browser_extension_directory()
        if not directory.is_dir():
            QMessageBox.warning(
                self,
                _("Estensione non trovata"),
                _(
                    "La cartella dell’estensione Chrome non è disponibile in questa installazione."
                ),
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
            QMessageBox.warning(
                self,
                _("Apertura cartella non riuscita"),
                str(directory),
            )

    def verify_browser_extension_connection(self) -> None:
        if not self.settings.browser_extension_enabled:
            QMessageBox.information(
                self,
                _("Automazione browser"),
                _("Abilita prima l’integrazione con l’estensione Chrome."),
            )
            return
        self.ensure_browser_extension_service(silent=True)
        try:
            payload = browser_extension_service_status(
                self.settings.web_port,
                self.settings.browser_extension_token,
            )
        except Exception as exc:
            QMessageBox.warning(self, _("Estensione non connessa"), str(exc))
            return
        self.refresh_browser_extension_settings()
        request_status = payload.get("request_status") or _("Nessuna richiesta in attesa.")
        QMessageBox.information(
            self,
            _("Automazione browser"),
            _("Servizio locale raggiungibile. {status}").format(status=request_status),
        )

    def queue_report_with_browser_extension(self, report: str) -> bool:
        enabled = (
            self.settings.browser_extension_enabled
            and self.settings.browser_extension_auto_send
            and not self.settings.gemini_drive_enabled
            and not self.settings.markdown_exchange_mode
            and self.workspace is not None
        )
        if not enabled:
            return False
        try:
            request = queue_request(
                self.workspace,
                report,
                provider="chatgpt",
            )
            self._browser_extension_seen_response_id = ""
            self._browser_extension_seen_update_path = ""
            self._browser_extension_seen_error_key = ""
            self.simple_apply_zip_button.setText(_("Applica aggiornamento"))
            self.ensure_browser_extension_service(silent=True)
            self._show_status(
                _("Richiesta pronta per l’estensione Chrome: {id}").format(
                    id=request["request_id"]
                )
            )
            return True
        except Exception as exc:
            self._show_status(
                _(
                    "Automazione non disponibile; puoi continuare manualmente: {error}"
                ).format(error=exc)
            )
            return False

    def poll_browser_extension(self) -> None:
        if not self.settings.browser_extension_enabled:
            return
        try:
            self._refresh_extension_managed_update_directory()
            snapshot = connection_snapshot()
            request = snapshot.get("request")
            if hasattr(self, "browser_extension_status_label"):
                self.refresh_browser_extension_settings()
            if not isinstance(request, dict) or self.workspace is None:
                return
            try:
                request_workspace = Path(str(request.get("workspace", ""))).resolve()
            except OSError:
                return
            if request_workspace != self.workspace.resolve():
                return

            request_id = str(request.get("request_id", ""))
            error_message = str(request.get("error", "")).strip()
            error_key = f"{request_id}:{error_message}"
            if (
                request.get("status") == "error"
                and error_message
                and error_key != getattr(self, "_browser_extension_seen_error_key", "")
            ):
                self._browser_extension_seen_error_key = error_key
                self._show_status(
                    _("Automazione browser interrotta: {error}").format(
                        error=error_message
                    )
                )
                QMessageBox.warning(
                    self,
                    _("Automazione browser interrotta"),
                    error_message,
                )

            response_text = str(request.get("response_text", ""))
            response_digest = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
            response_key = f"{request_id}:{response_digest}"
            if (
                self.settings.browser_extension_auto_receive
                and response_text.strip()
                and response_key != self._browser_extension_seen_response_id
            ):
                self.response_edit.setPlainText(response_text)
                self._browser_extension_seen_response_id = response_key
                self._show_status(_("Risposta ricevuta automaticamente dall’estensione."))

            if (
                request.get("status") == "waiting_update"
                and self.settings.browser_extension_auto_download
                and not request.get("update_zip_path")
            ):
                adopted = self._find_downloaded_extension_zip(request)
                if adopted is not None:
                    request = mark_update_ready(request_id, adopted)

            update_path = str(request.get("update_zip_path", ""))
            if (
                request.get("status") == "update_ready"
                and update_path
                and update_path != self._browser_extension_seen_update_path
                and Path(update_path).is_file()
            ):
                self._browser_extension_seen_update_path = update_path
                ready_message = _(
                    "Lo ZIP è stato ricevuto. L’applicazione resta manuale "
                    "e mostrerà l’anteprima."
                )
                self.zip_path_edit.setText(update_path)
                self.simple_apply_zip_button.setEnabled(True)
                self.simple_apply_zip_button.setText(_("Aggiornamento pronto — Applica"))
                self.simple_apply_zip_button.setToolTip(ready_message)
                self._show_status(
                    _("ZIP dell’aggiornamento ricevuto: {path}").format(
                        path=update_path
                    )
                )
                QMessageBox.information(
                    self,
                    _("Aggiornamento pronto — Applica"),
                    ready_message,
                )
        except (OSError, ValueError, TimeoutError):
            return

    def _find_downloaded_extension_zip(self, request: dict) -> Path | None:
        directories: list[Path] = []
        configured = self.settings.update_zip_directory.strip()
        if configured:
            directories.append(Path(configured).expanduser())
        downloads = Path.home() / "Downloads"
        if downloads not in directories:
            directories.append(downloads)
        candidates = [
            item
            for directory in directories
            if directory.is_dir()
            for item in [latest_zip_file(directory)]
            if item is not None
        ]
        if not candidates:
            return None
        latest = max(candidates, key=lambda item: item.stat().st_mtime)
        created_at = float(request.get("created_at") or 0.0)
        context_path = str(request.get("context_zip_path", ""))
        if latest.stat().st_mtime < created_at - 2.0:
            return None
        if str(latest.resolve()) == context_path:
            return None
        return latest
