from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.services.operational_missions import (
    PROCEDURE_CSV_MERGE,
    PROCEDURE_INPUT_INVENTORY,
)
from local_ai_bridge.ui.widgets import ToggleSwitch, _step_header


def _card(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    card = QGroupBox(_(title))
    card.setProperty("class", "operationsCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(18, 18, 18, 18)
    card_layout.setSpacing(12)
    return card, card_layout


def add_status_and_history(window, layout: QVBoxLayout) -> None:
    status_group, status_layout = _card("Stato del lavoro")
    window.operations_web_status = QTextEdit()
    window.operations_web_status.setObjectName("operationsWebStatus")
    window.operations_web_status.setReadOnly(True)
    window.operations_web_status.setAcceptRichText(False)
    window.operations_web_status.setMaximumHeight(120)
    window.operations_web_status.setPlainText(
        _("Prepara una missione oppure selezionala dalla cronologia.")
    )
    window.operations_execution_log = window.operations_web_status
    status_layout.addWidget(window.operations_web_status)
    layout.addWidget(status_group)

    window.operations_history_toggle = ToggleSwitch(_("Mostra cronologia e risultati"))
    window.operations_history_toggle.setObjectName("operationsHistoryToggle")
    layout.addWidget(window.operations_history_toggle)

    history_group, history_layout = _card("Cronologia missioni")
    history_group.setObjectName("operationsHistoryPanel")
    history_group.setVisible(False)
    window.operations_history_toggle.toggled.connect(history_group.setVisible)

    history_columns = QHBoxLayout()
    window.operations_history_list = QListWidget()
    window.operations_history_list.setObjectName("operationsHistoryList")
    window.operations_history_list.setMinimumWidth(270)
    window.operations_history_list.setMaximumHeight(220)
    window.operations_history_list.currentItemChanged.connect(
        window.show_selected_operational_mission
    )
    history_columns.addWidget(window.operations_history_list, 2)

    window.operations_details_edit = QTextEdit()
    window.operations_details_edit.setObjectName("operationsMissionDetails")
    window.operations_details_edit.setReadOnly(True)
    window.operations_details_edit.setAcceptRichText(False)
    window.operations_details_edit.setPlainText(
        _("La cronologia delle missioni apparirà qui.")
    )
    window.operations_details_edit.setMinimumHeight(190)
    history_columns.addWidget(window.operations_details_edit, 3)
    history_layout.addLayout(history_columns)

    history_actions = QHBoxLayout()
    window.operations_import_result_button = QPushButton(_("Importa risultati…"))
    window.operations_import_result_button.setObjectName("importOperationalResultsButton")
    window.operations_import_result_button.setProperty("role", "success")
    window.operations_import_result_button.setEnabled(False)
    window.operations_import_result_button.clicked.connect(window.import_operational_result)
    history_actions.addWidget(window.operations_import_result_button)

    window.operations_open_output_button = QPushButton(_("Apri cartella risultati"))
    window.operations_open_output_button.setEnabled(False)
    window.operations_open_output_button.clicked.connect(
        window.open_operational_output_directory
    )
    history_actions.addWidget(window.operations_open_output_button)

    window.operations_tool_button = QPushButton(
        _("Crea uno strumento in Modalità Sviluppo")
    )
    window.operations_tool_button.setEnabled(False)
    window.operations_tool_button.clicked.connect(
        window.prepare_operational_tool_in_development
    )
    history_actions.addWidget(window.operations_tool_button)

    window.operations_archive_button = QPushButton(_("Archivia"))
    window.operations_archive_button.setEnabled(False)
    window.operations_archive_button.clicked.connect(
        window.archive_selected_operational_mission
    )
    history_actions.addWidget(window.operations_archive_button)
    history_actions.addStretch(1)
    history_layout.addLayout(history_actions)
    layout.addWidget(history_group)


def add_advanced_tools(window, layout: QVBoxLayout) -> None:
    window.operations_local_tools_group = ToggleSwitch(
        _("Mostra strumenti locali avanzati")
    )
    window.operations_local_tools_group.setObjectName("operationsLocalToolsToggle")
    layout.addWidget(window.operations_local_tools_group)

    advanced_group, advanced_layout = _card("Strumenti locali avanzati")
    advanced_group.setObjectName("operationsLocalToolsPanel")
    advanced_group.setVisible(False)
    advanced_layout.addWidget(
        _step_header(
            "A",
            _("Esecuzione controllata"),
            _(
                "Usa procedure locali predefinite per produrre risultati senza modificare "
                "gli originali. Non è il flusso principale della Modalità Operativa."
            ),
        )
    )

    local_row = QHBoxLayout()
    window.operations_procedure_combo = QComboBox()
    window.operations_procedure_combo.setObjectName("operationsProcedureCombo")
    window.operations_procedure_combo.addItem(
        _("Unisci e riepiloga CSV"), PROCEDURE_CSV_MERGE
    )
    window.operations_procedure_combo.addItem(
        _("Inventario tecnico degli input"), PROCEDURE_INPUT_INVENTORY
    )
    window.operations_procedure_combo.currentIndexChanged.connect(
        window._refresh_operational_draft_state
    )
    local_row.addWidget(window.operations_procedure_combo, 1)

    save_local = QPushButton(_("Salva come strumento locale"))
    save_local.clicked.connect(window.save_operational_local_mission)
    local_row.addWidget(save_local)

    window.operations_execute_button = QPushButton(_("Esegui missione selezionata"))
    window.operations_execute_button.setObjectName("executeOperationalMissionButton")
    window.operations_execute_button.setProperty("role", "success")
    window.operations_execute_button.setEnabled(False)
    window.operations_execute_button.clicked.connect(
        window.execute_selected_operational_mission
    )
    local_row.addWidget(window.operations_execute_button)
    advanced_layout.addLayout(local_row)

    window.operations_local_tools_group.toggled.connect(advanced_group.setVisible)
    window.operations_local_tools_group.toggled.connect(
        window._refresh_operational_draft_state
    )
    layout.addWidget(advanced_group)
