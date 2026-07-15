from __future__ import annotations

import hashlib
import os
import sys
import time
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
    normalize_web_ai_provider,
    queue_request,
    web_ai_provider_label,
    web_ai_provider_url,
)
from local_ai_bridge.services.temp_storage import latest_zip_file
from local_ai_bridge.web.launcher import (
    browser_extension_service_status,
    project_root,
    start_web_interface,
    start_windows_direct_web_server,
)

HOT_EXTENSION_HANDOFF_SECONDS = 3.0


def _browser_extension_needs_wake(snapshot: dict) -> bool:
    """Return True when a queued request should actively wake the provider tab.

    ``connection_snapshot()["connected"]`` intentionally stays true for a
    fairly long UI status window, but Manifest V3 service workers can sleep
    much sooner. For the actual hand-off we require a very recent heartbeat;
    otherwise opening the selected provider lets the content script trigger an
    immediate poll instead of waiting for Chrome's next alarm cycle.
    """
    try:
        last_seen = float(snapshot.get("last_seen_at") or 0.0)
    except (TypeError, ValueError):
        last_seen = 0.0
    if last_seen <= 0.0:
        return not bool(snapshot.get("connected"))
    return time.time() - last_seen > HOT_EXTENSION_HANDOFF_SECONDS


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
            try:
                browser_extension_service_status(
                    self.settings.web_port,
                    self.settings.browser_extension_token,
                )
                return True
            except (RuntimeError, ValueError):
                pass

            console_options = (
                {"show_console": True}
                if self.settings.windows_show_diagnostic_consoles
                else {}
            )
            if sys.platform == "win32" and self.settings.web_port == 8765:
                result = start_windows_direct_web_server(
                    self.settings.web_port,
                    **console_options,
                )
            else:
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
                    **console_options,
                )
            if result.process is not None:
                self.web_process = result.process
            browser_extension_service_status(
                self.settings.web_port,
                self.settings.browser_extension_token,
            )
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

    def start_browser_extension_web_server(self) -> None:
        if sys.platform != "win32":
            QMessageBox.information(
                self,
                _("Server Web BridgAI"),
                _("Questo avvio diretto è disponibile solo su Windows."),
            )
            return

        script = project_root() / "web_server_force_win.bat"
        if not script.is_file():
            QMessageBox.warning(
                self,
                _("Script server Web non trovato"),
                _("Impossibile trovare lo script Windows: {path}").format(path=script),
            )
            return

        try:
            startfile = getattr(os, "startfile")
            startfile(str(script))
        except (AttributeError, OSError) as exc:
            QMessageBox.warning(
                self,
                _("Avvio server Web non riuscito"),
                str(exc),
            )
            return

        self._show_status(
            _("Server Web avviato in una finestra Windows separata.")
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

    def _wake_browser_extension_provider(self, provider: str) -> None:
        """Open the selected provider only when needed to wake the MV3 worker.

        Chrome can suspend an extension service worker between alarms. Opening the
        provider page lets the content script send an immediate poll message, so a
        queued request does not wait for the next alarm cycle.
        """
        try:
            QDesktopServices.openUrl(QUrl(web_ai_provider_url(provider)))
        except Exception:
            # The extension still has its alarm-based polling fallback.
            return

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
            if not self.ensure_browser_extension_service(silent=True):
                return False
            provider = normalize_web_ai_provider(self.settings.preferred_web_ai)
            snapshot = connection_snapshot()
            wake_provider = _browser_extension_needs_wake(snapshot)
            request = queue_request(
                self.workspace,
                report,
                provider=provider,
            )
            self._browser_extension_seen_response_id = ""
            self._browser_extension_seen_update_path = ""
            self._browser_extension_seen_error_key = ""
            self._browser_extension_fallback_prompt_shown_id = ""
            if wake_provider:
                self._wake_browser_extension_provider(provider)
            self.simple_apply_zip_button.setText(_("Applica aggiornamento · Shift: scegli ZIP"))
            if hasattr(self, "refresh_apply_zip_button_hint"):
                self.refresh_apply_zip_button_hint()
            self._show_status(
                _(
                    "Richiesta pronta per {provider} tramite l’estensione Chrome: {id}"
                ).format(
                    provider=web_ai_provider_label(provider),
                    id=request["request_id"],
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
            if not isinstance(request, dict):
                return
            if request.get("request_kind") == "operational":
                self.handle_operational_browser_request(request)
                return
            if self.workspace is None:
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
                if any(x in error_message.lower() for x in ["zip", "download", "pulsante", "non ha mostrato", "scaricabile", "timeout"]):
                    error_guide = _(
                        "L'estensione non è riuscita a prelevare lo ZIP automaticamente a causa di modifiche strutturali del sito dell'AI.\n\n"
                        "Nessun problema! Scarica il file ZIP cliccando sul pulsante direttamente nella chat del browser. "
                        "BridgAI lo importerà automaticamente dalla tua cartella Download appena completato."
                    )
                    self._show_status(_("Download automatico fallito. Procedi manualmente."))
                    QMessageBox.information(
                        self,
                        _("Importazione manuale richiesta"),
                        error_guide,
                    )
                else:
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
                self._response_received_at = time.time()
                self._show_status(_("Risposta ricevuta automaticamente dall’estensione."))

            if (
                request.get("status") == "waiting_update"
                and hasattr(self, "_response_received_at")
                and time.time() - self._response_received_at > 12.0
                and getattr(self, "_browser_extension_fallback_prompt_shown_id", "") != request_id
            ):
                self._browser_extension_fallback_prompt_shown_id = request_id
                friendly_prompt = _(
                    "Il testo della risposta dell'AI è pronto nella chat!\n\n"
                    "Se l'estensione riscontra difficoltà a scaricare automaticamente lo ZIP dell'aggiornamento, procedi così:\n"
                    "1. Clicca sul pulsante di download dello ZIP direttamente nella chat del browser.\n"
                    "2. BridgAI rileverà all'istante il file all'interno della cartella Download senza bloccare il tuo lavoro."
                )
                QMessageBox.information(
                    self,
                    _("Aggiornamento pronto sulla pagina Web"),
                    friendly_prompt,
                )

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
                self.simple_apply_zip_button.setText(_("Aggiornamento pronto — Applica · Shift: scegli ZIP"))
                hint = self._apply_zip_button_hint() if hasattr(self, "_apply_zip_button_hint") else _("Shift+clic: scegli manualmente il file ZIP da applicare.")
                self.simple_apply_zip_button.setToolTip(ready_message + "\n\n" + hint)
                if hasattr(self.simple_apply_zip_button, "setStatusTip"):
                    self.simple_apply_zip_button.setStatusTip(hint)
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
        timestamps: list[float] = []
        for field in ("created_at", "response_received_at"):
            try:
                value = float(request.get(field) or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0.0:
                timestamps.append(value)
        try:
            local_response_seen_at = float(getattr(self, "_response_received_at", 0.0) or 0.0)
        except (TypeError, ValueError):
            local_response_seen_at = 0.0
        if local_response_seen_at > 0.0:
            timestamps.append(local_response_seen_at)
        ready_after = max(timestamps, default=0.0)
        if ready_after and latest.stat().st_mtime < ready_after - 2.0:
            return None
        context_path = str(request.get("context_zip_path", "")).strip()
        if context_path:
            try:
                if latest.resolve() == Path(context_path).expanduser().resolve(strict=False):
                    return None
            except OSError:
                return None
        return latest
