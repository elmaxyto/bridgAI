from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from local_ai_bridge.i18n import current_language, tr as _
from local_ai_bridge.services.browser_extension import queue_operational_request
from local_ai_bridge.services.operational_missions import (
    MISSION_RUNNING,
    PROCEDURE_WEB_MISSION,
    PROVIDER_CHATGPT,
    PROVIDER_CLAUDE,
    PROVIDER_GEMINI,
    MissionError,
)
from local_ai_bridge.services.operational_results import (
    OperationalResultError,
    import_operational_result_zip,
    inspect_operational_result_zip,
)
from local_ai_bridge.services.operational_web import (
    OperationalWebError,
    build_operational_mission_package,
)
from local_ai_bridge.ui.operations_presenters import (
    category_label,
    provider_label,
    result_preview_text,
)


GEMINI_URL = "https://gemini.google.com/"


class OperationsWebActionsMixin:
    def start_operational_web_mission(self) -> None:
        request = self.operations_request_edit.toPlainText().strip()
        if not request:
            QMessageBox.warning(
                self,
                _("Attività non pronta"),
                _("Descrivi prima cosa vuoi realizzare."),
            )
            return
        provider = self._selected_operational_provider()
        superpower = self._selected_operational_superpower()
        if current_language() == "en":
            prompt = (
                "You are the AI Task Assistant for the following activity.\n\n"
                f"USER GOAL:\n{request}\n\n"
                "Before producing the final result, understand the goal and ask only for the "
                "clarifications and attachments that are genuinely necessary. Clearly specify "
                "which documents, PDFs, images, spreadsheets, data, or examples the user should "
                "attach directly in this chat. Do not ask for local paths, technical folders, or "
                "unnecessary setup. When enough material is available, briefly confirm what you "
                "will create and proceed with a high-quality result."
            )
        else:
            prompt = (
                "Sei l’Assistente Attività AI per il seguente lavoro.\n\n"
                f"OBIETTIVO DELL’UTENTE:\n{request}\n\n"
                "Prima di produrre il risultato finale, comprendi l’obiettivo e chiedi soltanto "
                "i chiarimenti e gli allegati realmente necessari. Specifica chiaramente quali "
                "documenti, PDF, immagini, fogli di calcolo, dati o esempi l’utente deve allegare "
                "direttamente in questa chat. Non chiedere percorsi locali, cartelle tecniche o "
                "configurazioni non indispensabili. Quando hai materiale sufficiente, conferma "
                "brevemente cosa realizzerai e procedi con un risultato di qualità."
            )
        if superpower is not None:
            prompt += (
                f"\n\nGUIDED PROMPT: {superpower.title} "
                f"(@superpower:{superpower.superpower_id})\n\n"
                f"{superpower.instructions}"
            )
        QApplication.clipboard().setText(prompt)
        self._open_operational_provider(provider)
        message = _(
            "Prompt guidato copiato negli appunti. Incollalo nella chat e allega direttamente "
            "nell’interfaccia Web soltanto i materiali che l’AI ti richiederà."
        )
        self.operations_web_status.setPlainText(message)
        self._show_status(message)

    def _open_operational_provider(self, provider: str) -> None:
        if provider == PROVIDER_GEMINI:
            url = GEMINI_URL
        elif provider == PROVIDER_CLAUDE:
            url = self.settings.claude_url or "https://claude.ai/"
        else:
            url = self.settings.chatgpt_url or "https://chatgpt.com/"
        QDesktopServices.openUrl(QUrl(url))

    def handle_operational_browser_request(self, request: dict) -> None:
        mission_id = str(request.get("mission_id", ""))
        try:
            mission = self.mission_store.load(mission_id)
        except MissionError:
            return
        status = str(request.get("message", "")).strip()
        if status:
            self.operations_web_status.setPlainText(status)
        if request.get("status") == "error":
            key = f"{mission_id}:{request.get('error', '')}"
            if key != getattr(self, "_operational_seen_error_key", ""):
                self._operational_seen_error_key = key
                QMessageBox.warning(
                    self,
                    _("Missione Web interrotta"),
                    str(request.get("error", "")),
                )
            return
        if request.get("status") != "result_ready":
            return
        path = str(request.get("result_zip_path", ""))
        if not path or not Path(path).is_file():
            return
        self._operational_pending_result_path = path
        self._operational_pending_result_mission_id = mission_id
        if hasattr(self, "operations_history_toggle"):
            self.operations_history_toggle.setChecked(True)
        self.refresh_operational_missions(select_mission_id=mission_id)
        preview = dict(request.get("result_preview") or {})
        self.operations_web_status.setPlainText(result_preview_text(preview))
        self.operations_import_result_button.setEnabled(True)
        if path != getattr(self, "_operational_seen_result_path", ""):
            self._operational_seen_result_path = path
            QMessageBox.information(
                self,
                _("Risultati pronti"),
                _(
                    "Lo ZIP dell’AI è stato verificato. Controlla l’elenco e premi "
                    "“Importa risultati”."
                ),
            )

    def import_operational_result(self) -> None:
        mission = self._selected_operational_mission()
        if mission is None or mission.procedure_id != PROCEDURE_WEB_MISSION:
            return
        pending = getattr(self, "_operational_pending_result_path", "")
        pending_mission = getattr(self, "_operational_pending_result_mission_id", "")
        if pending_mission != mission.mission_id:
            pending = ""
        if not pending or not Path(pending).is_file():
            pending, _selected_filter = QFileDialog.getOpenFileName(
                self,
                _("Seleziona lo ZIP dei risultati"),
                filter=_("Archivi ZIP (*.zip)"),
            )
        if not pending:
            return
        try:
            preview = inspect_operational_result_zip(mission, pending)
        except OperationalResultError as exc:
            QMessageBox.warning(self, _("ZIP risultati non valido"), str(exc))
            return
        if QMessageBox.question(
            self,
            _("Importa risultati"),
            result_preview_text(preview.to_dict())
            + "\n\n"
            + _("I file esistenti non verranno sovrascritti. Importare?"),
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            imported = import_operational_result_zip(
                self.mission_store,
                mission.mission_id,
                pending,
            )
        except (OperationalResultError, OSError) as exc:
            QMessageBox.warning(self, _("Importazione non riuscita"), str(exc))
            return
        self._operational_pending_result_path = ""
        self._operational_pending_result_mission_id = ""
        self.refresh_operational_missions(select_mission_id=mission.mission_id)
        self.operations_web_status.setPlainText(
            _("Risultati importati:")
            + "\n"
            + "\n".join(f"• {path}" for path in imported.output_paths)
        )
        QMessageBox.information(
            self,
            _("Missione completata"),
            _("I risultati sono stati salvati nella cartella autorizzata."),
        )

    def prepare_operational_tool_in_development(self) -> None:
        mission = self._selected_operational_mission()
        if mission is None:
            return
        input_kinds = sorted(
            {Path(path).suffix.lower() or _("cartella") for path in mission.input_paths}
        )
        specification = _(
            "Crea uno strumento locale riutilizzabile per questa missione operativa.\n\n"
            "Obiettivo:\n{request}\n\n"
            "Categoria: {category}\n"
            "Tipi di input previsti: {inputs}\n\n"
            "Vincoli:\n"
            "- non modificare gli originali;\n"
            "- scrivere soltanto in una cartella di output scelta dall’utente;\n"
            "- funzionare offline salvo autorizzazione esplicita;\n"
            "- mostrare errori comprensibili;\n"
            "- non sovrascrivere file esistenti;\n"
            "- includere istruzioni d’uso e test mirati."
        ).format(
            request=mission.original_request,
            category=category_label(mission.work_category),
            inputs=", ".join(input_kinds),
        )
        self.task_edit.setPlainText(specification)
        self.activate_development_mode()
        QMessageBox.information(
            self,
            _("Specifica pronta"),
            _("La richiesta tecnica è stata trasferita alla Modalità Sviluppo."),
        )
