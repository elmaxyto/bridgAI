from __future__ import annotations

import os
import re
import stat
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from local_ai_bridge.services.project_scanner_git import (
    GIT_DISCOVERY_TIMEOUT_SECONDS,
    GitDiscoveryBudgetExceeded,
    git_manifest,
    tree_from_manifest,
)
from local_ai_bridge.services.project_scanner_helpers import (
    detect_project_version,
    detect_stack,
)
from local_ai_bridge.services.project_scanner_policy import (
    SPECIAL_FILES,
    SUPPORTED_EXTENSIONS,
    ProjectIgnoreRules,
    directory_exclusion_reason,
    directory_scan_key,
    file_exclusion_reason,
    is_compact_metadata_file,
    is_context_file,
    is_generated_report,
    load_project_ignore,
    relative_posix,
)
from local_ai_bridge.services.project_scanner_summary import (
    adaptive_summary_limit,
    format_hot_files,
    summarize_files,
)


__all__ = (
    "ProjectIgnoreRules",
    "ScanBudgetExceeded",
    "ScanResult",
    "SPECIAL_FILES",
    "SUPPORTED_EXTENSIONS",
    "is_generated_report",
    "iter_project_files",
    "load_project_ignore",
    "rank_task_candidates",
    "scan_project",
)


MAX_FILE_BYTES = 750_000
MAX_TREE_ENTRIES = 3_000
MAX_SUMMARY_FILES = 240
MAX_CANDIDATE_BYTES = 120_000
MAX_DISCOVERED_FILES = 12_000
MAX_DISCOVERED_DIRS = 2_000
MAX_SCAN_DEPTH = 40
DEFAULT_SCAN_BUDGET_SECONDS = 45.0
CANDIDATE_SCAN_BUDGET_SECONDS = 15.0


class ScanBudgetExceeded(RuntimeError):
    """Raised internally when a filesystem scan exceeds its safety budget."""


@dataclass(slots=True)
class ScanResult:
    tree: str
    summaries: str
    hot_files: str
    stack: str
    project_version: str | None = None
    diagnostics: list[str] = field(default_factory=list)
    scanned_files: int = 0
    skipped_files: int = 0
    omitted_files: int = 0
    discovered_files: int = 0
    excluded_directories: int = 0
    excluded_files: int = 0
    exclusion_summary: str = ""
    discovery_mode: str = "filesystem filtrato"
    python_files: int = 0
    python_syntax_errors: int = 0
    javascript_files: int = 0


@dataclass(slots=True)
class ScanStats:
    excluded_directories: int = 0
    excluded_files: int = 0
    discovered_files: int = 0
    reasons: Counter[str] = field(default_factory=Counter)
    excluded_directory_keys: set[str] = field(default_factory=set)

    def exclude_directory(self, reason: str, key: str | None = None) -> None:
        if key is not None:
            normalized = key.casefold()
            if normalized in self.excluded_directory_keys:
                return
            self.excluded_directory_keys.add(normalized)
        self.excluded_directories += 1
        self.reasons[f"dir: {reason}"] += 1

    def exclude_file(self, reason: str) -> None:
        self.excluded_files += 1
        self.reasons[f"file: {reason}"] += 1

    def discover_file(self) -> None:
        self.discovered_files += 1

    def merge(self, other: "ScanStats") -> None:
        self.excluded_directories += other.excluded_directories
        self.excluded_files += other.excluded_files
        self.discovered_files += other.discovered_files
        self.reasons.update(other.reasons)
        self.excluded_directory_keys.update(other.excluded_directory_keys)

    def summary(self, limit: int = 8) -> str:
        if not self.reasons:
            return "nessuna esclusione automatica"
        rows = [f"{reason} ({count})" for reason, count in self.reasons.most_common(limit)]
        remaining = len(self.reasons) - len(rows)
        if remaining > 0:
            rows.append(f"altre categorie ({remaining})")
        return ", ".join(rows)


def _deadline(seconds: float) -> float:
    return time.monotonic() + max(1.0, seconds)


def _check_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise ScanBudgetExceeded("limite di tempo della scansione raggiunto")


def _git_attempt_deadline(deadline: float) -> float:
    """Reserve time for the filtered-filesystem fallback."""
    remaining = max(0.1, deadline - time.monotonic())
    git_budget = min(GIT_DISCOVERY_TIMEOUT_SECONDS + 1.0, max(0.5, remaining * 0.35))
    return min(deadline, _deadline(git_budget))


def _is_reparse_or_link(entry: os.DirEntry[str]) -> bool:
    """Return True for symlinks and Windows reparse points/junctions."""
    try:
        if entry.is_symlink():
            return True
    except OSError:
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if not reparse_flag:
        return False
    try:
        info = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    file_attributes = getattr(info, "st_file_attributes", 0)
    return bool(file_attributes & reparse_flag)


def _safe_entries(
    root: Path,
    directory: Path,
    deadline: float,
    ignore: ProjectIgnoreRules,
    stats: ScanStats | None = None,
    *,
    context_only: bool = False,
) -> list[tuple[Path, bool]]:
    _check_deadline(deadline)
    items: list[tuple[Path, bool]] = []
    try:
        with os.scandir(directory) as iterator:
            for entry in iterator:
                _check_deadline(deadline)
                if _is_reparse_or_link(entry):
                    continue
                path = Path(entry.path)
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    is_file = entry.is_file(follow_symlinks=False)
                except OSError:
                    continue
                if is_dir:
                    reason = directory_exclusion_reason(root, directory, entry.name, ignore)
                    if reason:
                        if stats is not None:
                            stats.exclude_directory(reason)
                        continue
                    items.append((path, True))
                elif is_file:
                    reason = file_exclusion_reason(root, path, ignore)
                    if reason:
                        if stats is not None:
                            stats.exclude_file(reason)
                        continue
                    if stats is not None:
                        stats.discover_file()
                    if context_only and not is_context_file(path):
                        continue
                    items.append((path, False))
    except OSError:
        return []
    return sorted(items, key=lambda item: (not item[1], item[0].name.casefold()))


def _walk_project_files(
    root: Path,
    deadline: float,
    ignore: ProjectIgnoreRules,
    stats: ScanStats | None = None,
    *,
    context_only: bool = False,
) -> Iterator[tuple[Path, str]]:
    stack: list[tuple[Path, int]] = [(root, 0)]
    directories_seen = 0
    files_seen = 0
    while stack:
        _check_deadline(deadline)
        directory, depth = stack.pop()
        if depth > MAX_SCAN_DEPTH:
            continue
        directories_seen += 1
        if directories_seen > MAX_DISCOVERED_DIRS:
            raise ScanBudgetExceeded("limite massimo di directory raggiunto")
        entries = _safe_entries(
            root,
            directory,
            deadline,
            ignore,
            stats,
            context_only=context_only,
        )
        child_dirs: list[Path] = []
        for path, is_dir in entries:
            if is_dir:
                child_dirs.append(path)
                continue
            files_seen += 1
            if files_seen > MAX_DISCOVERED_FILES:
                raise ScanBudgetExceeded("limite massimo di file rilevanti raggiunto")
            yield path, relative_posix(root, path)
        child_dirs.sort(key=directory_scan_key)
        for child in reversed(child_dirs):
            stack.append((child, depth + 1))


def iter_project_files(root: Path, time_budget: float = DEFAULT_SCAN_BUDGET_SECONDS):
    """Yield safe project files without following links or junctions."""
    ignore = load_project_ignore(root)
    deadline = _deadline(time_budget)
    try:
        manifest = git_manifest(root, _git_attempt_deadline(deadline), ignore)
    except GitDiscoveryBudgetExceeded:
        manifest = None
    if manifest is not None:
        yield from manifest
        return
    yield from _walk_project_files(root, deadline, ignore)


def _tree(root: Path, deadline: float, ignore: ProjectIgnoreRules) -> tuple[str, bool]:
    rows = [f"{root.name}/"]
    count = 0
    truncated = False

    def visit(directory: Path, prefix: str, depth: int) -> bool:
        nonlocal count, truncated
        _check_deadline(deadline)
        if depth > MAX_SCAN_DEPTH:
            rows.append(prefix + "└── ... [profondità massima raggiunta]")
            truncated = True
            return True
        entries = _safe_entries(root, directory, deadline, ignore)
        for index, (entry, is_dir) in enumerate(entries):
            _check_deadline(deadline)
            count += 1
            if count > MAX_TREE_ENTRIES:
                rows.append(prefix + "└── ... [albero troncato: limite elementi]")
                truncated = True
                return True
            is_last = index == len(entries) - 1
            connector = "└── " if is_last else "├── "
            rows.append(prefix + connector + entry.name + ("/" if is_dir else ""))
            if is_dir:
                child_prefix = prefix + ("    " if is_last else "│   ")
                if visit(entry, child_prefix, depth + 1):
                    return True
        return False

    try:
        visit(root, "", 0)
    except ScanBudgetExceeded:
        rows.append("└── ... [albero troncato: limite tempo]")
        truncated = True
    return "\n".join(rows), truncated


def _candidate_files(
    root: Path,
    deadline: float,
    ignore: ProjectIgnoreRules,
) -> Iterator[tuple[Path, str]]:
    try:
        manifest = git_manifest(root, _git_attempt_deadline(deadline), ignore)
    except GitDiscoveryBudgetExceeded:
        manifest = None
    if manifest is not None:
        return (item for item in manifest if is_context_file(item[0]))
    return _walk_project_files(root, deadline, ignore, context_only=True)


def rank_task_candidates(root: Path, task: str, limit: int = 12) -> list[str]:
    tokens = {token for token in re.findall(r"[a-zA-Z0-9_]{3,}", task.lower())}
    if not tokens:
        return []
    scored: list[tuple[int, str]] = []
    ignore = load_project_ignore(root)
    try:
        files = _candidate_files(root, _deadline(CANDIDATE_SCAN_BUDGET_SECONDS), ignore)
        for path, relative in files:
            score = sum(4 for token in tokens if token in relative.lower())
            try:
                if not is_compact_metadata_file(path) and path.stat().st_size <= MAX_CANDIDATE_BYTES:
                    sample = path.read_text(encoding="utf-8", errors="replace").lower()
                    score += sum(min(sample.count(token), 5) for token in tokens)
            except OSError:
                continue
            if score:
                scored.append((score, relative))
    except ScanBudgetExceeded:
        pass
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [relative for _, relative in scored[:limit]]


def _discover_context_files(
    root: Path,
    deadline: float,
    ignore: ProjectIgnoreRules,
    stats: ScanStats,
    diagnostics: list[str],
) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]] | None, str]:
    files: list[tuple[Path, str]] = []
    manifest: list[tuple[Path, str]] | None = None
    discovery_mode = "filesystem filtrato"
    git_stats = ScanStats()
    git_workspace = (root / ".git").exists()

    try:
        manifest = git_manifest(
            root,
            _git_attempt_deadline(deadline),
            ignore,
            git_stats,
        )
    except GitDiscoveryBudgetExceeded:
        manifest = None
        diagnostics.append(
            "Manifest Git non completato entro il budget riservato; "
            "attivato il fallback sul filesystem filtrato."
        )

    if manifest is not None:
        stats.merge(git_stats)
        discovery_mode = "manifest Git + filtri BridgAI"
        context_files = [item for item in manifest if is_context_file(item[0])]
        if len(context_files) > MAX_DISCOVERED_FILES:
            diagnostics.append(
                "Elenco dei file rilevanti troncato al limite massimo configurato."
            )
            context_files = context_files[:MAX_DISCOVERED_FILES]
        files.extend(context_files)
        return files, manifest, discovery_mode

    if git_workspace:
        discovery_mode = "filesystem filtrato (fallback Git)"
        if not any("fallback sul filesystem" in item for item in diagnostics):
            diagnostics.append(
                "Manifest Git non disponibile; utilizzato il fallback sul filesystem filtrato."
            )

    try:
        files.extend(
            _walk_project_files(
                root,
                deadline,
                ignore,
                stats,
                context_only=True,
            )
        )
    except ScanBudgetExceeded as exc:
        diagnostics.append(
            f"Scansione filesystem interrotta in sicurezza: {exc}. "
            f"Conservati {len(files)} file già individuati e ritenuti rilevanti."
        )
    return files, None, discovery_mode


def scan_project(
    root: Path,
    time_budget: float = DEFAULT_SCAN_BUDGET_SECONDS,
    task: str = "",
) -> ScanResult:
    diagnostics: list[str] = []
    deadline = _deadline(time_budget)
    discovery_budget = min(25.0, max(5.0, time_budget * 0.6))
    discovery_deadline = min(deadline, _deadline(discovery_budget))
    ignore = load_project_ignore(root)
    stats = ScanStats()

    files, manifest, discovery_mode = _discover_context_files(
        root,
        discovery_deadline,
        ignore,
        stats,
        diagnostics,
    )
    summary_limit = adaptive_summary_limit(len(files), task, MAX_SUMMARY_FILES)
    summary = summarize_files(
        files,
        deadline=deadline,
        max_file_bytes=MAX_FILE_BYTES,
        max_summary_files=summary_limit,
        task=task,
    )
    if summary.omitted_files:
        diagnostics.append(
            f"Limite adattivo del contesto: {summary_limit} file espansi su "
            f"{summary_limit + summary.omitted_files} file rilevanti indicizzati."
        )
    diagnostics.extend(summary.diagnostics)

    if manifest is not None:
        tree, tree_truncated = tree_from_manifest(
            root,
            manifest,
            max_entries=MAX_TREE_ENTRIES,
            max_depth=MAX_SCAN_DEPTH,
        )
    else:
        tree, tree_truncated = _tree(root, _deadline(min(15.0, time_budget)), ignore)
    if tree_truncated:
        diagnostics.append("Albero del progetto troncato in sicurezza per limite di tempo o dimensione.")

    return ScanResult(
        tree=tree,
        summaries="\n".join(summary.summaries) or "Nessun file supportato rilevato.",
        hot_files=format_hot_files(summary.code_sizes),
        stack=detect_stack(root),
        project_version=detect_project_version(root),
        diagnostics=diagnostics,
        scanned_files=summary.scanned_files,
        skipped_files=summary.skipped_files,
        omitted_files=summary.omitted_files,
        discovered_files=stats.discovered_files,
        excluded_directories=stats.excluded_directories,
        excluded_files=stats.excluded_files,
        exclusion_summary=stats.summary(),
        discovery_mode=discovery_mode,
        python_files=summary.python_files,
        python_syntax_errors=summary.python_syntax_errors,
        javascript_files=summary.javascript_files,
    )
