from pathlib import Path

from local_ai_bridge.core.settings import AppSettings


def test_advanced_settings_cards_are_grouped_in_requested_order() -> None:
    from local_ai_bridge.ui.tabs import settings as settings_tab

    source = Path(settings_tab.__file__).read_text(encoding="utf-8")
    function_source = source[source.index("def build_settings_tab"):]
    headings = (
        "QGroupBox(_('Interfaccia'))",
        "QGroupBox(_('Cartelle'))",
        "build_ai_assistant_settings_group(window)",
        "QGroupBox(_('Interfaccia Web UI'))",
        "QGroupBox(_('Formati di scambio con AI Web'))",
    )
    positions = [function_source.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "ToggleSwitch(_('Tema scuro'))" in function_source
    assert "_section('Lingua interfaccia')" in function_source
    assert "_section('Cartella aggiornamenti')" in function_source
    assert "_section('Cartella file temporanei')" in function_source
    assert "build_ai_assistant_settings_group(window)" in function_source
    assert "_section('Interfaccia web locale')" in function_source
    assert "_section('Cartella progetti Web UI')" in function_source
    assert "_section('Formato dei file richiesti')" in function_source
    assert "_section('Formato delle modifiche proposte')" in function_source
    assert "_section('Trasporto ZIP per Gemini')" in function_source


def test_simple_preferences_keep_language_and_hide_other_llm_models() -> None:
    from local_ai_bridge.ui import main_window
    from local_ai_bridge.ui.tabs import settings as settings_tab

    settings_source = Path(settings_tab.__file__).read_text(encoding="utf-8")
    settings_function = settings_source[settings_source.index("def build_settings_tab"):]
    assert "interface_layout.addWidget(language_section)" in settings_function
    assert "advanced_settings_groups.append(language_section)" not in settings_function

    main_source = Path(main_window.__file__).read_text(encoding="utf-8")
    simple_mode_source = main_source[
        main_source.index("    def apply_simple_mode"):main_source.index(
            "    def _auto_copy_report_in_simple_mode"
        )
    ]
    assert "self.other_llm_settings_group.setVisible(not simple)" in simple_mode_source


def test_exchange_formats_and_gemini_transport_are_independent() -> None:
    from local_ai_bridge.ui.settings_actions import SettingsActionsMixin

    class FakeCombo:
        def __init__(self, values: tuple[str, ...]) -> None:
            self.values = values
            self.index = 0

        def blockSignals(self, _blocked: bool) -> None:
            pass

        def findData(self, value: str) -> int:
            return self.values.index(value) if value in self.values else -1

        def setCurrentIndex(self, index: int) -> None:
            self.index = index

    class FakeCheck:
        def __init__(self) -> None:
            self.checked = False

        def blockSignals(self, _blocked: bool) -> None:
            pass

        def setChecked(self, checked: bool) -> None:
            self.checked = checked

    class FakeLineEdit:
        def text(self) -> str:
            return "/drive"

        def setText(self, _value: str) -> None:
            pass

    class FakeStore:
        def __init__(self) -> None:
            self.saved: list[tuple[bool, bool, bool]] = []

        def save(self, settings: AppSettings) -> None:
            self.saved.append((
                settings.gemini_drive_enabled,
                settings.markdown_exchange_mode,
                settings.textual_file_operations_mode,
            ))

    class FakeWindow(SettingsActionsMixin):
        def __init__(self) -> None:
            self.settings = AppSettings()
            self.settings_store = FakeStore()
            self.requested_files_format_combo = FakeCombo(("zip", "markdown"))
            self.update_format_combo = FakeCombo(("zip", "text"))
            self.gemini_drive_enabled_check = FakeCheck()
            self.gemini_drive_path_edit = FakeLineEdit()
            self.status = ""

        def apply_simple_mode(self) -> None:
            pass

        def _show_status(self, message: str) -> None:
            self.status = message

    window = FakeWindow()
    window.set_requested_files_format("markdown")
    window.set_update_format("text")
    window.set_gemini_drive_enabled(True)

    assert window.settings.markdown_exchange_mode is True
    assert window.settings.textual_file_operations_mode is True
    assert window.settings.gemini_drive_enabled is True
    assert window.settings.gemini_drive_path == "/drive"
    assert window.settings_store.saved[-1] == (True, True, True)
    assert "Google Drive" in window.status


def test_new_settings_labels_are_translated() -> None:
    from local_ai_bridge.i18n import configure_language, tr

    configure_language("en")
    assert tr("Tema scuro") == "Dark theme"
    assert tr("Cartelle") == "Folders"
    assert tr("Interfaccia Web UI") == "Web UI"
    assert tr("Formati di scambio con AI Web") == "Web AI exchange formats"
    assert tr("Formato dei file richiesti") == "Requested files format"
    assert tr("Formato delle modifiche proposte") == "Proposed changes format"
    configure_language("it")


def test_web_settings_expose_totp_enrollment_and_local_bypass() -> None:
    from local_ai_bridge.ui.tabs import settings as settings_tab

    source = Path(settings_tab.__file__).read_text(encoding="utf-8")
    function_source = source[source.index("def build_settings_tab"):]
    assert "_section('Autenticazione a due fattori')" in function_source
    assert "web_totp_configure_button" in function_source
    assert "web_totp_disable_button" in function_source
    assert "web_totp_local_bypass_check" in function_source
    assert "Non richiedere il codice 2FA" in function_source


def test_recent_projects_toolbar_uses_persistent_popup_menu() -> None:
    from local_ai_bridge.ui import main_window, recent_projects

    main_source = Path(main_window.__file__).read_text(encoding="utf-8")
    toolbar_source = main_source[
        main_source.index("    def _build_toolbar"):main_source.index("    def show_credits")
    ]
    workspace_source = main_source[
        main_source.index("    def set_workspace"):main_source.index("    def _load_last_workspace")
    ]
    recent_source = Path(recent_projects.__file__).read_text(encoding="utf-8")

    assert "RecentProjectsMixin" in main_source
    assert "self.add_recent_projects_widget(toolbar)" in toolbar_source
    assert "self._remember_recent_workspace(path)" in workspace_source
    assert "QToolButton.ToolButtonPopupMode.InstantPopup" in recent_source
    assert "aboutToShow.connect(self._refresh_recent_projects_menu)" in recent_source
    assert "Cancella elenco recenti" in recent_source


def test_recent_projects_labels_are_translated() -> None:
    from local_ai_bridge.i18n import configure_language, tr

    configure_language("en")
    assert tr("Recenti") == "Recent"
    assert tr("Nessun progetto recente") == "No recent projects"
    assert tr("Cancella elenco recenti") == "Clear recent projects"
    assert tr("{name} (non disponibile)").format(name="Example").endswith("(unavailable)")
    configure_language("it")


def test_advanced_tab_contains_optional_browser_extension_settings() -> None:
    from local_ai_bridge.ui.tabs import advanced

    source = Path(advanced.__file__).read_text(encoding="utf-8")
    assert "QGroupBox(_('Automazione browser'))" in source
    assert "browser_extension_enabled_check" in source
    assert "browser_extension_auto_send_check" in source
    assert "browser_extension_auto_receive_check" in source
    assert "browser_extension_auto_export_check" in source
    assert "browser_extension_auto_download_check" in source
    assert "La sottocartella degli ZIP si configura nelle opzioni" in source
    assert "Gli aggiornamenti non vengono mai applicati automaticamente" in source


def test_exchange_format_controls_are_only_in_advanced_settings() -> None:
    from local_ai_bridge.ui.tabs import settings as settings_tab
    from local_ai_bridge.ui.tabs import workflow

    workflow_source = Path(workflow.__file__).read_text(encoding="utf-8")
    settings_source = Path(settings_tab.__file__).read_text(encoding="utf-8")
    assert "requested_files_format_combo" not in workflow_source
    assert "update_format_combo" not in workflow_source
    assert "requested_files_format_combo" in settings_source
    assert "update_format_combo" in settings_source
    assert "_section('Formato dei file richiesti')" in settings_source
    assert "_section('Formato delle modifiche proposte')" in settings_source
    assert "window.set_requested_files_format" in settings_source
    assert "window.set_update_format" in settings_source


def test_text_file_operations_labels_are_translated() -> None:
    from local_ai_bridge.i18n import configure_language, tr

    configure_language("en")
    assert tr("File Markdown di aggiornamento") == "Markdown update file"
    assert tr("Markdown — per AI senza supporto ZIP") == "Markdown — for AI without ZIP support"
    configure_language("it")


def test_ai_assistant_settings_expose_optional_sources_and_free_form_models() -> None:
    from local_ai_bridge.ui.tabs import ai_assistant, settings as settings_tab

    settings_source = Path(settings_tab.__file__).read_text(encoding="utf-8")
    source = Path(ai_assistant.__file__).read_text(encoding="utf-8")

    assert "build_ai_assistant_settings_group(window)" in settings_source
    assert "window.refresh_ai_assistant_settings()" in settings_source
    assert "ai_assistant_enabled_check" in source
    assert "set_ai_assistant_enabled" in source
    assert "QStackedWidget" in source
    assert '"gemma_internal"' in source
    assert '"ollama"' in source
    assert '"cloud_provider"' in source
    assert "ai_assistant_ollama_model_edit = QLineEdit()" in source
    assert "ai_assistant_cloud_model_edit = QLineEdit()" in source
    assert "ai_assistant_cloud_key_edit.setEchoMode(QLineEdit.Password)" in source
    assert "qwen2.5-coder:7b" in source
    assert "llama-3.3-70b-speculative" in source
    assert "download_ai_assistant_gemma_model" in source


def test_ai_assistant_micro_tasks_are_present_and_bilingual() -> None:
    import json
    from local_ai_bridge import i18n as i18n_module
    from local_ai_bridge.i18n import configure_language, tr

    tasks = (
        "Scrittura automatica dei messaggi di commit basati sul diff reale.",
        "Code review e analisi dei rischi nella scheda Anteprima Modifiche prima dell’applicazione.",
        "Pre-validazione dei blocchi SEARCH/REPLACE e delle patch testuali per intercettare refusi o troncamenti prima che tocchino il codice reale (ottimale per risposte testuali da Gemini/Perplexity).",
        "Spiegazione in linguaggio naturale dei test falliti tramite l’analisi dei log di pytest.",
        "Suggerimento intelligente dei file rilevanti da includere nel Super-Report in base al task inserito.",
    )
    resources = Path(i18n_module.__file__).with_name("resources")
    italian = json.loads((resources / "i18n_it.json").read_text(encoding="utf-8"))
    english = json.loads((resources / "i18n_en.json").read_text(encoding="utf-8"))

    for task in tasks:
        assert task in italian
        assert task in english

    configure_language("en")
    assert tr("Abilita Assistente AI (Funzioni Extra)") == (
        "Enable AI Assistant (Extra Features)"
    )
    assert tr("Gemma 4 Integrata (100% Locale e Offline)") == (
        "Integrated Gemma 4 (100% Local and Offline)"
    )
    assert "actual diff" in tr(tasks[0])
    assert "pytest log analysis" in tr(tasks[3])
    configure_language("it")


def test_ai_assistant_actions_persist_configuration_and_model_import_flow() -> None:
    from local_ai_bridge.ui import ai_assistant_actions, main_window, settings_actions

    source = Path(ai_assistant_actions.__file__).read_text(encoding="utf-8")
    main_source = Path(main_window.__file__).read_text(encoding="utf-8")
    settings_source = Path(settings_actions.__file__).read_text(encoding="utf-8")

    assert "class AIAssistantActionsMixin" in source
    assert "def set_ai_assistant_enabled" in source
    assert "def save_ai_assistant_source" in source
    assert "def save_ai_assistant_settings" in source
    assert "AI_ASSISTANT_CLOUD_PROVIDERS" in source
    assert "AI_ASSISTANT_MODEL_SUFFIXES" in source
    assert 'managed_subdir(self.settings.temp_directory, "ai_models")' in source
    assert "shutil.copy2" in source
    assert "self._run_background(" in source
    assert "AIAssistantActionsMixin" in main_source
    assert "ai_assistant_gemma_downloaded = False" in settings_source


def test_simple_mode_switches_between_zip_and_text_update_inputs() -> None:
    from local_ai_bridge.ui import main_window

    source = Path(main_window.__file__).read_text(encoding="utf-8")
    method = source[
        source.index("    def apply_simple_mode"):source.index(
            "    def _auto_copy_report_in_simple_mode"
        )
    ]
    assert "markdown_files = simple and bool(self.settings.markdown_exchange_mode)" in method
    assert "text_updates = bool(self.settings.textual_file_operations_mode)" in method
    assert "self.text_result_group.setVisible(text_updates)" in method
    assert "self.simple_apply_zip_button.setVisible(simple and not text_updates)" in method
    assert "self.simple_prepare_files_button.setText" in method


def test_desktop_markdown_update_mode_exposes_file_and_manual_paths() -> None:
    from local_ai_bridge.ui import main_window, workflow_actions
    from local_ai_bridge.ui.tabs import workflow

    workflow_source = Path(workflow.__file__).read_text(encoding="utf-8")
    actions_source = Path(workflow_actions.__file__).read_text(encoding="utf-8")
    main_source = Path(main_window.__file__).read_text(encoding="utf-8")

    assert "text_update_path_edit" in workflow_source
    assert "Scegli file…" in workflow_source
    assert "Analizza file" in workflow_source
    assert "Oppure incolla manualmente la risposta" in workflow_source
    assert "Analizza testo incollato" in workflow_source
    assert "def choose_text_update_file" in actions_source
    assert "def analyze_selected_text_update_file" in actions_source
    assert "{'.md', '.txt'}" in actions_source
    assert "raw.decode('utf-8-sig')" in actions_source
    assert "inspect_text_file_operations(workspace, text)" in actions_source
    assert "suffixes.update({'.md', '.txt'})" in main_source
    assert "self._set_text_update_path(path)" in main_source


def test_primary_mode_settings_and_operations_screen_are_separate() -> None:
    from local_ai_bridge.ui import application_modes, main_window
    from local_ai_bridge.ui.tabs import operations, settings as settings_tab

    settings_source = Path(settings_tab.__file__).read_text(encoding="utf-8")
    operations_source = Path(operations.__file__).read_text(encoding="utf-8")
    selection_source = Path(application_modes.__file__).read_text(encoding="utf-8")
    main_source = Path(main_window.__file__).read_text(encoding="utf-8")

    assert "_section('Modalità principale')" in settings_source
    assert "primary_mode_combo" in settings_source
    assert "'development'" in settings_source
    assert "'operations'" in settings_source
    assert "def choose_initial_primary_mode" in selection_source
    assert "Che cosa vuoi fare con BridgAI?" in selection_source
    assert "Puoi cambiare modalità in qualsiasi momento" in selection_source
    assert "def build_operations_tab" in operations_source
    assert "richiesta, input, piano, autorizzazioni" in operations_source
    assert "self.operations_tab = build_operations_tab(self)" in main_source
    assert "self._ensure_primary_mode()" in main_source
    assert "self.settings.primary_mode == OPERATIONS_MODE" in main_source


def test_primary_mode_change_is_persisted_and_applied_immediately() -> None:
    from local_ai_bridge.core.settings import DEVELOPMENT_MODE, OPERATIONS_MODE
    from local_ai_bridge.ui.settings_actions import SettingsActionsMixin

    class FakeStore:
        def __init__(self) -> None:
            self.saved_modes: list[str] = []

        def save(self, settings: AppSettings) -> None:
            self.saved_modes.append(settings.primary_mode)

    class FakeWindow(SettingsActionsMixin):
        def __init__(self) -> None:
            self.settings = AppSettings(primary_mode=DEVELOPMENT_MODE)
            self.settings_store = FakeStore()
            self.applied = 0
            self.status = ""

        def apply_simple_mode(self) -> None:
            self.applied += 1

        def _show_status(self, message: str) -> None:
            self.status = message

    window = FakeWindow()
    window.set_primary_mode(OPERATIONS_MODE)

    assert window.settings.primary_mode == OPERATIONS_MODE
    assert window.settings_store.saved_modes == [OPERATIONS_MODE]
    assert window.applied == 1
    assert "Operativa" in window.status


def test_primary_mode_labels_are_bilingual() -> None:
    from local_ai_bridge.i18n import configure_language, tr

    configure_language("en")
    assert tr("Modalità principale") == "Primary mode"
    assert tr("Modalità Sviluppo") == "Development Mode"
    assert tr("Modalità Operativa") == "Operations Mode"
    assert tr("Che cosa vuoi fare con BridgAI?") == "What do you want to do with BridgAI?"
    configure_language("it")


def test_phase_two_mission_model_and_ui_are_separate_from_software_sessions() -> None:
    from local_ai_bridge.ui import main_window, operations_actions
    from local_ai_bridge.ui.tabs import operations, operations_secondary
    from local_ai_bridge.services import operational_missions

    main_source = Path(main_window.__file__).read_text(encoding="utf-8")
    actions_source = Path(operations_actions.__file__).read_text(encoding="utf-8")
    tab_source = Path(operations.__file__).read_text(encoding="utf-8")
    secondary_source = Path(operations_secondary.__file__).read_text(encoding="utf-8")
    operational_ui_source = tab_source + secondary_source
    service_source = Path(operational_missions.__file__).read_text(encoding="utf-8")

    assert "class OperationalMission" in service_source
    assert "class OperationalMissionStore" in service_source
    assert 'app_data_dir() / "missions"' in service_source
    assert 'self.session_manager = SessionManager()' in main_source
    assert 'self.mission_store = OperationalMissionStore()' in main_source
    assert "OperationsActionsMixin" in main_source
    assert "save_operational_mission" in actions_source
    assert "archive_selected_operational_mission" in actions_source
    assert "operations_input_list" in tab_source
    assert "operations_output_edit" in tab_source
    assert "operations_history_list" in operational_ui_source
    assert "Esecuzione controllata" in operational_ui_source


def test_phase_two_mission_labels_are_bilingual() -> None:
    from local_ai_bridge.i18n import configure_language, tr

    configure_language("en")
    assert tr("Nuova missione") == "New mission"
    assert tr("Input autorizzati") == "Authorized inputs"
    assert tr("Cartella di output:") == "Output folder:"
    assert tr("Cronologia missioni") == "Mission history"
    assert tr("Esecuzione non ancora attiva") == "Execution is not active yet"
    assert tr("Archivia missione") == "Archive mission"
    configure_language("it")


def test_phase_three_controlled_executor_is_exposed_without_generated_code() -> None:
    from local_ai_bridge.services import operational_execution, operational_execution_policy
    from local_ai_bridge.ui import main_window, operations_actions
    from local_ai_bridge.ui.tabs import operations, operations_secondary

    executor_source = Path(operational_execution.__file__).read_text(encoding="utf-8")
    policy_source = Path(operational_execution_policy.__file__).read_text(encoding="utf-8")
    main_source = Path(main_window.__file__).read_text(encoding="utf-8")
    actions_source = Path(operations_actions.__file__).read_text(encoding="utf-8")
    tab_source = Path(operations.__file__).read_text(encoding="utf-8")
    secondary_source = Path(operations_secondary.__file__).read_text(encoding="utf-8")
    operational_ui_source = tab_source + secondary_source

    assert "class OperationalMissionExecutor" in executor_source
    assert 'PROCEDURE_INPUT_INVENTORY = "builtin.input_inventory.v1"' in executor_source
    assert "input_contents_read" in policy_source
    assert "external_processes_used" in policy_source
    assert "validate_execution_boundaries" in policy_source
    assert "OperationalMissionExecutor(self.mission_store)" in main_source
    assert "execute_selected_operational_mission" in actions_source
    assert "operations_execution_log" in operational_ui_source
    assert "Esegui missione selezionata" in operational_ui_source
    assert "modificare gli originali" in operational_ui_source


def test_phase_three_execution_labels_are_bilingual() -> None:
    from local_ai_bridge.i18n import configure_language, tr

    configure_language("en")
    assert tr("Esecuzione controllata") == "Controlled execution"
    assert tr("Esegui missione selezionata") == "Run selected mission"
    assert tr("Apri cartella risultati") == "Open results folder"
    assert tr("Missione completata") == "Mission completed"
    assert tr("Missione non riuscita") == "Mission failed"
    configure_language("it")


def test_operational_mode_reuses_the_development_theme_palette() -> None:
    from local_ai_bridge.ui.tabs import operations
    from local_ai_bridge.ui.theme import application_style

    operations_source = Path(operations.__file__).read_text(encoding="utf-8")
    assert 'page.setObjectName("operationsPage")' in operations_source
    assert 'content.setObjectName("operationsScrollContent")' in operations_source

    for dark in (False, True):
        style = application_style(dark)
        assert "QWidget#workflowPage, QWidget#operationsPage" in style
        assert "QScrollArea#operationsScrollArea" in style
        assert "QWidget#operationsScrollContent" in style
        assert "QPlainTextEdit, QTextEdit, QLineEdit, QComboBox" in style
        assert "QTreeView, QTableWidget, QListWidget" in style
        assert "QListWidget::item:selected" in style
        assert 'QGroupBox[class="operationsCard"]' in style
        assert 'QWidget[class="operationsFlow"]' in style
        assert 'QLabel[class="flowPill"]' in style
        assert 'QLabel[class="stateBadge"][state="ready"]' in style
        assert "QTextEdit#operationsPlanPreview" in style


def test_exchange_formats_expose_collapsible_web_ai_compatibility_table() -> None:
    settings_source = (Path(__file__).parents[1] / "src/local_ai_bridge/ui/tabs/settings.py").read_text(encoding="utf-8")

    assert "QToolButton()" in settings_source
    assert "aiWebCompatibilityButton" in settings_source
    assert "aiWebCompatibilityPanel" in settings_source
    assert "compatibility_panel.setVisible(False)" in settings_source
    assert "'Compatibilità con le AI Web'" in settings_source
    assert "<b>Gemini Pro</b>" in settings_source
    assert "<b>Perplexity</b>" in settings_source
    assert "<b>Microsoft Copilot</b>" in settings_source
    assert "Markdown offre la massima compatibilità generale." in settings_source
