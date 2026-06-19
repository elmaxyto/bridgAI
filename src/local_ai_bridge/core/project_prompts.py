from __future__ import annotations

import json
from pathlib import Path


PROJECT_SETTINGS_RELATIVE = ".bridgai/project.json"
MAX_PROJECT_PROMPT_CHARS = 20_000
PROJECT_IGNORE_RELATIVE = ".bridgai/ignore"
MAX_PROJECT_IGNORE_CHARS = 100_000


def project_settings_path(workspace: Path) -> Path:
    return workspace / PROJECT_SETTINGS_RELATIVE


def load_project_prompt(workspace: Path) -> str:
    path = project_settings_path(workspace)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return ""
    value = data.get("project_prompt", "") if isinstance(data, dict) else ""
    return value[:MAX_PROJECT_PROMPT_CHARS] if isinstance(value, str) else ""


def save_project_prompt(workspace: Path, prompt: str) -> Path:
    path = project_settings_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            data.update(existing)
    except (OSError, ValueError, TypeError):
        pass
    data["project_prompt"] = prompt.strip()[:MAX_PROJECT_PROMPT_CHARS]
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    return path


def project_ignore_path(workspace: Path) -> Path:
    return workspace / PROJECT_IGNORE_RELATIVE


def load_project_ignore(workspace: Path) -> str:
    try:
        return project_ignore_path(workspace).read_text(encoding="utf-8")[:MAX_PROJECT_IGNORE_CHARS]
    except OSError:
        return ""


def save_project_ignore(workspace: Path, content: str) -> Path:
    path = project_ignore_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")[:MAX_PROJECT_IGNORE_CHARS]
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    temp = path.with_suffix(".tmp")
    temp.write_text(normalized, encoding="utf-8")
    temp.replace(path)
    return path
