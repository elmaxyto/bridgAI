from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "LocalAIBridge"
APP_AUTHOR = "LocalAIBridge"
DEFAULT_SIMPLE_MODE = True
MAX_RECENT_WORKSPACES = 10


def app_data_dir() -> Path:
    path = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(slots=True)
class AppSettings:
    language: str = "it"
    last_workspace: str = ""
    recent_workspaces: list[str] = field(default_factory=list)
    simple_mode: bool = DEFAULT_SIMPLE_MODE
    dark_mode: bool = False
    include_custom_prompts: bool = True
    global_prompt: str = ""
    chatgpt_url: str = "https://chatgpt.com/"
    claude_url: str = "https://claude.ai/"
    grok_url: str = "https://grok.com/"
    temp_directory: str = ""
    update_zip_directory: str = ""
    gemini_drive_enabled: bool = False
    gemini_drive_path: str = ""
    markdown_exchange_mode: bool = False
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
            values["recent_workspaces"] = normalize_recent_workspaces(
                values.get("recent_workspaces", [])
            )
            if not isinstance(values.get("web_totp_recovery_hashes", []), list):
                values["web_totp_recovery_hashes"] = []
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
