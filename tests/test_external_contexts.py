from __future__ import annotations

from pathlib import Path

from local_ai_bridge.core.settings import AppSettings
from local_ai_bridge.services.external_contexts import resolve_external_context_roots


def test_external_contexts_reject_overlapping_roots(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    child = workspace / "nested"
    child.mkdir()
    sibling = tmp_path / "library"
    sibling.mkdir()

    roots, diagnostics = resolve_external_context_roots(
        workspace,
        AppSettings(external_context_paths=[str(tmp_path), str(child), str(sibling)]),
    )

    assert [root.path for root in roots] == [sibling.resolve()]
    assert any("si sovrappone al workspace corrente" in item for item in diagnostics)


def test_external_contexts_reject_symbolic_links(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    link = tmp_path / "linked-target"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        return

    roots, diagnostics = resolve_external_context_roots(
        workspace,
        AppSettings(external_context_paths=[str(link), str(target)]),
    )

    assert [root.path for root in roots] == [target.resolve()]
    assert any("link simbolici non sono consentiti" in item for item in diagnostics)
