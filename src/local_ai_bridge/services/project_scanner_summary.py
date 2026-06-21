from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from local_ai_bridge.services.project_scanner_helpers import (
    summarize_generic,
    summarize_js,
    summarize_python,
)
from local_ai_bridge.services.project_scanner_policy import (
    CODE_EXTENSIONS,
    is_compact_metadata_file,
    is_special_file,
    project_file_sort_key,
)


ENTRYPOINT_NAMES = {
    "__main__.py", "app.py", "main.py", "run.py",
    "main.ts", "main.tsx", "index.ts", "index.tsx",
    "app.ts", "app.tsx", "server.ts", "server.js",
}
BALANCED_ROOTS = {"src", "app", "lib", "packages", "apps"}
LARGE_CODE_RESERVE = 30
GENERAL_CONTEXT_LIMIT = 180
TASK_CONTEXT_LIMIT = 120
FOCUSED_TASK_CONTEXT_LIMIT = 100
FULL_CONTEXT_MARKERS = (
    "analisi completa", "analizza tutto", "tutti i file", "intero progetto",
    "complete analysis", "analyze everything", "all files", "entire project",
)


@dataclass(slots=True)
class SummaryResult:
    summaries: list[str] = field(default_factory=list)
    code_sizes: list[tuple[int, str]] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    scanned_files: int = 0
    skipped_files: int = 0
    omitted_files: int = 0
    python_files: int = 0
    python_syntax_errors: int = 0
    javascript_files: int = 0


def _task_tokens(task: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9_]{3,}", task)
        if token.casefold() not in {"file", "progetto", "project", "codice", "code"}
    }


def adaptive_summary_limit(total_files: int, task: str, hard_limit: int) -> int:
    """Choose a context size that preserves breadth without flooding the prompt."""
    if total_files <= 0 or hard_limit <= 0:
        return 0
    normalized_task = " ".join(task.casefold().split())
    if any(marker in normalized_task for marker in FULL_CONTEXT_MARKERS):
        return min(total_files, hard_limit)
    tokens = _task_tokens(task)
    if not tokens:
        target = GENERAL_CONTEXT_LIMIT
    elif len(tokens) >= 4:
        target = FOCUSED_TASK_CONTEXT_LIMIT
    else:
        target = TASK_CONTEXT_LIMIT
    return min(total_files, hard_limit, target)


def _deduplicate_files(files: list[tuple[Path, str]]) -> list[tuple[Path, str]]:
    """Return one stable entry per normalized project-relative path."""
    unique: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for path, relative in files:
        normalized = relative.replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        normalized = normalized.lstrip("/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append((path, normalized))
    return unique


def _summary_bucket(relative: str) -> str:
    parts = [part.casefold() for part in Path(relative).parts]
    if len(parts) <= 1:
        return "__root__"
    if parts[0] in BALANCED_ROOTS and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _mandatory_priority(
    item: tuple[Path, str],
    *,
    task_tokens: set[str],
    large_code_paths: set[str],
) -> tuple[int, int, tuple[int, int, str]]:
    path, relative = item
    folded = relative.casefold()
    matches = sum(1 for token in task_tokens if token in folded)
    depth = len(Path(relative).parts)
    important = int(
        is_special_file(path)
        or depth == 1
        or path.name.casefold() in ENTRYPOINT_NAMES
        or relative in large_code_paths
    )
    return -matches, -important, project_file_sort_key(item)


def select_summary_files(
    files: list[tuple[Path, str]],
    *,
    limit: int,
    task: str = "",
) -> tuple[list[tuple[Path, str]], int]:
    """Select a compact, balanced context without letting one large folder dominate."""
    files = _deduplicate_files(files)
    if len(files) <= limit:
        return list(files), 0
    if limit <= 0:
        return [], len(files)

    task_tokens = _task_tokens(task)
    largest_code = sorted(
        (
            (_safe_size(path), relative)
            for path, relative in files
            if path.suffix.casefold() in CODE_EXTENSIONS
        ),
        reverse=True,
    )[:LARGE_CODE_RESERVE]
    large_code_paths = {relative for _, relative in largest_code}

    mandatory: list[tuple[Path, str]] = []
    remaining: list[tuple[Path, str]] = []
    for item in files:
        path, relative = item
        folded = relative.casefold()
        depth = len(Path(relative).parts)
        task_match = any(token in folded for token in task_tokens)
        if (
            task_match
            or is_special_file(path)
            or depth == 1
            or path.name.casefold() in ENTRYPOINT_NAMES
            or relative in large_code_paths
        ):
            mandatory.append(item)
        else:
            remaining.append(item)

    mandatory.sort(
        key=lambda item: _mandatory_priority(
            item,
            task_tokens=task_tokens,
            large_code_paths=large_code_paths,
        )
    )
    selected = mandatory[:limit]
    selected_paths = {relative for _, relative in selected}
    if len(selected) >= limit:
        return selected, len(files) - len(selected)

    groups: dict[str, deque[tuple[Path, str]]] = defaultdict(deque)
    for item in sorted(remaining, key=project_file_sort_key):
        if item[1] not in selected_paths:
            groups[_summary_bucket(item[1])].append(item)

    group_order = sorted(
        groups,
        key=lambda key: (
            0 if key == "__root__" else 1,
            project_file_sort_key(groups[key][0]),
            key,
        ),
    )
    while len(selected) < limit and group_order:
        next_round: list[str] = []
        for key in group_order:
            queue = groups[key]
            if queue and len(selected) < limit:
                item = queue.popleft()
                selected.append(item)
                selected_paths.add(item[1])
            if queue:
                next_round.append(key)
        group_order = next_round

    return selected, len(files) - len(selected)


def summarize_files(
    files: list[tuple[Path, str]],
    *,
    deadline: float,
    max_file_bytes: int,
    max_summary_files: int,
    task: str = "",
) -> SummaryResult:
    result = SummaryResult()
    selected, omitted = select_summary_files(
        files,
        limit=max_summary_files,
        task=task,
    )
    result.omitted_files = omitted
    if omitted:
        result.diagnostics.append(
            f"Contesto sintetico: {omitted} file rilevanti indicizzati ma non espansi; "
            "la selezione bilancia configurazioni, entry point, aree del progetto e file grandi."
        )

    for index, (path, relative) in enumerate(selected):
        if time.monotonic() > deadline:
            result.diagnostics.append("Analisi dei file troncata per limite di tempo.")
            result.skipped_files += len(selected) - index
            break
        try:
            size = path.stat().st_size
        except OSError:
            result.skipped_files += 1
            continue

        if is_compact_metadata_file(path):
            result.summaries.append(
                f"### `{relative}`\n```text\n"
                f"Lockfile o metadato dipendenze rilevato ({size} byte); "
                "contenuto non espanso nel report.\n```\n"
            )
            result.scanned_files += 1
            continue
        if size > max_file_bytes:
            result.summaries.append(
                f"### `{relative}`\n[File oltre il limite di scansione: {size} byte]\n"
            )
            result.skipped_files += 1
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            result.summaries.append(f"### `{relative}`\n[Errore lettura: {exc}]\n")
            result.skipped_files += 1
            continue

        loc = content.count("\n") + (1 if content else 0)
        if path.suffix.casefold() in CODE_EXTENSIONS:
            result.code_sizes.append((loc, relative))

        suffix = path.suffix.casefold()
        if suffix == ".py":
            result.python_files += 1
            summary, found = summarize_python(content, relative)
            result.python_syntax_errors += len(found)
            result.diagnostics.extend(found)
        elif suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}:
            result.javascript_files += 1
            summary = summarize_js(content)
        else:
            summary = summarize_generic(path, content)
        result.summaries.append(f"### `{relative}`\n```text\n{summary}\n```\n")
        result.scanned_files += 1
    return result


def format_hot_files(sizes: list[tuple[int, str]]) -> str:
    rows: list[str] = []
    for loc, relative in sorted(sizes, reverse=True)[:20]:
        icon = "🔥" if loc >= 350 else "⚠️" if loc >= 300 else "🛠️"
        rows.append(f"- {icon} `{relative}` ({loc} LOC)")
    return "\n".join(rows) or "- Nessun file di codice testuale rilevato."
