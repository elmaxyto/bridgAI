from __future__ import annotations

import fnmatch
import os
import re
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from local_ai_bridge.core.safety import is_sensitive_relative_path
from local_ai_bridge.services.project_scanner_helpers import (
    detect_project_version,
    detect_stack,
    summarize_generic,
    summarize_js,
    summarize_python,
)


EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea",
    ".vscode", "backups", "backup", "coverage", ".next", ".nuxt",
}
EXCLUDED_DIRS_CASEFOLD = {name.casefold() for name in EXCLUDED_DIRS}
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml", ".toml",
    ".html", ".css", ".scss", ".go", ".rs", ".java", ".cs", ".md",
}
SPECIAL_FILES = {"Dockerfile", "Makefile", "package.json", "pyproject.toml", "requirements.txt"}
GENERATED_REPORT_PATTERNS = (
    "ai_super_report.md",
    "ai_super_report_*.md",
    "report_diagnostic.md",
    "report_diagnostic_*.md",
    "super_report.md",
    "super_report_*.md",
)
MAX_FILE_BYTES = 750_000
MAX_TREE_ENTRIES = 3_000
MAX_SUMMARY_FILES = 700
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
    discovered_files: int = 0


def _deadline(seconds: float) -> float:
    return time.monotonic() + max(1.0, seconds)


def _check_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise ScanBudgetExceeded("limite di tempo della scansione raggiunto")


def is_generated_report(relative: str) -> bool:
    name = Path(relative).name.lower()
    return any(fnmatch.fnmatch(name, pattern) for pattern in GENERATED_REPORT_PATTERNS)


def _relative_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _allowed_dir(root: Path, current: Path, name: str) -> bool:
    if name.casefold() in EXCLUDED_DIRS_CASEFOLD:
        return False
    relative = _relative_posix(root, current / name)
    return not is_sensitive_relative_path(relative)


def _allowed_file(root: Path, path: Path) -> bool:
    relative = _relative_posix(root, path)
    return not is_sensitive_relative_path(relative) and not is_generated_report(relative)


def _is_reparse_or_link(entry: os.DirEntry[str]) -> bool:
    """Return True for symlinks and Windows reparse points/junctions.

    The scanner never follows these entries. This prevents cycles and very slow
    traversals on Windows where a junction can point back to a parent or to a
    large external tree.
    """
    try:
        if entry.is_symlink():
            return True
        info = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(info, "st_file_attributes", 0)
    return bool(reparse_flag and file_attributes & reparse_flag)


def _safe_entries(root: Path, directory: Path, deadline: float) -> list[tuple[Path, bool]]:
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
                    if _allowed_dir(root, directory, entry.name):
                        items.append((path, True))
                elif is_file and _allowed_file(root, path):
                    items.append((path, False))
    except OSError:
        return []
    return sorted(items, key=lambda item: (not item[1], item[0].name.casefold()))


def _walk_project_files(root: Path, deadline: float) -> Iterator[tuple[Path, str]]:
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
        entries = _safe_entries(root, directory, deadline)
        child_dirs: list[Path] = []
        for path, is_dir in entries:
            if is_dir:
                child_dirs.append(path)
                continue
            files_seen += 1
            if files_seen > MAX_DISCOVERED_FILES:
                raise ScanBudgetExceeded("limite massimo di file raggiunto")
            yield path, _relative_posix(root, path)
        for child in reversed(child_dirs):
            stack.append((child, depth + 1))


def iter_project_files(root: Path, time_budget: float = DEFAULT_SCAN_BUDGET_SECONDS):
    """Yield safe project files without following links or junctions."""
    yield from _walk_project_files(root, _deadline(time_budget))


def _tree(root: Path, deadline: float) -> tuple[str, bool]:
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
        entries = _safe_entries(root, directory, deadline)
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


def rank_task_candidates(root: Path, task: str, limit: int = 12) -> list[str]:
    tokens = {token for token in re.findall(r"[a-zA-Z0-9_]{3,}", task.lower())}
    if not tokens:
        return []
    scored: list[tuple[int, str]] = []
    try:
        files = iter_project_files(root, CANDIDATE_SCAN_BUDGET_SECONDS)
        for path, relative in files:
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS and path.name not in SPECIAL_FILES:
                continue
            score = sum(4 for token in tokens if token in relative.lower())
            try:
                if path.stat().st_size <= MAX_CANDIDATE_BYTES:
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


def scan_project(root: Path, time_budget: float = DEFAULT_SCAN_BUDGET_SECONDS) -> ScanResult:
    summaries: list[str] = []
    sizes: list[tuple[int, str]] = []
    diagnostics: list[str] = []
    scanned = skipped = 0
    deadline = _deadline(time_budget)

    try:
        files = list(_walk_project_files(root, deadline))
    except ScanBudgetExceeded as exc:
        files = []
        diagnostics.append(f"Scansione filesystem interrotta in sicurezza: {exc}.")

    for path, relative in files:
        try:
            _check_deadline(deadline)
        except ScanBudgetExceeded:
            diagnostics.append("Analisi dei file troncata per limite di tempo.")
            skipped += max(0, len(files) - scanned)
            break
        try:
            size = path.stat().st_size
            loc = sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
        except OSError:
            skipped += 1
            continue

        supported = path.suffix.lower() in SUPPORTED_EXTENSIONS or path.name in SPECIAL_FILES
        if supported:
            sizes.append((loc, relative))
        if not supported:
            continue
        if scanned >= MAX_SUMMARY_FILES:
            skipped += 1
            continue
        if size > MAX_FILE_BYTES:
            summaries.append(f"### `{relative}`\n[File oltre il limite di scansione: {size} byte]\n")
            skipped += 1
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            summaries.append(f"### `{relative}`\n[Errore lettura: {exc}]\n")
            skipped += 1
            continue

        if path.suffix.lower() == ".py":
            summary, found = summarize_python(content, relative)
            diagnostics.extend(found)
        elif path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}:
            summary = summarize_js(content)
        else:
            summary = summarize_generic(path, content)
        summaries.append(f"### `{relative}`\n```text\n{summary}\n```\n")
        scanned += 1

    sizes.sort(reverse=True)
    hot_rows = []
    for loc, relative in sizes[:20]:
        icon = "🔥" if loc >= 350 else "⚠️" if loc >= 300 else "🛠️"
        hot_rows.append(f"- {icon} `{relative}` ({loc} LOC)")

    tree, tree_truncated = _tree(root, _deadline(min(15.0, time_budget)))
    if tree_truncated:
        diagnostics.append("Albero del progetto troncato in sicurezza per limite di tempo o dimensione.")

    return ScanResult(
        tree=tree,
        summaries="\n".join(summaries) or "Nessun file supportato rilevato.",
        hot_files="\n".join(hot_rows) or "- Nessun file testuale rilevato.",
        stack=detect_stack(root),
        project_version=detect_project_version(root),
        diagnostics=diagnostics,
        scanned_files=scanned,
        skipped_files=skipped,
        discovered_files=len(files),
    )
