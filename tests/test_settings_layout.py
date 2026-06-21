from pathlib import Path

from local_ai_bridge.core.settings import AppSettings


def test_advanced_settings_cards_are_grouped_in_requested_order() -> None:
    from local_ai_bridge.ui.tabs import settings as settings_tab

    source = Path(settings_tab.__file__).read_text(encoding="utf-8")
    function_source = source[source.index("def build_settings_tab"):]
    headings = (
        "QGroupBox(_('Interfaccia'))",
        "QGroupBox(_('Cartelle'))",
        "QGroupBox(_('Interfaccia Web UI'))",
        "QGroupBox(_('Altri modelli LLM (Beta)'))",
    )
    positions = [function_source.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "ToggleSwitch(_('Tema scuro'))" in function_source
    assert "_section('Lingua interfaccia')" in function_source
    assert "_section('Cartella aggiornamenti')" in function_source
    assert "_section('Cartella file temporanei')" in function_source
    assert "_section('Interfaccia web locale')" in function_source
    assert "_section('Cartella progetti Web UI')" in function_source
    assert "_section('Utilizzo Gemini')" in function_source
    assert "_section('Utilizzo Markdown')" in function_source


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


def test_alternative_llm_modes_disable_each_other() -> None:
    from local_ai_bridge.ui.settings_actions import SettingsActionsMixin

    class FakeCheck:
        def __init__(self) -> None:
            self.checked = False

        def blockSignals(self, _blocked: bool) -> None:
            pass

        def setChecked(self, checked: bool) -> None:
            self.checked = checked

    class FakeLineEdit:
        def __init__(self, value: str = "") -> None:
            self.value = value

        def text(self) -> str:
            return self.value

        def setText(self, value: str) -> None:
            self.value = value

    class FakeStore:
        def __init__(self) -> None:
            self.saved = []

        def save(self, settings: AppSettings) -> None:
            self.saved.append((settings.gemini_drive_enabled, settings.markdown_exchange_mode))

    class FakeWindow(SettingsActionsMixin):
        def __init__(self, settings: AppSettings) -> None:
            self.settings = settings
            self.settings_store = FakeStore()
            self.gemini_drive_enabled_check = FakeCheck()
            self.markdown_exchange_mode_check = FakeCheck()
            self.gemini_drive_path_edit = FakeLineEdit("/drive")
            self.status = ""

        def apply_simple_mode(self) -> None:
            pass

        def _show_status(self, message: str) -> None:
            self.status = message

    gemini_window = FakeWindow(AppSettings(markdown_exchange_mode=True))
    gemini_window.set_gemini_drive_enabled(True)
    assert gemini_window.settings.gemini_drive_enabled is True
    assert gemini_window.settings.markdown_exchange_mode is False
    assert gemini_window.markdown_exchange_mode_check.checked is False
    assert "disattivata automaticamente" in gemini_window.status

    markdown_window = FakeWindow(AppSettings(gemini_drive_enabled=True))
    markdown_window.set_markdown_exchange_mode(True)
    assert markdown_window.settings.markdown_exchange_mode is True
    assert markdown_window.settings.gemini_drive_enabled is False
    assert markdown_window.gemini_drive_enabled_check.checked is False
    assert "disattivata automaticamente" in markdown_window.status


def test_new_settings_labels_are_translated() -> None:
    from local_ai_bridge.i18n import configure_language, tr

    configure_language("en")
    assert tr("Tema scuro") == "Dark theme"
    assert tr("Cartelle") == "Folders"
    assert tr("Interfaccia Web UI") == "Web UI"
    assert tr("Altri modelli LLM (Beta)") == "Other LLM models (Beta)"
    assert "mutually exclusive" in tr(
        "Gemini e Markdown Exchange sono modalità alternative: attivandone una, "
        "l’altra viene disattivata automaticamente."
    )
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
