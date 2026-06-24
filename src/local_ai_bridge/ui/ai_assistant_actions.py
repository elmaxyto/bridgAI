from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from local_ai_bridge.core.settings import (
    AI_ASSISTANT_CLOUD_PROVIDERS,
    AI_ASSISTANT_SOURCES,
)
from local_ai_bridge.i18n import tr as _
from local_ai_bridge.services.temp_storage import managed_subdir


AI_ASSISTANT_MODEL_SUFFIXES = frozenset({".litertlm", ".gguf"})


def _copy_ai_assistant_model(source: Path, target: Path) -> Path:
    shutil.copy2(source, target)
    return target


class AIAssistantActionsMixin:
    def _ai_assistant_model_directory(self) -> Path:
        return managed_subdir(self.settings.temp_directory, "ai_models")

    def _installed_ai_assistant_model(self) -> Path | None:
        directory = self._ai_assistant_model_directory()
        try:
            candidates = [
                path
                for path in directory.iterdir()
                if path.is_file()
                and path.suffix.lower() in AI_ASSISTANT_MODEL_SUFFIXES
            ]
            if not candidates:
                return None
            return max(candidates, key=lambda path: path.stat().st_mtime)
        except OSError:
            return None

    def _sync_ai_assistant_source_ui(self) -> None:
        source = self.ai_assistant_source_combo.currentData()
        index = {
            "gemma_internal": 0,
            "ollama": 1,
            "cloud_provider": 2,
        }.get(source, 0)
        self.ai_assistant_source_stack.setCurrentIndex(index)
        self.ai_assistant_options_widget.setEnabled(
            bool(self.ai_assistant_enabled_check.isChecked())
        )

    def refresh_ai_assistant_settings(self) -> None:
        controls = (
            self.ai_assistant_enabled_check,
            self.ai_assistant_source_combo,
            self.ai_assistant_cloud_provider_combo,
            self.ai_assistant_ollama_url_edit,
            self.ai_assistant_ollama_model_edit,
            self.ai_assistant_cloud_key_edit,
            self.ai_assistant_cloud_model_edit,
        )
        for control in controls:
            control.blockSignals(True)
        try:
            self.ai_assistant_enabled_check.setChecked(
                self.settings.ai_assistant_enabled
            )
            source_index = self.ai_assistant_source_combo.findData(
                self.settings.ai_assistant_source
            )
            self.ai_assistant_source_combo.setCurrentIndex(max(0, source_index))
            provider_index = self.ai_assistant_cloud_provider_combo.findData(
                self.settings.ai_assistant_cloud_provider
            )
            self.ai_assistant_cloud_provider_combo.setCurrentIndex(
                max(0, provider_index)
            )
            self.ai_assistant_ollama_url_edit.setText(
                self.settings.ai_assistant_ollama_url
            )
            self.ai_assistant_ollama_model_edit.setText(
                self.settings.ai_assistant_ollama_model
            )
            self.ai_assistant_cloud_key_edit.setText(
                self.settings.ai_assistant_cloud_key
            )
            self.ai_assistant_cloud_model_edit.setText(
                self.settings.ai_assistant_cloud_model
            )
        finally:
            for control in controls:
                control.blockSignals(False)

        model = self._installed_ai_assistant_model()
        downloaded = model is not None
        if downloaded != self.settings.ai_assistant_gemma_downloaded:
            self.settings.ai_assistant_gemma_downloaded = downloaded
            self.settings_store.save(self.settings)
        model_directory = self._ai_assistant_model_directory()
        if model is None:
            self.ai_assistant_gemma_status_label.setText(
                _(
                    "Modello integrato non ancora disponibile. Seleziona un file "
                    ".litertlm o .gguf da copiare in:\n{path}"
                ).format(path=model_directory)
            )
        else:
            self.ai_assistant_gemma_status_label.setText(
                _("Modello pronto: {name}\nCartella: {path}").format(
                    name=model.name,
                    path=model_directory,
                )
            )
        self._sync_ai_assistant_source_ui()

    def set_ai_assistant_enabled(self, enabled: bool) -> None:
        self.settings.ai_assistant_enabled = bool(enabled)
        self.settings_store.save(self.settings)
        self._sync_ai_assistant_source_ui()
        self._show_status(
            _(
                "Assistente AI abilitato. Le funzioni extra useranno la sorgente "
                "configurata."
            )
            if enabled
            else _(
                "Assistente AI disabilitato. Restano attivi i fallback locali con "
                "espressioni regolari ed euristiche."
            )
        )

    def save_ai_assistant_source(self) -> None:
        source = self.ai_assistant_source_combo.currentData()
        if source not in AI_ASSISTANT_SOURCES:
            source = "gemma_internal"
        self.settings.ai_assistant_source = source
        self.settings_store.save(self.settings)
        self._sync_ai_assistant_source_ui()
        self._show_status(_("Sorgente Assistente AI salvata."))

    def save_ai_assistant_settings(self) -> None:
        source = self.ai_assistant_source_combo.currentData()
        provider = self.ai_assistant_cloud_provider_combo.currentData()
        self.settings.ai_assistant_source = (
            source if source in AI_ASSISTANT_SOURCES else "gemma_internal"
        )
        self.settings.ai_assistant_ollama_url = (
            self.ai_assistant_ollama_url_edit.text().strip()
            or "http://localhost:11434"
        )
        self.settings.ai_assistant_ollama_model = (
            self.ai_assistant_ollama_model_edit.text().strip()
        )
        self.settings.ai_assistant_cloud_provider = (
            provider if provider in AI_ASSISTANT_CLOUD_PROVIDERS else "groq"
        )
        self.settings.ai_assistant_cloud_key = (
            self.ai_assistant_cloud_key_edit.text().strip()
        )
        self.settings.ai_assistant_cloud_model = (
            self.ai_assistant_cloud_model_edit.text().strip()
        )
        self.settings_store.save(self.settings)
        self._sync_ai_assistant_source_ui()
        self._show_status(_("Configurazione Assistente AI salvata."))

    def download_ai_assistant_gemma_model(self) -> None:
        selected, _selected_filter = QFileDialog.getOpenFileName(
            self,
            _("Seleziona il modello AI scaricato"),
            str(Path.home()),
            _("Modelli AI (*.litertlm *.gguf)"),
        )
        if not selected:
            return
        source = Path(selected).expanduser()
        if (
            not source.is_file()
            or source.suffix.lower() not in AI_ASSISTANT_MODEL_SUFFIXES
        ):
            QMessageBox.warning(
                self,
                _("Modello non valido"),
                _("Seleziona un file di pesi con estensione .litertlm o .gguf."),
            )
            return

        try:
            target_directory = self._ai_assistant_model_directory()
            source_resolved = source.resolve(strict=True)
            target = target_directory / source.name
            counter = 2
            while target.exists() and target.resolve() != source_resolved:
                target = (
                    target_directory
                    / f"{source.stem}-{counter}{source.suffix}"
                )
                counter += 1
        except OSError as exc:
            QMessageBox.critical(self, _("Copia modello fallita"), str(exc))
            return

        if target.resolve() == source_resolved:
            self._ai_assistant_model_copy_finished(target)
            return
        self._run_background(
            lambda: _copy_ai_assistant_model(source_resolved, target),
            self._ai_assistant_model_copy_finished,
            _("Copia del modello AI nella cartella temporanea..."),
        )

    def _ai_assistant_model_copy_finished(self, target: Path) -> None:
        self.settings.ai_assistant_gemma_downloaded = True
        self.settings_store.save(self.settings)
        self.refresh_ai_assistant_settings()
        self._show_status(
            _(
                "Modello AI copiato nella cartella temporanea gestita: {path}"
            ).format(path=target)
        )
