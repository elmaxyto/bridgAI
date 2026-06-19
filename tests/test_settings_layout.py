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
