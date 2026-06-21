from __future__ import annotations

import subprocess
from pathlib import Path

from local_ai_bridge.services.project_scanner_policy import (
    directory_exclusion_reason,
    file_exclusion_reason,
    load_project_ignore,
)


def _status_relative_path(line: str) -> str | None:
    if line.startswith("## ") or len(line) < 4:
        return None
    value = line[3:].strip()
    if " -> " in value:
        value = value.rsplit(" -> ", 1)[-1]
    return value.strip('"').replace("\\", "/")


def _git_path_exclusion_reason(root: Path, relative: str, ignore) -> str | None:
    current = root
    parts = Path(relative).parts
    for part in parts[:-1]:
        reason = directory_exclusion_reason(root, current, part, ignore)
        if reason:
            return reason
        current = current / part
    return file_exclusion_reason(root, root.joinpath(*parts), ignore)


def compact_git_status(root: Path, output: str) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    if not lines:
        return "Working tree pulita."

    ignore = load_project_ignore(root)
    visible: list[str] = []
    omitted: dict[str, int] = {}
    for line in lines:
        relative = _status_relative_path(line)
        if relative is None:
            visible.append(line)
            continue
        reason = _git_path_exclusion_reason(root, relative, ignore)
        if reason:
            omitted[reason] = omitted.get(reason, 0) + 1
            continue
        visible.append(line)

    if omitted:
        total = sum(omitted.values())
        detail = ", ".join(
            f"{reason}: {count}" for reason, count in sorted(omitted.items())
        )
        visible.append(
            f"... {total} modifiche in percorsi tecnici omesse dal dettaglio ({detail})."
        )
    return "\n".join(visible) or "Working tree pulita."


def git_snapshot(root: Path) -> str:
    if not (root / ".git").exists():
        return "Repository Git non rilevato."
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        output = (result.stdout + result.stderr).strip()
        return compact_git_status(root, output)
    except Exception as exc:
        return f"Git status non disponibile: {exc}"
