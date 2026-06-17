from __future__ import annotations

from pathlib import Path

from local_ai_bridge.core.models import SkillResult
from local_ai_bridge.core.skills import SkillContext, SkillRegistry, SkillSpec
from local_ai_bridge.services.exporting import create_export_zip
from local_ai_bridge.services.git import git_status
from local_ai_bridge.services.reporting import build_super_report
from local_ai_bridge.services.testing import format_test_results, run_detected_tests


def _workspace(context: SkillContext) -> Path:
    if context.workspace is None:
        raise ValueError("Seleziona prima un workspace.")
    return Path(context.workspace).resolve(strict=True)


def register_builtin_skills(registry: SkillRegistry) -> None:
    registry.register(SkillSpec(
        "report.generate", "Genera Super-Report",
        "Scansiona il progetto e produce il contesto operativo per l'AI Web.",
        frozenset({"workspace.read", "git.read"}),
        lambda ctx, p: SkillResult(True, "Report generato.", build_super_report(_workspace(ctx), p.get("task", ""))),
    ))
    registry.register(SkillSpec(
        "files.export", "Esporta file richiesti",
        "Crea uno ZIP con i file richiesti tramite #scarica.",
        frozenset({"workspace.read"}),
        lambda ctx, p: SkillResult(
            True, "ZIP creato.",
            create_export_zip(_workspace(ctx), list(p["requested"]), Path(p["destination"])),
        ),
    ))
    registry.register(SkillSpec(
        "tests.run", "Esegui test rilevati",
        "Esegue compile, test, lint e build rilevati nel workspace.",
        frozenset({"workspace.read", "command.run"}),
        lambda ctx, p: SkillResult(
            True, "Controlli completati.",
            format_test_results(run_detected_tests(_workspace(ctx))),
        ),
    ))
    registry.register(SkillSpec(
        "git.status", "Stato Git",
        "Mostra branch e file modificati senza scrivere nel repository.",
        frozenset({"git.read"}),
        lambda ctx, p: SkillResult(True, "Stato Git acquisito.", git_status(_workspace(ctx))),
    ))
