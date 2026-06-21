from pathlib import Path

from local_ai_bridge.core.settings import (
    MAX_RECENT_WORKSPACES,
    AppSettings,
    SettingsStore,
    normalize_recent_workspaces,
    remember_recent_workspace,
)


def test_recent_workspaces_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    expected = [str(tmp_path / "project-b"), str(tmp_path / "project-a")]
    store.save(AppSettings(recent_workspaces=expected))
    assert store.load().recent_workspaces == expected


def test_recent_workspaces_are_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"last_workspace": "C:/workspace"}', encoding="utf-8")
    assert store.load().recent_workspaces == []


def test_recent_workspaces_are_normalized_and_limited() -> None:
    values: list[object] = [" /projects/current ", "", None, "/projects/current"]
    values.extend(f"/projects/project-{index}" for index in range(MAX_RECENT_WORKSPACES + 3))
    normalized = normalize_recent_workspaces(values)
    assert normalized[0] == "/projects/current"
    assert len(normalized) == MAX_RECENT_WORKSPACES
    assert normalized.count("/projects/current") == 1


def test_remember_recent_workspace_moves_project_to_front() -> None:
    recent = ["/projects/one", "/projects/two", "/projects/three"]
    assert remember_recent_workspace(recent, "/projects/two") == [
        "/projects/two",
        "/projects/one",
        "/projects/three",
    ]


def test_recent_workspaces_ignore_invalid_persisted_values(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text(
        '{"recent_workspaces": ["/projects/one", 42, "", "/projects/one"]}',
        encoding="utf-8",
    )
    assert store.load().recent_workspaces == ["/projects/one"]


def test_temp_directory_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    settings = AppSettings(temp_directory=str(tmp_path / "base"))
    store.save(settings)
    assert store.load().temp_directory == str(tmp_path / "base")


def test_merge_task_text() -> None:
    from local_ai_bridge.services.speech_to_text import merge_task_text

    assert merge_task_text("", " nuovo task ") == "nuovo task"
    assert merge_task_text("task esistente\n", "aggiunta") == "task esistente\naggiunta"
    assert merge_task_text("task esistente", "  ") == "task esistente"


def test_system_dictation_hints() -> None:
    from local_ai_bridge.ui.speech_dialog import system_dictation_hint

    assert "Win + H" in system_dictation_hint("Windows")
    assert "Tastiera > Dettatura" in system_dictation_hint("Darwin")
    assert "Linux" in system_dictation_hint("Linux")


def test_gemini_drive_settings_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    settings = AppSettings(
        gemini_drive_enabled=True,
        gemini_drive_path=str(tmp_path / "Google Drive"),
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.gemini_drive_enabled is True
    assert loaded.gemini_drive_path == str(tmp_path / "Google Drive")


def test_gemini_drive_settings_are_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"last_workspace": "C:/workspace"}', encoding="utf-8")
    loaded = store.load()
    assert loaded.gemini_drive_enabled is False
    assert loaded.gemini_drive_path == ""


def test_update_zip_directory_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    expected = str(tmp_path / "Downloads")
    store.save(AppSettings(update_zip_directory=expected))
    assert store.load().update_zip_directory == expected


def test_update_zip_directory_is_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"last_workspace": "C:/workspace"}', encoding="utf-8")
    assert store.load().update_zip_directory == ""


def test_language_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.save(AppSettings(language="en"))
    assert store.load().language == "en"


def test_language_is_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"last_workspace": "C:/workspace"}', encoding="utf-8")
    assert store.load().language == "it"


def test_i18n_catalog_falls_back_to_source_text() -> None:
    from local_ai_bridge.i18n import configure_language, tr
    configure_language("en")
    assert tr("Impostazioni") == "Settings"
    assert tr("Scegli root progetti") == "Choose project root"
    assert tr("not-in-catalog") == "not-in-catalog"
    configure_language("it")


def test_gemini_beta_warning_is_translated() -> None:
    from local_ai_bridge.i18n import configure_language, tr

    source = (
        "Modalità Gemini — Beta: questa integrazione è ancora in fase di perfezionamento e "
        "potrebbe non funzionare correttamente. Gemini può avere difficoltà a restituire patch "
        "complete e codice applicabile; controlla sempre con attenzione l’anteprima prima di "
        "applicare le modifiche."
    )
    configure_language("en")
    translated = tr(source)
    assert translated.startswith("Gemini mode — Beta:")
    assert "may not work correctly" in translated
    configure_language("it")


def test_gemini_drive_warning_is_shown_only_when_disabled() -> None:
    from local_ai_bridge.ui.workflow_actions import gemini_drive_warning_required

    assert gemini_drive_warning_required(False) is True
    assert gemini_drive_warning_required(True) is False


def test_simple_mode_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.save(AppSettings(simple_mode=False))
    assert store.load().simple_mode is False


def test_simple_mode_is_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"last_workspace": "C:/workspace"}', encoding="utf-8")
    assert store.load().simple_mode is True


def test_web_auto_start_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.save(AppSettings(web_auto_start=True))
    assert store.load().web_auto_start is True


def test_external_ai_and_manual_web_defaults_are_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"language": "it"}', encoding="utf-8")
    loaded = store.load()
    assert loaded.grok_url == "https://grok.com/"
    assert loaded.web_auto_start is False


def test_dark_mode_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.save(AppSettings(dark_mode=True))
    assert store.load().dark_mode is True


def test_dark_mode_is_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"last_workspace": "C:/workspace"}', encoding="utf-8")
    assert store.load().dark_mode is False


def test_fresh_install_starts_in_simple_mode(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "missing-settings.json"
    assert store.load().simple_mode is True



def test_reset_project_ui_clears_project_specific_state() -> None:
    from local_ai_bridge.ui.main_window import _reset_project_ui

    class FakeEditor:
        def __init__(self) -> None:
            self.cleared = False

        def clear(self) -> None:
            self.cleared = True

    class FakeTable:
        def __init__(self) -> None:
            self.rows = 3

        def setRowCount(self, rows: int) -> None:
            self.rows = rows

    class FakeButton:
        def __init__(self) -> None:
            self.enabled = True

        def setEnabled(self, enabled: bool) -> None:
            self.enabled = enabled

    class FakeWindow:
        def __init__(self) -> None:
            for name in (
                'task_edit', 'report_edit', 'response_edit', 'gemini_result_edit', 'target_edit',
                'zip_path_edit', 'diff_edit', 'session_details_edit',
            ):
                setattr(self, name, FakeEditor())
            self.plan_table = FakeTable()
            self.apply_button = FakeButton()
            self.current_plan = object()
            self._last_auto_copied_report = 'old report'

    window = FakeWindow()
    _reset_project_ui(window)

    for name in (
        'task_edit', 'report_edit', 'response_edit', 'gemini_result_edit', 'target_edit',
        'zip_path_edit', 'diff_edit', 'session_details_edit',
    ):
        assert getattr(window, name).cleared is True
    assert window.plan_table.rows == 0
    assert window.apply_button.enabled is False
    assert window.current_plan is None
    assert window._last_auto_copied_report is None


def test_project_display_name_uses_only_directory_name() -> None:
    from local_ai_bridge.ui.main_window import _project_display_name

    assert _project_display_name(Path("C:/software/LocalBridge")) == "LocalBridge"
    assert _project_display_name(Path("/home/user/example")) == "example"


def test_validated_project_name_rejects_empty_and_path_components() -> None:
    import pytest
    from local_ai_bridge.ui.main_window import _validated_project_name

    assert _validated_project_name("  My Project  ") == "My Project"
    for invalid in ("", "   ", ".", "..", "folder/name", "folder\\name"):
        with pytest.raises(ValueError):
            _validated_project_name(invalid)


def test_web_workspace_root_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    expected = str(tmp_path / "projects")
    store.save(AppSettings(web_workspace_root=expected))
    assert store.load().web_workspace_root == expected


def test_web_workspace_root_is_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"language": "it"}', encoding="utf-8")
    assert store.load().web_workspace_root == ""


def test_web_credentials_round_trip_without_plaintext_password(tmp_path: Path) -> None:
    from local_ai_bridge.web.security import hash_password

    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    password_hash = hash_password("a sufficiently long password")
    store.save(AppSettings(
        web_remote_access=True,
        web_username="admin",
        web_password_hash=password_hash,
    ))
    loaded = store.load()
    assert loaded.web_remote_access is True
    assert loaded.web_username == "admin"
    assert loaded.web_password_hash == password_hash
    assert "a sufficiently long password" not in store.path.read_text(encoding="utf-8")


def test_settings_tab_uses_scrollable_content() -> None:
    from local_ai_bridge.ui.tabs import settings as settings_tab

    source = Path(settings_tab.__file__).read_text(encoding="utf-8")
    function_source = source[source.index("def build_settings_tab"):]
    assert "QScrollArea()" in function_source
    assert "setWidgetResizable(True)" in function_source
    assert "setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)" in function_source
    assert "scroll_area.setWidget(content)" in function_source


def test_settings_theme_styles_scroll_content_and_group_titles() -> None:
    from local_ai_bridge.ui.theme import application_style

    for dark in (False, True):
        style = application_style(dark)
        assert "QScrollArea#settingsScrollArea" in style
        assert "QWidget#settingsScrollContent" in style
        assert "QGroupBox::title" in style


def test_custom_prompt_settings_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.save(AppSettings(include_custom_prompts=False, global_prompt="Use typed Python."))
    loaded = store.load()
    assert loaded.include_custom_prompts is False
    assert loaded.global_prompt == "Use typed Python."


def test_custom_prompt_settings_are_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"language": "it"}', encoding="utf-8")
    loaded = store.load()
    assert loaded.include_custom_prompts is True
    assert loaded.global_prompt == ""


def test_project_prompt_round_trip_preserves_other_metadata(tmp_path: Path) -> None:
    from local_ai_bridge.core.project_prompts import load_project_prompt, save_project_prompt

    metadata = tmp_path / ".bridgai" / "project.json"
    metadata.parent.mkdir()
    metadata.write_text('{"other": true}', encoding="utf-8")
    save_project_prompt(tmp_path, "  Prefer service modules.  ")
    assert load_project_prompt(tmp_path) == "Prefer service modules."
    assert '"other": true' in metadata.read_text(encoding="utf-8")


def test_project_ignore_round_trip(tmp_path: Path) -> None:
    from local_ai_bridge.core.project_prompts import load_project_ignore, save_project_ignore

    saved = save_project_ignore(tmp_path, "dist/\r\n*.sqlite")
    assert saved == tmp_path / ".bridgai" / "ignore"
    assert load_project_ignore(tmp_path) == "dist/\n*.sqlite\n"


def test_markdown_exchange_mode_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.save(AppSettings(markdown_exchange_mode=True))
    assert store.load().markdown_exchange_mode is True


def test_markdown_exchange_mode_is_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"last_workspace": "C:/workspace"}', encoding="utf-8")
    assert store.load().markdown_exchange_mode is False



def test_web_two_factor_settings_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    settings = AppSettings(
        web_totp_enabled=True,
        web_totp_secret="JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
        web_totp_local_bypass=True,
        web_totp_last_counter=123,
        web_totp_recovery_hashes=["a" * 64, "b" * 64],
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.web_totp_enabled is True
    assert loaded.web_totp_secret == settings.web_totp_secret
    assert loaded.web_totp_local_bypass is True
    assert loaded.web_totp_last_counter == 123
    assert loaded.web_totp_recovery_hashes == ["a" * 64, "b" * 64]


def test_web_two_factor_settings_are_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"web_username": "admin"}', encoding="utf-8")
    loaded = store.load()
    assert loaded.web_totp_enabled is False
    assert loaded.web_totp_secret == ""
    assert loaded.web_totp_local_bypass is False
    assert loaded.web_totp_last_counter == -1
    assert loaded.web_totp_recovery_hashes == []


def test_browser_extension_settings_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    settings = AppSettings(
        browser_extension_enabled=True,
        browser_extension_remote_access=True,
        browser_extension_auto_send=False,
        browser_extension_auto_receive=False,
        browser_extension_auto_export=False,
        browser_extension_auto_download=False,
        browser_extension_token="token-value-with-at-least-thirty-two-characters",
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.browser_extension_enabled is True
    assert loaded.browser_extension_remote_access is True
    assert loaded.browser_extension_auto_send is False
    assert loaded.browser_extension_auto_receive is False
    assert loaded.browser_extension_auto_export is False
    assert loaded.browser_extension_auto_download is False
    assert loaded.browser_extension_token == settings.browser_extension_token


def test_browser_extension_settings_are_backward_compatible(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.path.write_text('{"language": "it"}', encoding="utf-8")
    loaded = store.load()
    assert loaded.browser_extension_enabled is False
    assert loaded.browser_extension_remote_access is False
    assert loaded.browser_extension_auto_send is True
    assert loaded.browser_extension_auto_receive is True
    assert loaded.browser_extension_auto_export is True
    assert loaded.browser_extension_auto_download is True
    assert loaded.browser_extension_token == ""
