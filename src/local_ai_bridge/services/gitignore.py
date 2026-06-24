from __future__ import annotations

import codecs
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from local_ai_bridge.services.git import GitIntegrationError, _run_command, is_git_repository
from local_ai_bridge.services.gitignore_rules import (
    MANAGED_END,
    MANAGED_START,
    detect_stacks,
    is_managed_generated_path,
    managed_block,
)


_MAX_GITIGNORE_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class GitIgnoreUpdate:
    created: bool = False
    changed: bool = False
    untracked_paths: tuple[str, ...] = ()
    detected_stacks: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        messages: list[str] = []
        if self.created:
            messages.append("Creato .gitignore con le protezioni automatiche di BridgAI.")
        elif self.changed:
            messages.append("Aggiornato il blocco automatico BridgAI in .gitignore.")
        if self.untracked_paths:
            count = len(self.untracked_paths)
            messages.append(
                f"Rimossi dall'indice Git {count} file generati o locali già tracciati; "
                "i file sul computer sono stati conservati."
            )
            if any(
                Path(relative).name.lower() == ".env"
                or (
                    Path(relative).name.lower().startswith(".env.")
                    and Path(relative).name.lower()
                    not in {".env.example", ".env.sample", ".env.template"}
                )
                for relative in self.untracked_paths
            ):
                messages.append(
                    "Attenzione: eventuali segreti già pubblicati possono restare nella cronologia Git; "
                    "ruota le credenziali e valuta una bonifica separata della cronologia."
                )
        return "\n".join(messages)


def _workspace_has_content(workspace: Path) -> bool:
    try:
        return any(entry.name != ".git" for entry in workspace.iterdir())
    except OSError as exc:
        raise GitIntegrationError(f"Impossibile leggere il workspace: {exc}") from exc


def _decode_gitignore(path: Path) -> tuple[str, bool]:
    if not path.exists():
        return "", False
    if path.is_symlink():
        raise GitIntegrationError("Il file .gitignore è un collegamento simbolico e non verrà modificato.")
    if not path.is_file():
        raise GitIntegrationError("Il percorso .gitignore esiste ma non è un file regolare.")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise GitIntegrationError(f"Impossibile leggere .gitignore: {exc}") from exc
    if len(raw) > _MAX_GITIGNORE_BYTES:
        raise GitIntegrationError("Il file .gitignore è troppo grande per essere aggiornato automaticamente.")
    has_bom = raw.startswith(codecs.BOM_UTF8)
    payload = raw[len(codecs.BOM_UTF8) :] if has_bom else raw
    try:
        return payload.decode("utf-8"), has_bom
    except UnicodeDecodeError as exc:
        raise GitIntegrationError("Il file .gitignore non è codificato in UTF-8.") from exc


def _updated_text(existing: str, block: str) -> str:
    start_count = existing.count(MANAGED_START)
    end_count = existing.count(MANAGED_END)
    if start_count != end_count or start_count > 1:
        raise GitIntegrationError(
            "Il blocco BridgAI in .gitignore è incompleto o duplicato; correggilo prima della pubblicazione."
        )

    newline = "\r\n" if "\r\n" in existing else "\n"
    native_block = block.replace("\n", newline)
    if start_count == 0:
        if not existing:
            return native_block + newline
        return native_block + newline * 2 + existing.lstrip("\r\n")

    start = existing.index(MANAGED_START)
    end = existing.index(MANAGED_END, start) + len(MANAGED_END)
    custom_rules = (existing[:start] + existing[end:]).lstrip("\r\n")
    if not custom_rules:
        return native_block + newline
    return native_block + newline * 2 + custom_rules


def _write_gitignore(path: Path, text: str, has_bom: bool) -> None:
    payload = text.encode("utf-8")
    if has_bom:
        payload = codecs.BOM_UTF8 + payload
    try:
        path.write_bytes(payload)
    except OSError as exc:
        raise GitIntegrationError(f"Impossibile aggiornare .gitignore: {exc}") from exc


def gitignore_update_needed(workspace: Path) -> bool:
    workspace = Path(workspace)
    if not workspace.is_dir() or not _workspace_has_content(workspace):
        return False
    path = workspace / ".gitignore"
    existing, _has_bom = _decode_gitignore(path)
    desired = _updated_text(existing, managed_block(detect_stacks(workspace)))
    return desired != existing


def _tracked_files(workspace: Path) -> tuple[str, ...]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached"],
            cwd=workspace,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitIntegrationError("Git non ha completato l'analisi dei file tracciati entro 60 secondi.") from exc
    except OSError as exc:
        raise GitIntegrationError(f"Impossibile analizzare i file Git tracciati: {exc}") from exc
    if result.returncode != 0:
        git_marker = workspace / ".git"
        if git_marker.is_dir() and not (git_marker / "HEAD").exists():
            return ()
        detail = (result.stderr or result.stdout or b"").decode("utf-8", errors="replace").strip()
        raise GitIntegrationError(f"Git non ha potuto elencare i file tracciati: {detail or result.returncode}")
    return tuple(os.fsdecode(item) for item in result.stdout.split(b"\0") if item)


def _effectively_ignored_paths(workspace: Path, paths: tuple[str, ...]) -> tuple[str, ...]:
    if not paths:
        return ()
    payload = b"".join(os.fsencode(path) + b"\0" for path in paths)
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-z", "--stdin", "--no-index"],
            cwd=workspace,
            input=payload,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitIntegrationError("Git non ha completato il controllo di .gitignore entro 60 secondi.") from exc
    except OSError as exc:
        raise GitIntegrationError(f"Impossibile verificare le regole .gitignore: {exc}") from exc
    if result.returncode == 1:
        return ()
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or b"").decode("utf-8", errors="replace").strip()
        raise GitIntegrationError(f"Git non ha potuto verificare .gitignore: {detail or result.returncode}")
    return tuple(os.fsdecode(item) for item in result.stdout.split(b"\0") if item)


def _path_chunks(paths: tuple[str, ...], maximum_characters: int = 7000) -> tuple[tuple[str, ...], ...]:
    chunks: list[tuple[str, ...]] = []
    current: list[str] = []
    current_size = 0
    for path in paths:
        size = len(path) + 1
        if current and current_size + size > maximum_characters:
            chunks.append(tuple(current))
            current = []
            current_size = 0
        current.append(path)
        current_size += size
    if current:
        chunks.append(tuple(current))
    return tuple(chunks)


def _untrack_generated_paths(workspace: Path, paths: tuple[str, ...]) -> None:
    for chunk in _path_chunks(paths):
        _run_command(
            ["git", "rm", "-r", "--cached", "--ignore-unmatch", "-f", "--", *chunk],
            cwd=workspace,
            timeout=120,
        )


def ensure_publish_gitignore(workspace: Path, *, untrack: bool = True) -> GitIgnoreUpdate:
    workspace = Path(workspace)
    if not workspace.is_dir():
        raise GitIntegrationError("Il workspace non esiste o non è una cartella.")
    if not _workspace_has_content(workspace):
        return GitIgnoreUpdate()

    stacks = detect_stacks(workspace)
    path = workspace / ".gitignore"
    created = not path.exists()
    existing, has_bom = _decode_gitignore(path)
    desired = _updated_text(existing, managed_block(stacks))
    changed = desired != existing
    if changed:
        _write_gitignore(path, desired, has_bom)

    untracked_paths: tuple[str, ...] = ()
    if untrack and is_git_repository(workspace):
        managed_candidates = tuple(
            relative
            for relative in _tracked_files(workspace)
            if is_managed_generated_path(relative, stacks)
        )
        untracked_paths = _effectively_ignored_paths(workspace, managed_candidates)
        if untracked_paths:
            _untrack_generated_paths(workspace, untracked_paths)

    return GitIgnoreUpdate(
        created=created and changed,
        changed=changed,
        untracked_paths=untracked_paths,
        detected_stacks=stacks,
    )
