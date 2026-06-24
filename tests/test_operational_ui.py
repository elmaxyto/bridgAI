from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_web_ai_is_the_primary_operational_workflow_and_local_tools_are_advanced() -> None:
    catalog_source = _source("src/local_ai_bridge/services/operational_catalog.py")
    web_source = _source("src/local_ai_bridge/services/operational_web.py")
    result_source = _source("src/local_ai_bridge/services/operational_results.py")
    actions_source = _source("src/local_ai_bridge/ui/operations_actions.py")
    web_actions_source = _source("src/local_ai_bridge/ui/operations_web_actions.py")
    presenter_source = _source("src/local_ai_bridge/ui/operations_presenters.py")
    tab_source = _source("src/local_ai_bridge/ui/tabs/operations.py")
    secondary_source = _source(
        "src/local_ai_bridge/ui/tabs/operations_secondary.py"
    )
    operational_ui_source = tab_source + secondary_source

    assert 'PROCEDURE_WEB_MISSION = "web.ai_mission.v1"' in catalog_source
    assert 'CATEGORY_PRESENTATIONS = "presentations"' in catalog_source
    assert 'PROVIDER_CHATGPT = "chatgpt"' in catalog_source
    assert "build_operational_mission_package" in web_source
    assert 'input/' in web_source
    assert 'output/' in web_source
    assert "inspect_operational_result_zip" in result_source
    assert "import_operational_result_zip" in result_source
    assert "OperationsWebActionsMixin" in actions_source
    assert "start_operational_web_mission" in web_actions_source
    assert "queue_operational_request" in web_actions_source
    assert "prepare_operational_tool_in_development" in web_actions_source
    assert "operations_category_combo" in tab_source
    assert "operations_provider_combo" in tab_source
    assert "Prepara e invia all’AI" in tab_source
    assert "Importa risultati" in operational_ui_source
    assert "Strumenti locali avanzati" in operational_ui_source
    assert "Unisci e riepiloga CSV" in operational_ui_source
    assert "Inventario tecnico degli input" in operational_ui_source
    assert "operationsFlow" in tab_source
    assert "operationsHistoryToggle" in secondary_source
    assert "operationsLocalToolsToggle" in secondary_source
    assert "ToggleSwitch" in secondary_source
    assert "setCheckable(True)" not in operational_ui_source
    assert "self.operations_start_button.setEnabled(ready)" in actions_source
    assert "operations_history_toggle.setChecked(True)" in web_actions_source
    assert "web_plan" in presenter_source


def test_web_operational_labels_are_bilingual() -> None:
    italian = json.loads(
        _source("src/local_ai_bridge/resources/i18n_it.json")
    )
    english = json.loads(
        _source("src/local_ai_bridge/resources/i18n_en.json")
    )
    expected = {
        "Nuovo lavoro con AI Web": "New Web AI task",
        "Documenti e PDF": "Documents and PDFs",
        "Fogli di calcolo e dati": "Spreadsheets and data",
        "Presentazioni": "Presentations",
        "Immagini e grafica": "Images and graphics",
        "Prepara e invia all’AI": "Prepare and send to AI",
        "Importa risultati…": "Import results…",
        "Strumenti locali avanzati": "Advanced local tools",
        "Definisci il risultato": "Define the result",
        "Autorizza gli input": "Authorize inputs",
        "Mostra cronologia e risultati": "Show history and results",
        "Mostra strumenti locali avanzati": "Show advanced local tools",
    }
    for source, translated in expected.items():
        assert italian.get(source, source) == source
        assert english[source] == translated


def test_extension_routes_operational_requests_as_results_not_code_updates() -> None:
    api_source = _source("src/local_ai_bridge/web/extension_api.py")
    adapter_source = _source("src/local_ai_bridge/web/extension_operational.py")
    background_source = _source(
        "src/local_ai_bridge/resources/chrome_extension/background.js"
    )
    downloads_source = _source(
        "src/local_ai_bridge/resources/chrome_extension/download_tracking.js"
    )

    assert 'request.get("request_kind") == "operational"' in api_source
    assert "mark_waiting_result" in api_source
    assert "register_operational_result" in api_source
    assert "inspect_operational_result_zip" in adapter_source
    assert '"action": "result_ready"' in api_source
    assert "request.initial_attachment" in background_source
    assert 'type: "BRIDGAI_ATTACH_CONTEXT"' in background_source
    assert '["update_ready", "result_ready"].includes(payload.action)' in downloads_source
