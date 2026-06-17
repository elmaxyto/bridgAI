# Super-Report del Progetto

**Progetto:** `bridgAI`  
**Workspace:** `/home/max/Documenti/progetti/bridgAI`  
**Generato:** 2026-06-16 01:37:19  
**Modalità:** `standard`

---

## 1. Scopo del Report

Questo documento unifica:

- mappa reale del progetto;
- contesto architetturale;
- regole anti-monolite;
- file caldi;
- diagnostici live;
- note locali;
- prompt pronto per brainstorming con AI esterne.

È pensato per sostituire i vecchi flussi separati `#briefing`, `#mobile` e `Prompt_Vision`.

---

## 2. Regole Anti-Monolite

- File oltre **300-350 LOC**: evitare nuove logiche interne.
- Preferire nuove skill in `skills/`.
- Separare UI Telegram, logica core, accesso file, bridge e AI routing.
- Evitare duplicazioni tra handler e skill.
- Mantenere comandi legacy come alias, ma semplificare la tastiera.

---

## 3. File Caldi / Vicini alla Soglia

- 🔥 `AI_SUPER_REPORT.md` (1256 LOC)
- 🛠️ `README.md` (259 LOC)

---

## 4. Diagnostici Live

```text
Nessun diagnostico live rilevato.
```

---

## 5. Mappa Statica del Progetto

```text
# Mappa del Progetto JIT: `bridgAI`
**Percorso Assoluto:** `/home/max/Documenti/progetti/bridgAI`

## 📁 Struttura delle Cartelle
```text
├── src/
│   └── local_ai_bridge/
│       ├── core/
│       │   ├── __init__.py
│       │   ├── io.py
│       │   ├── models.py
│       │   ├── safety.py
│       │   ├── sessions.py
│       │   ├── settings.py
│       │   └── skills.py
│       ├── resources/
│       │   ├── app_icon.ico
│       │   ├── app_icon.png
│       │   ├── app_icon.svg
│       │   ├── i18n_en.json
│       │   └── i18n_it.json
│       ├── services/
│       │   ├── __init__.py
│       │   ├── apply.py
│       │   ├── archive.py
│       │   ├── exporting.py
│       │   ├── git.py
│       │   ├── github.py
│       │   ├── google_drive.py
│       │   ├── google_drive_auth.py
│       │   ├── patching.py
│       │   ├── project_scanner.py
│       │   ├── project_scanner_helpers.py
│       │   ├── reporting.py
│       │   ├── speech_to_text.py
│       │   ├── system.py
│       │   ├── temp_storage.py
│       │   └── testing.py
│       ├── skills/
│       │   ├── __init__.py
│       │   └── builtins.py
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── change_actions.py
│       │   ├── command_dialog.py
│       │   ├── github_actions.py
│       │   ├── layouts.py
│       │   ├── main_window.py
│       │   ├── settings_actions.py
│       │   ├── speech_dialog.py
│       │   ├── system_actions.py
│       │   ├── theme.py
│       │   ├── tool_actions.py
│       │   ├── workers.py
│       │   └── workflow_actions.py
│       ├── web/
│       │   ├── __init__.py
│       │   ├── __main__.py
│       │   ├── launcher.py
│       │   ├── page.py
│       │   └── server.py
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       └── i18n.py
├── tests/
│   ├── test_archive_and_sessions.py
│   ├── test_git_service.py
│   ├── test_google_drive.py
│   ├── test_launcher_diagnostics.py
│   ├── test_patching.py
│   ├── test_reporting_export.py
│   ├── test_safety.py
│   ├── test_settings.py
│   ├── test_system_service.py
│   ├── test_temp_storage.py
│   ├── test_testing.py
│   ├── test_web_launcher.py
│   ├── test_web_server.py
│   └── test_web_startup_regression.py
├── AGGIORNAMENTO_0.1.1.md
├── AGGIORNAMENTO_0.1.2.md
├── AGGIORNAMENTO_0.1.3.md
├── AGGIORNAMENTO_0.1.4.md
├── AGGIORNAMENTO_0.1.5.md
├── AGGIORNAMENTO_0.1.6.md
├── AGGIORNAMENTO_0.1.7.md
├── AGGIORNAMENTO_0.1.8.md
├── AGGIORNAMENTO_1.0.0.md
├── AI_SUPER_REPORT.md
├── Avvia_BridgAI.bat
├── Avvia_Local_AI_Bridge.bat
├── README.md
├── TEST_RESULTS.md
├── pyproject.toml
├── requirements.txt
├── run.py
├── start_bridgai_linux_mac.sh
├── start_bridgai_windows.bat
├── start_linux_mac.sh
└── start_windows.bat
```

## 📄 Sommario dei File (Firme e Docstrings)
### File: `pyproject.toml`
*(Nessuna definizione trovata o file vuoto)*

### File: `run.py`
```python

def _missing_dependencies() -> list[str]:
    ...

def _print_setup_help(missing: list[str]) -> None:
    ...

def _check_report(workspace: str, output: str | None) -> int:
    ...

def _parse_args() -> argparse.Namespace:
    ...
```

### File: `tests/test_archive_and_sessions.py`
```python

def make_manager(tmp_path: Path) -> SessionManager:
    ...

def test_simple_zip_inspect_apply_and_rollback(tmp_path: Path) -> None:
    ...

def test_manifest_hash_is_enforced(tmp_path: Path) -> None:
    ...

def test_transaction_rolls_back_after_second_write_failure(tmp_path: Path, monkeypatch) -> None:
    ...

def test_rollback_detects_later_changes(tmp_path: Path) -> None:
    ...

def test_manifest_delete_is_applied_and_rollback_restores_file(tmp_path: Path) -> None:
    ...

def test_manifest_delete_missing_file_is_idempotent(tmp_path: Path) -> None:
    ...

def test_manifest_delete_hash_is_enforced(tmp_path: Path) -> None:
    ...

def test_manifest_cannot_write_and_delete_same_target(tmp_path: Path) -> None:
    ...

def test_rollback_detects_recreated_deleted_file(tmp_path: Path) -> None:
    ...

def test_session_test_results_are_saved_and_reloaded(tmp_path: Path) -> None:
    ...

def test_old_session_json_is_backward_compatible(tmp_path: Path) -> None:
    ...
```

### File: `tests/test_git_service.py`
```python
def test_normalize_github_repository_accepts_slug_and_urls() -> None: ...
def test_normalize_github_repository_rejects_unsafe_values(value: str) -> None: ...
def test_connect_repository_adds_canonical_origin(tmp_path: Path, monkeypatch) -> None: ...
    def fake_run(command, *, cwd=None, timeout=60, check=True): ...
def test_create_repository_builds_noninteractive_gh_command(tmp_path: Path, monkeypatch) -> None: ...
    def fake_run(command, *, cwd=None, timeout=60, check=True): ...
def test_create_repository_refuses_push_without_commits(tmp_path: Path, monkeypatch) -> None: ...
def test_push_uses_current_branch_and_never_stages_files(tmp_path: Path, monkeypatch) -> None: ...
    def fake_run(command, *, cwd=None, timeout=60, check=True): ...
def test_application_icon_resource_exists() -> None: ...
def test_list_github_accounts_uses_json_without_exposing_tokens(monkeypatch) -> None: [REDACTED SECRET] ...
    def fake_run(command, *, cwd=None, timeout=60, check=True): ...
def test_switch_github_account_is_noninteractive(monkeypatch) -> None: ...
    def fake_run(command, *, cwd=None, timeout=60, check=True): ...
```

### File: `tests/test_google_drive.py`
```python
def test_token_path_is_isolated_in_app_data_dir(tmp_path: [REDACTED SECRET] ...
def test_offline_drive_failure_is_translated_without_unhandled_error(monkeypatch) -> None: ...
    class OfflineRequest: ...
        def execute(self): ...
    class OfflineFiles: ...
        def list(self, **_kwargs): ...
    class OfflineService: ...
        def files(self): ...
    def offline_service(interactive: bool): ...
```

### File: `tests/test_launcher_diagnostics.py`
```python

def test_report_diagnostic_cli(tmp_path: Path) -> None:
    ...

def test_report_diagnostic_can_write_output(tmp_path: Path) -> None:
    ...
```

### File: `tests/test_patching.py`
```python

def patch(search: str, replacement: str) -> str:
    ...

def test_patch_requires_blocks() -> None:
    ...

def test_patch_rejects_ambiguous_search() -> None:
    ...

def test_patch_preserves_crlf() -> None:
    ...

def test_inspect_patch_builds_diff(tmp_path: Path) -> None:
    ...

def test_full_python_file_is_validated(tmp_path: Path) -> None:
    ...
```

### File: `tests/test_reporting_export.py`
```python
def test_report_contains_protocol_and_skips_env(tmp_path: Path) -> None: ...
def test_empty_workspace_requires_complete_zip_and_apply_instruction(tmp_path: Path) -> None: ...
def test_workspace_with_unsupported_file_is_not_treated_as_empty(tmp_path: Path) -> None: ...
def test_tree_preserves_directories_and_paths(tmp_path: Path) -> None: ...
def test_report_detects_dependencies_and_runtime_limits(tmp_path: Path) -> None: ...
def test_readme_is_not_duplicated_as_priority_note(tmp_path: Path) -> None: ...
def test_generated_reports_are_excluded_everywhere(tmp_path: Path) -> None: ...
def test_two_consecutive_reports_do_not_grow_by_self_inclusion(tmp_path: Path) -> None: ...
def test_report_identifies_generator_version(tmp_path: Path) -> None: ...
def test_download_parse_and_export(tmp_path: Path) -> None: ...
def test_download_parse_restores_dunder_names_rewritten_by_markdown() -> None: ...
def test_download_export_accepts_markdown_rewritten_dunder_path(tmp_path: Path) -> None: ...
def test_scanner_does_not_follow_symlink_cycles(tmp_path: Path) -> None: ...
def test_scanner_skips_excluded_dirs_case_insensitively(tmp_path: Path) -> None: ...
```

### File: `tests/test_safety.py`
```python
def test_sensitive_paths_are_blocked() -> None: ...
def test_unsafe_targets_are_rejected(tmp_path: Path, raw: str) -> None: ...
def test_target_stays_inside_workspace(tmp_path: Path) -> None: ...
def test_zip_traversal_is_rejected(tmp_path: Path) -> None: ...
def test_zip_env_variant_is_rejected(tmp_path: Path) -> None: ...
def test_manifest_delete_traversal_is_rejected(tmp_path: Path) -> None: ...
def test_manifest_delete_sensitive_path_is_rejected(tmp_path: Path) -> None: ...
```

### File: `tests/test_settings.py`
```python

def test_temp_directory_round_trip(tmp_path: Path) -> None:
    ...

def test_merge_task_text() -> None:
    ...

def test_system_dictation_hints() -> None:
    ...

def test_gemini_drive_settings_round_trip(tmp_path: Path) -> None:
    ...

def test_gemini_drive_settings_are_backward_compatible(tmp_path: Path) -> None:
    ...

def test_update_zip_directory_round_trip(tmp_path: Path) -> None:
    ...

def test_update_zip_directory_is_backward_compatible(tmp_path: Path) -> None:
    ...

def test_language_round_trip(tmp_path: Path) -> None:
    ...

def test_language_is_backward_compatible(tmp_path: Path) -> None:
    ...

def test_i18n_catalog_falls_back_to_source_text() -> None:
    ...

def test_gemini_drive_warning_is_shown_only_when_disabled() -> None:
    ...

def test_simple_mode_round_trip(tmp_path: Path) -> None:
    ...

def test_simple_mode_is_backward_compatible(tmp_path: Path) -> None:
    ...

def test_external_ai_and_manual_web_defaults_are_backward_compatible(tmp_path: Path) -> None:
    ...

def test_dark_mode_round_trip(tmp_path: Path) -> None:
    ...

def test_dark_mode_is_backward_compatible(tmp_path: Path) -> None:
    ...
```

### File: `tests/test_system_service.py`
```python

def test_restart_source_run_uses_same_interpreter_and_script(tmp_path: Path) -> None:
    ...

def test_restart_frozen_relaunches_executable(tmp_path: Path) -> None:
    ...

def test_restart_console_script_falls_back_to_module(tmp_path: Path) -> None:
    ...
```

### File: `tests/test_temp_storage.py`
```python

def test_configured_root_uses_managed_subdirectory(tmp_path: Path) -> None:
    ...

def test_stage_import_zip_copies_to_managed_area(tmp_path: Path) -> None:
    ...

def test_clean_only_managed_directory(tmp_path: Path) -> None:
    ...

def test_latest_zip_file_returns_most_recent_zip(tmp_path: Path) -> None:
    ...

def test_latest_zip_file_handles_missing_or_empty_directory(tmp_path: Path) -> None:
    ...
```

### File: `tests/test_testing.py`
```python

def test_pytest_is_not_scheduled_when_module_is_missing(tmp_path: Path, monkeypatch) -> None:
    ...

def test_missing_pytest_is_reported_as_unavailable_not_failed(tmp_path: Path, monkeypatch) -> None:
    ...
```

### File: `tests/test_web_launcher.py`
```python

def test_web_settings_are_backward_compatible(tmp_path: Path, monkeypatch) -> None:
    ...

def test_web_url_validates_port() -> None:
    ...

def test_existing_server_is_reused(monkeypatch) -> None:
    ...

def test_server_uses_same_python_interpreter(monkeypatch) -> None:
    ...

def test_stop_terminates_owned_process() -> None:
    ...

def test_project_root_points_above_src() -> None:
    ...

def test_subprocess_environment_preserves_existing_pythonpath(monkeypatch, tmp_path: Path) -> None:
    ...
```

### File: `tests/test_web_server.py`
```python
def _request(url: str, method: str = "GET", payload: dict | None = None, csrf: str | None = None): ...
def test_local_server_status_and_csrf(tmp_path: Path, monkeypatch) -> None: ...
```

### File: `tests/test_web_startup_regression.py`
```python

def test_server_version_does_not_require_package_dunder_version() -> None:
    ...

def test_web_log_path_is_inside_app_data(tmp_path: Path, monkeypatch) -> None:
    ...
```

### File: `src/local_ai_bridge/__init__.py`
```python
"""
BridgAI.
"""
```

### File: `src/local_ai_bridge/__main__.py`
*(Nessuna definizione trovata o file vuoto)*

### File: `src/local_ai_bridge/app.py`
```python

def _set_windows_app_id() -> None:
    ...

def _icon_path() -> Path:
    ...

def main() -> int:
    ...
```

### File: `src/local_ai_bridge/i18n.py`
```python

def available_languages() -> tuple[tuple[str, str], ...]:
    ...

def normalize_language(value: str | None) -> str:
    ...

def configure_language(value: str | None) -> str:
    ...

def current_language() -> str:
    ...

def translate(text: str) -> str:
    ...

def tr(text: str) -> str:
    ...
```

### File: `src/local_ai_bridge/skills/__init__.py`
```python
"""
Package module.
"""
```

### File: `src/local_ai_bridge/skills/builtins.py`
```python

def _workspace(context: SkillContext) -> Path:
    ...

def register_builtin_skills(registry: SkillRegistry) -> None:
    ...
```

### File: `src/local_ai_bridge/services/__init__.py`
```python
"""
Package module.
"""
```

### File: `src/local_ai_bridge/services/apply.py`
```python

class ApplyService:
    def __init__(self, sessions: SessionManager | None=None) -> None:
        ...
    def apply(self, plan: ChangePlan) -> SessionRecord:
        ...
    def rollback_latest(self, workspace):
        ...
```

### File: `src/local_ai_bridge/services/archive.py`
```python

def _decode_for_diff(data: bytes) -> str | None:
    ...

def _unified_diff(relative: str, old_data: bytes, new_data: bytes) -> str:
    ...

def _delete_diff(relative: str, old_data: bytes) -> str:
    ...

def _load_manifest(zf: zipfile.ZipFile, member_info: dict[str, zipfile.ZipInfo]) -> tuple[dict[str, Any] | None, str | None]:
    ...

def _mappings(manifest: dict[str, Any] | None, manifest_name: str | None, members: list[str]) -> list[dict[str, Any]]:
    ...

def _deletions(manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    ...

def _check_expected_hash(relative: str, target_path: Path, expected: Any) -> str | None:
    ...

def inspect_zip(workspace: Path, zip_path: Path) -> ChangePlan:
    ...
```

### File: `src/local_ai_bridge/services/exporting.py`
```python

def _normalize_requested_path(raw: str) -> str:
    """
    Restore path characters that Markdown commonly rewrites while copying.

A filename such as ``__init__.py`` can be rendered as bold text and copied
back as ``**init**.py``.  Converting paired Markdown bold markers back to
double underscores is deterministic and preserves the intended filename;
no globbing or fuzzy filesystem lookup is performed.
    """
    ...

def parse_download_requests(text: str) -> list[str]:
    ...

def validate_requested_files(workspace: Path, requested: list[str]) -> list[tuple[str, Path]]:
    ...

def create_export_zip(workspace: Path, requested: list[str], destination: Path) -> Path:
    ...
```

### File: `src/local_ai_bridge/services/git.py`
```python

class GitIntegrationError(RuntimeError):
    """
    Errore leggibile prodotto da Git o GitHub CLI.
    """

def git_available() -> bool:
    ...

def _output(result: subprocess.CompletedProcess[str]) -> str:
    ...

def _run_command(command: list[str], *, cwd: Path | None=None, timeout: int=60, check: bool=True) -> str:
    ...

def is_git_repository(workspace: Path) -> bool:
    ...

def _git(workspace: Path, args: list[str], timeout: int=20) -> str:
    ...

def git_status(workspace: Path) -> str:
    ...

def git_diff(workspace: Path) -> str:
    ...

def git_remotes(workspace: Path) -> str:
    ...

def git_init(workspace: Path) -> str:
    ...

def git_remote_url(workspace: Path, remote_name: str='origin') -> str | None:
    ...

def git_has_commits(workspace: Path) -> bool:
    ...

def git_current_branch(workspace: Path) -> str:
    ...

def validate_remote_name(remote_name: str) -> str:
    ...

def push_current_branch(workspace: Path, remote_name: str='origin') -> str:
    ...
```

### File: `src/local_ai_bridge/services/github.py`
```python

class GitHubRepository:
    def display_name(self) -> str:
        ...

def github_cli_available() -> bool:
    ...

def github_auth_status() -> str:
    ...

def github_login_command() -> tuple[str, list[str]]:
    ...

def list_github_accounts() -> list[str]:
    ...

def github_switch_account(username: str) -> str:
    ...

def github_setup_git() -> str:
    ...

def _validate_repository_part(value: str, label: str) -> str:
    ...

def normalize_github_repository(value: str) -> tuple[str, str]:
    """
    Restituisce (owner/repo, URL HTTPS canonico) per un repository GitHub.
    """
    ...

def _validate_new_repository_name(value: str) -> str:
    ...

def list_github_repositories(limit: int=100) -> list[GitHubRepository]:
    ...

def create_github_repository(workspace: Path, name: str, *, visibility: str='private', description: str='', push: bool=False) -> str:
    ...

def connect_github_repository(workspace: Path, repository: str, *, remote_name: str='origin', replace_existing: bool=False) -> str:
    ...
```

### File: `src/local_ai_bridge/services/google_drive.py`
```python
def connect_account() -> str: ...
def connected_account() -> str: ...
def upload_export_zip(local_path: Path) -> str: ...
def list_import_zips() -> list[dict[str, Any]]: ...
def download_import_zip(file_id: str, local_destination: Path) -> Path: ...
def _ensure_folders(service: Any) -> dict[str, str]: ...
def _find_or_create_folder(service: Any, name: str, parent_id: str) -> str: ...
def _is_zip_metadata(metadata: dict[str, Any]) -> bool: ...
def _download_target(destination: Path, remote_name: str) -> Path: ...
def _query_literal(value: str) -> str: ...
```

### File: `src/local_ai_bridge/services/google_drive_auth.py`
```python
class GoogleDriveError(RuntimeError): ...
class GoogleDriveConfigurationError(GoogleDriveError): ...
class GoogleDriveAuthError(GoogleDriveError): ...
def google_drive_data_dir() -> Path: ...
def token_path() -> Path: [REDACTED SECRET] ...
def client_secrets_path() -> Path: [REDACTED SECRET] ...
def is_connected() -> bool: ...
def install_client_secrets(source: [REDACTED SECRET] ...
def disconnect_account() -> None: ...
def drive_service(interactive: bool) -> Iterator[Any]: ...
def google_imports() -> tuple[Any, Any, Any, Any, Any, Any]: ...
def _load_credentials(interactive: [REDACTED SECRET] ...
def _save_token(credentials: [REDACTED SECRET] ...
def _restrict_file_permissions(path: Path) -> None: ...
```

### File: `src/local_ai_bridge/services/patching.py`
```python

def _newline_style(text: str) -> str:
    ...

def _normalize(text: str) -> str:
    ...

def strip_outer_fence(text: str) -> str:
    ...

class PatchApplication:

def apply_search_replace(original: str, patch_text: str) -> PatchApplication:
    ...

def _diff(relative: str, old: str, new: str) -> str:
    ...

def inspect_patch(workspace: Path, target_relative: str, patch_text: str) -> ChangePlan:
    ...

def inspect_full_file(workspace: Path, target_relative: str, content: str) -> ChangePlan:
    ...
```

### File: `src/local_ai_bridge/services/project_scanner.py`
```python
class ScanBudgetExceeded(RuntimeError): ...
class ScanResult: ...
def _deadline(seconds: float) -> float: ...
def _check_deadline(deadline: float) -> None: ...
def is_generated_report(relative: str) -> bool: ...
def _relative_posix(root: Path, path: Path) -> str: ...
def _allowed_dir(root: Path, current: Path, name: str) -> bool: ...
def _allowed_file(root: Path, path: Path) -> bool: ...
def _is_reparse_or_link(entry: os.DirEntry[str]) -> bool: ...
def _safe_entries(root: Path, directory: Path, deadline: float) -> list[tuple[Path, bool]]: ...
def _walk_project_files(root: Path, deadline: float) -> Iterator[tuple[Path, str]]: ...
def iter_project_files(root: Path, time_budget: float = DEFAULT_SCAN_BUDGET_SECONDS): ...
def _tree(root: Path, deadline: float) -> tuple[str, bool]: ...
    def visit(directory: Path, prefix: str, depth: int) -> bool: ...
def rank_task_candidates(root: Path, task: str, limit: int = 12) -> list[str]: ...
def scan_project(root: Path, time_budget: float = DEFAULT_SCAN_BUDGET_SECONDS) -> ScanResult: ...
```

### File: `src/local_ai_bridge/services/project_scanner_helpers.py`
```python

def _annotation(node: ast.AST | None) -> str:
    ...

def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    ...

def summarize_python(content: str, relative: str) -> tuple[str, list[str]]:
    ...

def summarize_js(content: str) -> str:
    ...

def summarize_generic(path: Path, content: str) -> str:
    ...

def _read_pyproject(root: Path) -> dict:
    ...

def detect_project_version(root: Path) -> str | None:
    ...

def _dependency_names(root: Path) -> set[str]:
    ...

def detect_stack(root: Path) -> str:
    ...
```

### File: `src/local_ai_bridge/services/reporting.py`
```python

def _trace_report(message: str) -> None:
    """
    Append lightweight stage diagnostics for report generation.
    """
    ...

def _git_snapshot(root: Path) -> str:
    ...

def _notes(root: Path) -> str:
    ...

def _candidate_section(root: Path, task: str) -> str:
    ...

def _diagnostics_text(diagnostics: list[str]) -> str:
    ...

def build_super_report(root: Path, task: str='') -> str:
    ...
```

### File: `src/local_ai_bridge/services/speech_to_text.py`
```python

class SpeechToTextError(RuntimeError):
    """
    Raised when microphone capture or transcription cannot be completed.
    """

class MicrophoneRecorder:
    def is_recording(self) -> bool:
        ...
    def start(self) -> None:
        ...
    def stop(self) -> bytes:
        ...
    def cancel(self) -> None:
        ...

def transcribe_google(pcm_data: bytes, sample_rate: int=16000, language: str='it-IT') -> str:
    """
    Transcribe signed 16-bit mono PCM using SpeechRecognition's Google backend.
    """
    ...

def merge_task_text(existing: str, transcript: str) -> str:
    ...
```

### File: `src/local_ai_bridge/services/system.py`
```python

class RestartCommand:
    """
    Command used to start a fresh Local AI Bridge process.
    """

def build_restart_command(*, argv: Sequence[str] | None=None, executable: str | None=None, frozen: bool | None=None, cwd: str | Path | None=None) -> RestartCommand:
    """
    Build a cross-platform restart command for source and packaged runs.

Source runs reuse the current Python interpreter and the resolved ``run.py``
path. Packaged builds relaunch the executable directly. Console-script or
module-style runs fall back to ``python -m local_ai_bridge``.
    """
    ...
```

### File: `src/local_ai_bridge/services/temp_storage.py`
```python

class CleanupResult:

def configured_temp_root(configured: str | Path | None) -> Path:
    ...

def managed_subdir(configured: str | Path | None, name: str) -> Path:
    ...

def latest_zip_file(directory: str | Path | None) -> Path | None:
    ...

def stage_import_zip(source: Path, configured: str | Path | None) -> Path:
    ...

def clean_managed_temp(configured: str | Path | None) -> CleanupResult:
    ...
```

### File: `src/local_ai_bridge/services/testing.py`
```python

def _has_pytest_suite(workspace: Path) -> bool:
    ...

def _module_available(module_name: str) -> bool:
    ...

def _run(name: str, command: list[str], cwd: Path, timeout: int=120, env: dict[str, str] | None=None) -> TestResult:
    ...

def detect_test_commands(workspace: Path) -> list[tuple[str, list[str], int, dict[str, str] | None]]:
    ...

def run_detected_tests(workspace: Path) -> list[TestResult]:
    ...

def format_test_results(results: list[TestResult]) -> str:
    ...

def test_results_to_dicts(results: list[TestResult]) -> list[dict]:
    ...

def test_summary(results: list[TestResult]) -> str:
    ...
```

### File: `src/local_ai_bridge/web/__init__.py`
```python
"""
Localhost web interface for Local AI Bridge.
"""
```

### File: `src/local_ai_bridge/web/__main__.py`
*(Nessuna definizione trovata o file vuoto)*

### File: `src/local_ai_bridge/web/launcher.py`
```python

class WebLaunchResult:

def web_url(port: int) -> str:
    ...

def is_web_server_ready(port: int, timeout: float=0.35) -> bool:
    ...

def web_log_path() -> Path:
    ...

def project_root() -> Path:
    ...

def _subprocess_environment(root: Path) -> dict[str, str]:
    ...

def _creation_flags() -> int:
    ...

def start_web_interface(port: int=8765, *, open_browser: bool=True, wait_seconds: float=5.0, popen: Callable[..., subprocess.Popen[bytes]]=subprocess.Popen) -> WebLaunchResult:
    ...

def stop_web_interface(process: subprocess.Popen[bytes] | None, timeout: float=2.0) -> None:
    ...
```

### File: `src/local_ai_bridge/web/page.py`
```python
def render_index(csrf_token: [REDACTED SECRET] ...
```

### File: `src/local_ai_bridge/web/server.py`
```python
def _application_version() -> str: ...
class BridgeState: ...
    def __init__(self) -> None: ...
    def require_workspace(self) -> Path: ...
    def set_workspace(self, raw_path: str) -> Path: ...
class BridgeHandler(BaseHTTPRequestHandler): ...
    def log_message(self, format: str, *args: Any) -> None: ...
    def _is_local(self) -> bool: ...
    def _json(self, status: int, payload: dict[str, Any]) -> None: ...
    def _read_json(self) -> dict[str, Any]: ...
    def _require_write_access(self) -> None: ...
    def do_GET(self) -> None: ...
    def do_POST(self) -> None: ...
    def _dispatch(self, path: str, body: dict[str, Any]) -> dict[str, Any]: ...
class BridgeHTTPServer(ThreadingHTTPServer): ...
    def __init__(self, address: tuple[str, int], state: BridgeState) -> None: ...
def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None: ...
def _parse_args() -> argparse.Namespace: ...
def main() -> int: ...
```

### File: `src/local_ai_bridge/core/__init__.py`
```python
"""
Package module.
"""
```

### File: `src/local_ai_bridge/core/io.py`
```python

def sha256_bytes(data: bytes) -> str:
    ...

def sha256_file(path: Path) -> str:
    ...

def atomic_write(path: Path, data: bytes, *, original_mode: int | None=None) -> None:
    ...
```

### File: `src/local_ai_bridge/core/models.py`
```python

class FileChange:

class ChangePlan:

class TestResult:

class SkillResult:

class SessionRecord:
    def to_dict(self) -> dict[str, Any]:
        ...
```

### File: `src/local_ai_bridge/core/safety.py`
```python

class SafetyError(ValueError):

class ArchiveLimits:

def _normalized_parts(raw_path: str) -> tuple[str, ...]:
    ...

def is_sensitive_relative_path(raw_path: str) -> bool:
    ...

def resolve_workspace_target(workspace: Path, raw_path: str, *, allow_missing: bool=True) -> Path:
    ...

def validate_zip_info(info: zipfile.ZipInfo, limits: ArchiveLimits) -> str | None:
    ...

def validate_archive(zf: zipfile.ZipFile, limits: ArchiveLimits | None=None) -> list[str]:
    ...
```

### File: `src/local_ai_bridge/core/sessions.py`
```python

class SessionManager:
    def __init__(self) -> None:
        ...
    def create(self, workspace: Path, operation: str, source: str | None=None) -> tuple[Path, SessionRecord]:
        ...
    def save(self, directory: Path, record: SessionRecord) -> None:
        ...
    def load(self, directory: Path) -> SessionRecord:
        ...
    def iter_for_workspace(self, workspace: Path) -> Iterable[tuple[Path, SessionRecord]]:
        ...
    def save_test_results(self, record: SessionRecord, results: list[dict]) -> SessionRecord:
        ...
    def session_details(self, workspace: Path, session_id: str) -> tuple[Path, SessionRecord]:
        ...
    def latest_applied(self, workspace: Path) -> tuple[Path, SessionRecord] | None:
        ...
    def apply_transaction(self, workspace: Path, operation: str, changes: list[tuple[str, bytes | None]], *, source: str | None=None) -> SessionRecord:
        ...
    def rollback_latest(self, workspace: Path) -> SessionRecord:
        ...
    def _restore(self, directory: Path, record: SessionRecord, *, check_conflicts: bool) -> None:
        ...
```

### File: `src/local_ai_bridge/core/settings.py`
```python

def app_data_dir() -> Path:
    ...

class AppSettings:

class SettingsStore:
    def __init__(self) -> None:
        ...
    def load(self) -> AppSettings:
        ...
    def save(self, settings: AppSettings) -> None:
        ...
```

### File: `src/local_ai_bridge/core/skills.py`
```python

class SkillContext:

class SkillSpec:

class SkillRegistry:
    def __init__(self) -> None:
        ...
    def register(self, spec: SkillSpec) -> None:
        ...
    def execute(self, skill_id: str, context: SkillContext, **parameters: Any) -> SkillResult:
        ...
    def list_specs(self) -> list[SkillSpec]:
        ...
```

### File: `src/local_ai_bridge/resources/i18n_en.json`
```python
Invalid JSON syntax
```

### File: `src/local_ai_bridge/resources/i18n_it.json`
```python
JSON Object with keys: 
```

### File: `src/local_ai_bridge/ui/__init__.py`
```python
"""
Package module.
"""
```

### File: `src/local_ai_bridge/ui/change_actions.py`
```python

class ChangeActionsMixin:
    def choose_update_zip_directory(self) -> None:
        ...
    def apply_latest_zip(self) -> None:
        ...
    def choose_zip(self) -> None:
        ...
    def inspect_selected_zip(self) -> None:
        ...
    def display_plan(self, plan: ChangePlan) -> None:
        ...
    def apply_current_plan(self) -> None:
        ...
    def _after_apply(self, record) -> None:
        ...
    def _after_post_apply_tests(self, payload) -> None:
        ...
    def rollback_latest(self) -> None:
        ...
    def _after_rollback(self, record) -> None:
        ...
    def clear_plan(self) -> None:
        ...
```

### File: `src/local_ai_bridge/ui/command_dialog.py`
```python

class InteractiveCommandDialog(QDialog):
    """
    Piccolo terminale incorporato per i flussi interattivi di GitHub CLI.
    """
    def __init__(self, title: str, program: str, arguments: list[str], instructions: str, parent: QWidget | None=None) -> None:
        ...
    def _read_output(self) -> None:
        ...
    def _send_input(self) -> None:
        ...
    def _finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        ...
    def _process_error(self, error: QProcess.ProcessError) -> None:
        ...
    def reject(self) -> None:
        ...
```

### File: `src/local_ai_bridge/ui/github_actions.py`
```python

class GitHubActionsMixin:
    def show_github_status(self) -> None:
        ...
    def add_github_account(self) -> None:
        ...
    def switch_github_account(self) -> None:
        ...
    def _choose_github_account(self, accounts: list[str]) -> None:
        ...
    def _switch_and_setup_github_account(self, username: str) -> str:
        ...
    def create_github_repository(self) -> None:
        ...
    def _ask_repository_name(self, workspace: Path) -> str | None:
        ...
    def _ask_repository_visibility(self) -> str | None:
        ...
    def connect_existing_github_repository(self) -> None:
        ...
    def _choose_repository_to_connect(self, workspace: Path, repositories: list[GitHubRepository]) -> None:
        ...
    def _confirm_remote_link(self, workspace: Path, repository: str) -> bool | None:
        ...
    def push_to_github(self) -> None:
        ...
    def _ensure_github_cli(self) -> bool:
        ...
```

### File: `src/local_ai_bridge/ui/layouts.py`
```python

def build_central_ui(window) -> QSplitter:
    ...

def _button(label: str, callback, role: str='secondary') -> QPushButton:
    ...

def _step_header(number: str, title: str, description: str) -> QWidget:
    ...

def build_workflow_tab(window) -> QWidget:
    ...

def build_changes_tab(window) -> QWidget:
    ...

def build_tests_tab(window) -> QWidget:
    ...

def build_advanced_tab(window) -> QWidget:
    ...

def build_settings_tab(window) -> QWidget:
    ...
```

### File: `src/local_ai_bridge/ui/main_window.py`
```python

class MainWindow(WorkflowActionsMixin, ChangeActionsMixin, SystemActionsMixin, SettingsActionsMixin, GitHubActionsMixin, ToolActionsMixin, QMainWindow):
    def __init__(self) -> None:
        ...
    def apply_theme(self) -> None:
        ...
    def apply_simple_mode(self) -> None:
        ...
    def _auto_copy_report_in_simple_mode(self) -> None:
        ...
    def _build_toolbar(self) -> None:
        ...
    def show_credits(self) -> None:
        ...
    def _context(self) -> SkillContext:
        ...
    def _require_workspace(self) -> Path | None:
        ...
    def choose_workspace(self) -> None:
        ...
    def set_workspace(self, path: Path) -> None:
        ...
    def _load_last_workspace(self) -> None:
        ...
    def _tree_double_clicked(self, index: QModelIndex) -> None:
        ...
    def _run_background(self, function: Callable, on_result: Callable, status: str, on_finished: Callable | None=None) -> None:
        ...
    def _finish_worker(self, worker: FunctionWorker, callback: Callable | None) -> None:
        ...
    def _background_error(self, traceback_text: str) -> None:
        ...
    def _write_error_log(self, traceback_text: str) -> Path | None:
        ...
    def _show_status(self, text: str) -> None:
        ...
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        ...
    def dropEvent(self, event: QDropEvent) -> None:
        ...
    def closeEvent(self, event: QCloseEvent) -> None:
        ...
```

### File: `src/local_ai_bridge/ui/settings_actions.py`
```python

class SettingsActionsMixin:
    def set_dark_mode(self, enabled: bool) -> None:
        ...
    def save_interface_language(self) -> None:
        ...
    def refresh_web_settings(self) -> None:
        ...
    def save_web_settings(self) -> bool:
        ...
    def start_web_interface_from_settings(self) -> None:
        ...
    def refresh_temp_settings(self) -> None:
        ...
    def refresh_gemini_drive_settings(self) -> None:
        ...
    def set_gemini_drive_enabled(self, enabled: bool) -> None:
        ...
    def save_gemini_drive_path(self) -> None:
        ...
    def choose_gemini_drive_directory(self) -> None:
        ...
    def open_google_drive_download(self) -> None:
        ...
    def choose_temp_directory(self) -> None:
        ...
    def open_temp_directory(self) -> None:
        ...
    def clean_temp_directory(self) -> None:
        ...
```

### File: `src/local_ai_bridge/ui/speech_dialog.py`
```python

def system_dictation_hint(system_name: str | None=None) -> str:
    ...

class _SpeechSignals(QObject):

class SpeechDialog(QDialog):
    def __init__(self, parent=None, language: str='it-IT') -> None:
        ...
    def transcript(self) -> str:
        ...
    def _sync_insert_state(self) -> None:
        ...
    def start_recording(self) -> None:
        ...
    def stop_and_transcribe(self) -> None:
        ...
    def _transcribe_worker(self, audio: bytes) -> None:
        ...
    def _transcription_ready(self, text: str) -> None:
        ...
    def _transcription_failed(self, message: str) -> None:
        ...
    def reject(self) -> None:
        ...
    def closeEvent(self, event) -> None:
        ...
```

### File: `src/local_ai_bridge/ui/system_actions.py`
```python

class SystemActionsMixin:
    """
    Desktop actions that interact with the host operating system.
    """
    def open_workspace_folder(self) -> None:
        ...
    def restart_application(self) -> None:
        ...
```

### File: `src/local_ai_bridge/ui/theme.py`
```python

def application_style(dark: bool=False) -> str:
    ...
```

### File: `src/local_ai_bridge/ui/tool_actions.py`
```python

class ToolActionsMixin:
    def run_tests(self) -> None:
        ...
    def show_git_status(self) -> None:
        ...
    def show_git_diff(self) -> None:
        ...
    def show_git_remotes(self) -> None:
        ...
    def initialize_git_repository(self) -> None:
        ...
    def _show_tool_output(self, text: str) -> None:
        ...
    def _handle_skill_text_result(self, result, target: QPlainTextEdit) -> None:
        ...
    def _refresh_skills(self) -> None:
        ...
    def _refresh_sessions(self) -> None:
        ...
    def _session_test_state(self, record) -> str:
        ...
    def show_selected_session(self) -> None:
        ...
    def _save_simple_mode(self, checked: bool) -> None:
        ...
```

### File: `src/local_ai_bridge/ui/workers.py`
```python

class WorkerSignals(QObject):

class FunctionWorker(QRunnable):
    def __init__(self, function: Callable[[], Any]) -> None:
        ...
    def run(self) -> None:
        ...
```

### File: `src/local_ai_bridge/ui/workflow_actions.py`
```python

def gemini_drive_warning_required(enabled: bool) -> bool:
    ...

class WorkflowActionsMixin:
    def _gemini_drive_directory(self) -> Path | None:
        ...
    def open_speech_dialog(self) -> None:
        ...
    def generate_report(self) -> None:
        ...
    def _handle_report_result(self, result) -> None:
        ...
    def _report_finished(self) -> None:
        ...
    def copy_report(self) -> None:
        ...
    def save_report(self) -> None:
        ...
    def _open_web(self, url: str) -> None:
        ...
    def open_external_ai(self, url: str) -> None:
        ...
    def open_gemini(self) -> None:
        ...
    def open_download_folder(self) -> None:
        ...
    def analyze_response(self) -> None:
        ...
    def export_requested_files(self) -> None:
        ...
    def prepare_patch(self) -> None:
        ...
    def prepare_full_file(self) -> None:
        ...
    def _handle_export_result(self, result) -> None:
        ...
```


## 🕒 RUNTIME STATE
```json
{"error": "Impossibile leggere .context_snapshot.json: [Errno 2] No such file or directory: '/home/max/Documenti/progetti/bridgAI/.context_snapshot.json'"}
```

## 📄 RECENT LOGS
```text
[Impossibile leggere relay.log: [Errno 2] No such file or directory: '/home/max/Documenti/progetti/bridgAI/relay.log']
```

## 🕸️ HIGH-LEVEL DEPENDENCY GRAPH
```text
relay -> bridge
cmd_handlers -> vision
utils -> snapshot
cmd_handlers -> scanner
bridge -> relay
```
```

---

## 6. Note Locali Utili

_Nessuna nota locale rilevante trovata._

---

## 7. Prompt Pronto per AI Esterne

```text
Agisci come Software Architect Senior e assistente tecnico per questo progetto.

Modalità report: standard

Regole tassative:
1. Prima di proporre nuove funzionalità, valuta sempre i file coinvolti e il rischio monolite.
2. Se un file supera o rischia di superare 300-350 LOC, proponi una skill dedicata.
3. Non inventare file, funzioni o API non presenti nella mappa.
4. Per modifiche piccole usa patch SEARCH/REPLACE.
5. Per modifiche multi-file proponi ZIP con applymanifest.json.
6. Mantieni retrocompatibilità con i comandi esistenti, usando alias se necessario.
7. Distingui sempre tra analisi architetturale, piano operativo, patch/codice, rischi e test consigliati.
8. Preferisci soluzioni modulari, leggibili e facilmente testabili.
```

---

## 8. Protocollo di Modifica Consigliato

### Modifiche piccole

Usare blocchi SEARCH/REPLACE chirurgici.

### Sostituzione completa di un file

Fornire codice completo reale, senza Base64.

### Modifiche multi-file

Fornire uno ZIP applicabile tramite `#applica_zip`. Lo ZIP deve rispecchiare esattamente la struttura relativa del progetto a partire dalla root reale (es. `src/`, `styles/`, `index.html` direttamente alla radice dell'archivio, senza cartelle contenitore aggiuntive). L'uso di `applymanifest.json` alla radice dello ZIP è del tutto opzionale.

---

## 9. Protocollo operativo per AI esterne / ChatGPT

Questo report descrive il progetto attivo e deve essere usato come contesto iniziale per lavorare tramite il bot Telegram locale.

### Root progetto attivo

La root reale del progetto è quella indicata in alto nel campo `Workspace`.

Non assumere mai che la root sia il progetto del bot Telegram.
Il bot Telegram è solo il controller operativo; il progetto da modificare è quello indicato in questo report.

### Come richiedere file

Per modifiche precise, non basarti solo sulla mappa statica.
Chiedi sempre i file reali necessari usando un comando unico nel formato:

```text
#scarica percorso/file1, percorso/file2, percorso/file3
```

Richiedi solo i file davvero utili alla modifica.

### Come restituire modifiche

Scegli il formato più sicuro:

* Per un solo file completo: fornire il file intero da applicare con #modifica percorso/file
* Per più file completi: fornire uno ZIP da applicare con #applica_zip. Lo ZIP deve avere come radice interna direttamente le cartelle del progetto (es. `src/`, `styles/` alla radice dello ZIP), senza alcuna directory contenitore aggiuntiva.
  - **Formato ZIP semplice (consigliato)**: riproduce direttamente la struttura relativa del workspace, senza richiedere `applymanifest.json`.
  - **Formato ZIP avanzato (opzionale)**: include `applymanifest.json` per mappare in modo esplicito sorgenti e target, e opzionalmente verificare gli hash SHA-256 dei file originali.
* Per modifiche chirurgiche multi-file: fornire una patch .patch / .diff da applicare con #applica_patch, se disponibile
* Per modifiche ampie o architetturali: fornire un prompt agentico dettagliato per Codex/Cline/Antigravity

### Regola di sicurezza sulle scritture

Ogni operazione che scrive file deve mostrare chiaramente la base progetto prima di applicare modifiche:

📂 Base operazione:
/percorso/progetto/attivo

Fonte base:
bridge.current_project / workspace / env / altro

Se la base non è chiara, non applicare modifiche.

### Differenza tra progetto attivo e bot

Il progetto telegram.bot contiene gli strumenti e le skill del bot.
Il progetto indicato in questo report è invece il target operativo corrente.

Non usare percorsi di telegram.bot
salvo quando la richiesta riguarda esplicitamente il bot stesso.

---

## 10. Raccomandazioni Finali

## 9. Raccomandazione UI

Tastiera consigliata:

```text
🧠 #spiega        📊 #report
⚙️ AI_Direct_Hub
🧠 Bridge: OFF    ⬅️ Indietro
```

Comandi legacy consigliati come alias nascosti:

- `#briefing` → `#report completo`
- `#mobile` → `#report vision`
- `Prompt_Vision` → `#report vision`

---

## 11. Nota Finale

Questo report è uno snapshot operativo. Se il progetto cambia molto, rigenerarlo con `#report completo` prima di fare refactoring o brainstorming importante.
