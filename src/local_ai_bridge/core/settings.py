from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "LocalAIBridge"
APP_AUTHOR = "LocalAIBridge"
DEFAULT_SIMPLE_MODE = True
DEVELOPMENT_MODE = "development"
OPERATIONS_MODE = "operations"
PRIMARY_MODES = (DEVELOPMENT_MODE, OPERATIONS_MODE)
LEGACY_PRIMARY_MODE = DEVELOPMENT_MODE
MAX_RECENT_WORKSPACES = 10
AI_ASSISTANT_SOURCES = ("gemma_internal", "ollama", "cloud_provider")
AI_ASSISTANT_CLOUD_PROVIDERS = (
    "groq",
    "cerebras",
    "gemini",
    "mistral",
    "openrouter",
)
PREFERRED_WEB_AI_CHATGPT = "chatgpt"
PREFERRED_WEB_AI_CLAUDE = "claude"
PREFERRED_WEB_AI_GEMINI = "gemini"
PREFERRED_WEB_AI_CUSTOM = "custom"
PREFERRED_WEB_AI_VALUES = (
    PREFERRED_WEB_AI_CHATGPT,
    PREFERRED_WEB_AI_CLAUDE,
    PREFERRED_WEB_AI_GEMINI,
    PREFERRED_WEB_AI_CUSTOM,
)


def app_data_dir() -> Path:
    path = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(slots=True)
class AppSettings:
    language: str = "it"
    primary_mode: str = ""
    last_workspace: str = ""
    recent_workspaces: list[str] = field(default_factory=list)
    simple_mode: bool = DEFAULT_SIMPLE_MODE
    preferred_web_ai: str = PREFERRED_WEB_AI_CUSTOM
    dark_mode: bool = False
    include_custom_prompts: bool = True
    global_prompt: str = ""
    chatgpt_url: str = "https://chatgpt.com/"
    claude_url: str = "https://claude.ai/"
    grok_url: str = "https://grok.com/"
    temp_directory: str = ""
    update_zip_directory: str = ""
    ai_assistant_enabled: bool = False
    ai_assistant_source: str = "gemma_internal"
    ai_assistant_gemma_downloaded: bool = False
    ai_assistant_ollama_url: str = "http://localhost:11434"
    ai_assistant_ollama_model: str = ""
    ai_assistant_cloud_provider: str = "groq"
    ai_assistant_cloud_key: str = ""
    ai_assistant_cloud_model: str = ""
    gemini_drive_enabled: bool = False
    gemini_drive_path: str = ""
    markdown_exchange_mode: bool = False
    textual_file_operations_mode: bool = False
    browser_extension_enabled: bool = False
    browser_extension_remote_access: bool = False
    browser_extension_auto_send: bool = True
    browser_extension_auto_receive: bool = True
    browser_extension_auto_export: bool = True
    browser_extension_auto_download: bool = True
    browser_extension_token: str = ""
    web_auto_start: bool = False
    web_open_browser: bool = True
    web_port: int = 8765
    web_stop_on_exit: bool = True
    web_workspace_root: str = ""
    web_remote_access: bool = False
    web_username: str = ""
    web_password_hash: str = ""
    web_totp_enabled: bool = False
    web_totp_secret: str = ""
    web_totp_local_bypass: bool = False
    web_totp_last_counter: int = -1
    web_totp_recovery_hashes: list[str] = field(default_factory=list)


def normalize_recent_workspaces(
    value: object,
    limit: int = MAX_RECENT_WORKSPACES,
) -> list[str]:
    """Return a clean, ordered, duplicate-free recent workspace list."""
    if not isinstance(value, list) or limit <= 0:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        path = item.strip()
        if not path:
            continue
        key = os.path.normcase(os.path.normpath(path))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(path)
        if len(normalized) >= limit:
            break
    return normalized


def normalize_primary_mode(
    value: object,
    default: str = LEGACY_PRIMARY_MODE,
) -> str:
    """Return a supported primary mode without inferring workspace type."""
    if isinstance(value, str) and value in PRIMARY_MODES:
        return value
    return default


def normalize_preferred_web_ai(
    value: object,
    default: str = PREFERRED_WEB_AI_CUSTOM,
) -> str:
    """Return a supported preferred Web AI identifier."""
    if isinstance(value, str) and value in PREFERRED_WEB_AI_VALUES:
        return value
    return default


def preferred_web_ai_exchange_formats(value: object) -> tuple[bool, bool] | None:
    """Return ``(requested_markdown, update_markdown)`` for a provider preset."""
    preferred = normalize_preferred_web_ai(value, PREFERRED_WEB_AI_CUSTOM)
    if preferred in {PREFERRED_WEB_AI_CHATGPT, PREFERRED_WEB_AI_CLAUDE}:
        return False, False
    if preferred == PREFERRED_WEB_AI_GEMINI:
        return False, True
    return None


def remember_recent_workspace(
    recent_workspaces: object,
    workspace: str | Path,
    limit: int = MAX_RECENT_WORKSPACES,
) -> list[str]:
    """Move *workspace* to the front of the recent workspace list."""
    current = str(workspace).strip()
    if not current:
        return normalize_recent_workspaces(recent_workspaces, limit)
    existing = recent_workspaces if isinstance(recent_workspaces, list) else []
    return normalize_recent_workspaces([current, *existing], limit)


class SettingsStore:
    def __init__(self) -> None:
        self.path = app_data_dir() / "settings.json"

    def load(self) -> AppSettings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            values = {k: v for k, v in data.items() if k in AppSettings.__annotations__}
            values["primary_mode"] = normalize_primary_mode(
                data.get("primary_mode"),
                LEGACY_PRIMARY_MODE,
            )
            values["recent_workspaces"] = normalize_recent_workspaces(
                values.get("recent_workspaces", [])
            )
            preferred_web_ai = normalize_preferred_web_ai(
                data.get("preferred_web_ai"),
                PREFERRED_WEB_AI_CUSTOM,
            )
            values["preferred_web_ai"] = preferred_web_ai
            if not isinstance(values.get("web_totp_recovery_hashes", []), list):
                values["web_totp_recovery_hashes"] = []
            if not isinstance(values.get("markdown_exchange_mode", False), bool):
                values["markdown_exchange_mode"] = False
            if not isinstance(values.get("textual_file_operations_mode", False), bool):
                values["textual_file_operations_mode"] = False
            preferred_formats = preferred_web_ai_exchange_formats(preferred_web_ai)
            if preferred_formats is not None:
                (
                    values["markdown_exchange_mode"],
                    values["textual_file_operations_mode"],
                ) = preferred_formats
            if not isinstance(values.get("ai_assistant_enabled", False), bool):
                values["ai_assistant_enabled"] = False
            if not isinstance(values.get("ai_assistant_gemma_downloaded", False), bool):
                values["ai_assistant_gemma_downloaded"] = False
            if values.get("ai_assistant_source") not in AI_ASSISTANT_SOURCES:
                values["ai_assistant_source"] = "gemma_internal"
            if values.get("ai_assistant_cloud_provider") not in AI_ASSISTANT_CLOUD_PROVIDERS:
                values["ai_assistant_cloud_provider"] = "groq"
            ai_string_defaults = {
                "ai_assistant_ollama_url": "http://localhost:11434",
                "ai_assistant_ollama_model": "",
                "ai_assistant_cloud_key": "",
                "ai_assistant_cloud_model": "",
            }
            for key, default in ai_string_defaults.items():
                if not isinstance(values.get(key, default), str):
                    values[key] = default
            return AppSettings(**values)
        except Exception:
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        temp.replace(self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
