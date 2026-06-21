from __future__ import annotations

import stat
import subprocess
import time
from pathlib import Path
from typing import Protocol

from local_ai_bridge.services.project_scanner_policy import (
    PRIORITY_DIR_RANK,
    ProjectIgnoreRules,
    directory_exclusion_reason,
    file_exclusion_reason,
    is_media_file,
    project_file_sort_key,
)


GIT_DISCOVERY_TIMEOUT_SECONDS = 8.0
MEDIA_TREE_COMPACT_THRESHOLD = 4


class GitDiscoveryBudgetExceeded(RuntimeError):
    """Raised when Git-backed discovery exceeds the scanner deadline."""


class ScanStatsLike(Protocol):
    def exclude_directory(self, reason: str, key: str | None = None) -> None: ...
    def exclude_file(self, reason: str) -> None: ...
    def discover_file(self) -> None: ...


def _check_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise GitDiscoveryBudgetExceeded("limite di tempo della scansione Git raggiunto")


def _is_path_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        info = path.lstat()
    except OSError:
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(info, "st_file_attributes", 0)
    return bool(reparse_flag and file_attributes & reparse_flag)


def _path_directory_exclusion(
    root: Path,
    relative: str,
    ignore: ProjectIgnoreRules,
    cache: dict[str, tuple[str, str] | None] | None = None,
) -> tuple[str, str] | None:
    current = root
    parts = Path(relative).parts[:-1]
    walked: list[str] = []
    for part in parts:
        walked.append(part)
        key = "/".join(walked)
        if cache is not None and key in cache:
            cached = cache[key]
            if cached is not None:
                return cached
            current = current / part
            continue

        reason = directory_exclusion_reason(root, current, part, ignore)
        result = (reason, key) if reason else None
        if cache is not None:
            cache[key] = result
        if result is not None:
            return result
        current = current / part
    return None


def git_manifest(
    root: Path,
    deadline: float,
    ignore: ProjectIgnoreRules,
    stats: ScanStatsLike | None = None,
) -> list[tuple[Path, str]] | None:
    """Return tracked and untracked non-ignored files for a Git workspace.

    Git remains the authoritative parser for nested .gitignore files, negation
    rules and repository-specific exclusions. Built-in BridgAI rules are still
    applied afterwards, so tracked dependency/build directories do not leak into
    the report.
    """
    if not (root / ".git").exists():
        return None
    remaining = max(0.1, deadline - time.monotonic())
    timeout = min(GIT_DISCOVERY_TIMEOUT_SECONDS, remaining)
    try:
        result = subprocess.run(
            [
                "git", "ls-files", "-z", "--cached", "--others",
                "--exclude-standard",
            ],
            cwd=root,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None

    items: list[tuple[Path, str]] = []
    seen_relatives: set[str] = set()
    directory_cache: dict[str, tuple[str, str] | None] = {}
    for index, raw in enumerate(result.stdout.split(b"\0")):
        if index % 128 == 0:
            _check_deadline(deadline)
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        parts = Path(relative).parts
        if not parts or Path(relative).is_absolute() or ".." in parts:
            continue

        # Apply lexical exclusions before touching the filesystem. This matters
        # for SSHFS/network workspaces and for repositories that accidentally
        # track large dependency trees such as node_modules.
        excluded_dir = _path_directory_exclusion(
            root,
            relative,
            ignore,
            directory_cache,
        )
        if excluded_dir:
            if stats is not None:
                reason, key = excluded_dir
                stats.exclude_directory(reason, key)
            continue

        path = root.joinpath(*parts)
        reason = file_exclusion_reason(root, path, ignore)
        if reason:
            if stats is not None:
                stats.exclude_file(reason)
            continue

        if _is_path_link_or_reparse(path) or not path.is_file():
            continue
        if relative in seen_relatives:
            continue
        seen_relatives.add(relative)
        if stats is not None:
            stats.discover_file()
        items.append((path, relative))
    items.sort(key=project_file_sort_key)
    return items


def tree_from_manifest(
    root: Path,
    files: list[tuple[Path, str]],
    *,
    max_entries: int,
    max_depth: int,
) -> tuple[str, bool]:
    tree: dict[str, dict | None] = {}
    for _, relative in files:
        cursor = tree
        parts = Path(relative).parts
        for part in parts[:-1]:
            child = cursor.setdefault(part, {})
            if not isinstance(child, dict):
                break
            cursor = child
        else:
            if parts:
                cursor.setdefault(parts[-1], None)

    rows = [f"{root.name}/"]
    count = 0
    truncated = False

    def sort_key(item: tuple[str, dict | None]) -> tuple[int, int, str]:
        name, child = item
        is_dir = isinstance(child, dict)
        if is_dir:
            priority = PRIORITY_DIR_RANK.get(name.casefold(), len(PRIORITY_DIR_RANK))
            return 0, priority, name.casefold()
        return 1, len(PRIORITY_DIR_RANK), name.casefold()

    def media_leaf_count(node: dict[str, dict | None]) -> int | None:
        count = 0
        for name, child in node.items():
            if isinstance(child, dict):
                nested = media_leaf_count(child)
                if nested is None:
                    return None
                count += nested
            elif is_media_file(name):
                count += 1
            else:
                return None
        return count

    def visit(node: dict[str, dict | None], prefix: str, depth: int) -> bool:
        nonlocal count, truncated
        if depth > max_depth:
            rows.append(prefix + "└── ... [profondità massima raggiunta]")
            truncated = True
            return True
        entries = sorted(node.items(), key=sort_key)
        for index, (name, child) in enumerate(entries):
            count += 1
            if count > max_entries:
                rows.append(prefix + "└── ... [albero troncato: limite elementi]")
                truncated = True
                return True
            is_dir = isinstance(child, dict)
            is_last = index == len(entries) - 1
            connector = "└── " if is_last else "├── "
            if is_dir:
                media_count = media_leaf_count(child)
                if media_count is not None and media_count >= MEDIA_TREE_COMPACT_THRESHOLD:
                    rows.append(
                        prefix + connector + name + f"/ [{media_count} file multimediali]"
                    )
                    continue
            rows.append(prefix + connector + name + ("/" if is_dir else ""))
            if is_dir:
                child_prefix = prefix + ("    " if is_last else "│   ")
                if visit(child, child_prefix, depth + 1):
                    return True
        return False

    visit(tree, "", 0)
    return "\n".join(rows), truncated
