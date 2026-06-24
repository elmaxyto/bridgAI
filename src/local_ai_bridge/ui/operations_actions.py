from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QListWidgetItem, QMessageBox

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.services.operational_execution import (
    EXECUTION_COMPLETED,
    OperationalExecutionRecord,
)
from local_ai_bridge.services.operational_missions import (
    CATEGORY_CUSTOM,
    MISSION_ARCHIVED,
    MISSION_DRAFT,
    MISSION_READY,
    PROCEDURE_CSV_MERGE,
    PROCEDURE_WEB_MISSION,
    PROVIDER_CHATGPT,
    MissionError,
    OperationalMission,
)
from local_ai_bridge.ui.operations_presenters import (
    category_label,
    completion_message,
    draft_plan,
    execution_confirmation,
    execution_summary,
    mission_details,
    procedure_label,
    provider_label,
    state_label,
    web_plan,
)

from local_ai_bridge.ui.operations_web_actions import OperationsWebActionsMixin


class OperationsActionsMixin(OperationsWebActionsMixin):
    def _selected_operational_category(self) -> str:
        value = self.operations_category_combo.currentData()
        return str(value or CATEGORY_CUSTOM)

    def _selected_operational_provider(self) -> str:
        value = self.operations_provider_combo.currentData()
        return str(value or PROVIDER_CHATGPT)

    def _selected_operational_procedure(self) -> str:
        value = self.operations_procedure_combo.currentData()
        return str(value or PROCEDURE_CSV_MERGE)

    def _append_operational_inputs(self, paths: list[str]) -> None:
        existing = {
            self.operations_input_list.item(index).text()
            for index in range(self.operations_input_list.count())
        }
        for raw_path in paths:
            path = raw_path.strip()
            if path and path not in existing:
                self.operations_input_list.addItem(path)
                existing.add(path)
        self._refresh_operational_draft_state()

    def add_operational_input_files(self) -> None:
        paths, _used_filter = QFileDialog.getOpenFileNames(
            self,
            _("Seleziona i file di input"),
            filter=_("Tutti i file (*)"),
        )
        self._append_operational_inputs(paths)

    def add_operational_input_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, _("Seleziona una cartella di input"))
        if path:
            self._append_operational_inputs([path])

    def remove_operational_inputs(self) -> None:
        for item in self.operations_input_list.selectedItems():
            self.operations_input_list.takeItem(self.operations_input_list.row(item))
        self._refresh_operational_draft_state()

    def choose_operational_output_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, _("Seleziona la cartella di output"))
        if path:
            self.operations_output_edit.setText(path)
        self._refresh_operational_draft_state()

    def _operational_input_paths(self) -> list[str]:
        return [
            self.operations_input_list.item(index).text()
            for index in range(self.operations_input_list.count())
        ]

    def _refresh_operational_draft_state(self, _value=None) -> None:
        if not hasattr(self, "operations_draft_state_label"):
            return
        inputs = self._operational_input_paths()
        ready = bool(
            self.operations_request_edit.toPlainText().strip()
            and inputs
            and self.operations_output_edit.text().strip()
        )
        self.operations_draft_state_label.setText(
            state_label(MISSION_READY if ready else MISSION_DRAFT)
        )
        visual_state = "ready" if ready else "draft"
        if self.operations_draft_state_label.property("state") != visual_state:
            self.operations_draft_state_label.setProperty("state", visual_state)
            self.operations_draft_state_label.style().unpolish(
                self.operations_draft_state_label
            )
            self.operations_draft_state_label.style().polish(
                self.operations_draft_state_label
            )
        if hasattr(self, "operations_input_count_label"):
            self.operations_input_count_label.setText(
                _("Input selezionati: {count}").format(count=len(inputs))
            )
        if hasattr(self, "operations_start_button"):
            self.operations_start_button.setEnabled(ready)
        local_tools = bool(
            hasattr(self, "operations_local_tools_group")
            and self.operations_local_tools_group.isChecked()
        )
        if local_tools:
            plan = draft_plan(
                self._selected_operational_procedure(),
                len(inputs),
                self.operations_output_edit.text().strip(),
            )
        else:
            plan = web_plan(
                self._selected_operational_category(),
                self._selected_operational_provider(),
                len(inputs),
                self.operations_output_edit.text().strip(),
            )
        self.operations_plan_edit.setPlainText(plan)

    def clear_operational_mission_form(self) -> None:
        self.operations_title_edit.clear()
        self.operations_request_edit.clear()
        self.operations_input_list.clear()
        self.operations_output_edit.clear()
        self.operations_category_combo.setCurrentIndex(0)
        self.operations_provider_combo.setCurrentIndex(0)
        self._refresh_operational_draft_state()
        self.operations_request_edit.setFocus()

    def _operational_title(self) -> str:
        explicit = self.operations_title_edit.text().strip()
        if explicit:
            return explicit
        request = " ".join(self.operations_request_edit.toPlainText().split())
        return request[:72] or category_label(self._selected_operational_category())

    def _create_operational_mission(self, *, procedure_id: str) -> OperationalMission:
        return self.mission_store.create(
            title=self._operational_title(),
            original_request=self.operations_request_edit.toPlainText(),
            procedure_id=procedure_id,
            work_category=self._selected_operational_category(),
            provider=self._selected_operational_provider(),
            workspace=self.workspace,
            input_paths=self._operational_input_paths(),
            output_directory=self.operations_output_edit.text(),
        )

    def save_operational_mission(self) -> None:
        try:
            mission = self._create_operational_mission(procedure_id=PROCEDURE_WEB_MISSION)
        except MissionError as exc:
            QMessageBox.warning(self, _("Missione non valida"), str(exc))
            return
        self.refresh_operational_missions(select_mission_id=mission.mission_id)
        self._show_status(_("Missione salvata nella cronologia operativa."))
        self.clear_operational_mission_form()

    def save_operational_local_mission(self) -> None:
        try:
            mission = self._create_operational_mission(
                procedure_id=self._selected_operational_procedure()
            )
        except MissionError as exc:
            QMessageBox.warning(self, _("Missione non valida"), str(exc))
            return
        self.refresh_operational_missions(select_mission_id=mission.mission_id)
        self._show_status(_("Strumento locale salvato nella cronologia."))

    def refresh_operational_missions(self, select_mission_id: str | None = None) -> None:
        if not hasattr(self, "operations_history_list"):
            return
        self.operations_history_list.clear()
        selected_row = -1
        for row, mission in enumerate(self.mission_store.list_missions(include_archived=True)):
            source_label = (
                provider_label(mission.provider)
                if mission.procedure_id == PROCEDURE_WEB_MISSION
                else procedure_label(mission.procedure_id)
            )
            item = QListWidgetItem(
                f"{mission.title} — {state_label(mission.state)} — {source_label}"
            )
            item.setData(Qt.ItemDataRole.UserRole, mission.mission_id)
            item.setToolTip(mission.updated_at)
            self.operations_history_list.addItem(item)
            if mission.mission_id == select_mission_id:
                selected_row = row
        if selected_row >= 0:
            self.operations_history_list.setCurrentRow(selected_row)
        elif self.operations_history_list.count():
            self.operations_history_list.setCurrentRow(0)
        else:
            self.operations_details_edit.setPlainText(
                _("La cronologia delle missioni apparirà qui.")
            )
            self._set_operational_history_buttons(None)

    def _selected_operational_mission(self) -> OperationalMission | None:
        item = self.operations_history_list.currentItem()
        if item is None:
            return None
        mission_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(mission_id, str):
            return None
        try:
            return self.mission_store.load(mission_id)
        except MissionError as exc:
            self.operations_details_edit.setPlainText(
                _("Impossibile leggere la missione selezionata.") + f"\n\n{exc}"
            )
            return None

    def show_selected_operational_mission(self, _current=None, _previous=None) -> None:
        mission = self._selected_operational_mission()
        if mission is None:
            self._set_operational_history_buttons(None)
            return
        execution = (
            None
            if mission.procedure_id == PROCEDURE_WEB_MISSION
            else self.mission_executor.latest_execution(mission.mission_id)
        )
        self.operations_details_edit.setPlainText(mission_details(mission, execution))
        self._set_operational_history_buttons(mission)

    def _set_operational_history_buttons(self, mission: OperationalMission | None) -> None:
        available = mission is not None
        self.operations_archive_button.setEnabled(
            bool(available and mission.state != MISSION_ARCHIVED)
        )
        self.operations_execute_button.setEnabled(
            bool(
                available
                and mission.procedure_id != PROCEDURE_WEB_MISSION
                and mission.state == MISSION_READY
                and not self._operational_execution_in_progress
            )
        )
        can_import = bool(
            available
            and mission.procedure_id == PROCEDURE_WEB_MISSION
            and mission.state in {MISSION_READY, MISSION_RUNNING}
        )
        self.operations_import_result_button.setEnabled(can_import)
        self.operations_tool_button.setEnabled(
            bool(available and mission.procedure_id == PROCEDURE_WEB_MISSION)
        )
        output = Path(mission.output_directory) if available and mission.output_directory else None
        self.operations_open_output_button.setEnabled(bool(output and output.is_dir()))

    def archive_selected_operational_mission(self) -> None:
        mission = self._selected_operational_mission()
        if mission is None:
            return
        if QMessageBox.question(
            self,
            _("Archivia missione"),
            _("La missione resterà nella cronologia. Procedere?"),
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            archived = self.mission_store.archive(mission.mission_id)
        except MissionError as exc:
            QMessageBox.warning(self, _("Impossibile archiviare la missione"), str(exc))
            return
        self.refresh_operational_missions(select_mission_id=archived.mission_id)

    def execute_selected_operational_mission(self) -> None:
        mission = self._selected_operational_mission()
        if mission is None or self._operational_execution_in_progress:
            return
        if mission.procedure_id == PROCEDURE_WEB_MISSION or mission.state != MISSION_READY:
            return
        if QMessageBox.question(
            self,
            _("Esegui missione"),
            execution_confirmation(mission),
        ) != QMessageBox.StandardButton.Yes:
            return
        self._operational_execution_in_progress = True
        self.operations_execute_button.setEnabled(False)
        self.operations_web_status.setPlainText(_("Esecuzione locale in corso…"))
        self._run_background(
            lambda: self.mission_executor.execute(mission.mission_id),
            self._operational_execution_completed,
            _("Esecuzione missione in corso…"),
            on_finished=self._operational_execution_finished,
        )

    def _operational_execution_completed(self, record: OperationalExecutionRecord) -> None:
        self.refresh_operational_missions(select_mission_id=record.mission_id)
        self.operations_web_status.setPlainText(execution_summary(record))
        if record.state == EXECUTION_COMPLETED:
            QMessageBox.information(
                self,
                _("Missione completata"),
                completion_message(record.procedure_id),
            )
        else:
            QMessageBox.warning(self, _("Missione non riuscita"), record.error)

    def _operational_execution_finished(self) -> None:
        self._operational_execution_in_progress = False
        self.show_selected_operational_mission()

    def open_operational_artifacts_directory(self) -> None:
        mission = self._selected_operational_mission()
        if mission is None:
            return
        path = Path(mission.artifacts_directory)
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_operational_output_directory(self) -> None:
        mission = self._selected_operational_mission()
        if mission is None or not mission.output_directory:
            return
        path = Path(mission.output_directory)
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
