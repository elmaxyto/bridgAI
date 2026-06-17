from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "LocalAIBridge"
APP_AUTHOR = "LocalAIBridge"
DEFAULT_SIMPLE_MODE = True


def app_data_dir() -> Path:
    path = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(slots=True)
class AppSettings:
    language: str = "it"
    last_workspace: str = ""
    simple_mode: bool = DEFAULT_SIMPLE_MODE
    dark_mode: bool = False
    chatgpt_url: str = "https://chatgpt.com/"
    claude_url: str = "https://claude.ai/"
    grok_url: str = "https://grok.com/"
    temp_directory: str = ""
    update_zip_directory: str = ""
    gemini_drive_enabled: bool = False
    gemini_drive_path: str = ""
    web_auto_start: bool = False
    web_open_browser: bool = True
    web_port: int = 8765
    web_stop_on_exit: bool = True
    web_workspace_root: str = ""
    web_remote_access: bool = False
    web_username: str = ""
    web_password_hash: str = ""


class SettingsStore:
    def __init__(self) -> None:
        self.path = app_data_dir() / "settings.json"

    def load(self) -> AppSettings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            values = {k: v for k, v in data.items() if k in AppSettings.__annotations__}
            # The desktop app must never start the local web interface implicitly.
            # Keep reading the legacy field for compatibility, but force manual startup.
            values["web_auto_start"] = False
            return AppSettings(**values)
        except Exception:
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)
