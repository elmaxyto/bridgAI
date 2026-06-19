from __future__ import annotations

import zipfile
from pathlib import Path

from local_ai_bridge.services.exporting import create_export_zip, parse_download_requests
from local_ai_bridge.services.reporting import build_super_report


def test_report_contains_protocol_and_skips_env(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def hello(name):\n    return name\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    report = build_super_report(tmp_path, "Aggiungi un saluto")
    assert "#scarica" in report
    assert "def hello" in report
    assert "SECRET=1" not in report
    assert "app.py" in report



def test_report_requires_commit_message_metadata_in_zip(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")

    report = build_super_report(tmp_path, "Aggiorna il progetto")

    assert "`commit-message.md`" in report
    assert "prima riga non vuota" in report
    assert "modifiche realmente contenute nello ZIP" in report
    assert "non deve essere applicato al workspace" in report


def test_empty_workspace_requires_complete_zip_and_apply_instruction(tmp_path: Path) -> None:
    report = build_super_report(tmp_path, "Crea una piccola applicazione desktop")
    assert "**WORKSPACE VUOTO:**" in report
    assert "non esistono file da richiedere con `#scarica`" in report
    assert "un unico archivio ZIP applicabile" in report
    assert "**Applica ZIP**" in report
    assert "Workspace vuoto: non richiedere file con `#scarica`" in report


def test_empty_workspace_offers_optional_project_interview(tmp_path: Path) -> None:
    report = build_super_report(tmp_path, "Crea un gestionale")

    assert "Se il task è già sufficientemente specifico, procedi direttamente" in report
    assert "Vuoi che ti faccia alcune domande" in report
    assert "Rispondi: No, Breve oppure Dettagliata" in report
    assert "al massimo 4 domande indispensabili" in report
    assert "al massimo 8 domande mirate" in report
    assert "Non chiedere informazioni già presenti" in report
    assert "nella prima risposta fermati alla domanda di scelta" in report


def test_non_empty_workspace_does_not_offer_project_interview(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")

    report = build_super_report(tmp_path, "Aggiorna il progetto")

    assert "Vuoi che ti faccia alcune domande" not in report
    assert "Rispondi: No, Breve oppure Dettagliata" not in report
    assert "intervista opzionale" not in report


def test_workspace_with_unsupported_file_is_not_treated_as_empty(tmp_path: Path) -> None:
    (tmp_path / "asset.bin").write_bytes(b"\x00\x01")
    report = build_super_report(tmp_path, "Crea il progetto")
    assert "**WORKSPACE VUOTO:**" not in report


def test_tree_preserves_directories_and_paths(tmp_path: Path) -> None:
    target = tmp_path / "src" / "demo" / "core"
    target.mkdir(parents=True)
    (target / "service.py").write_text("def run():\n    return True\n", encoding="utf-8")
    report = build_super_report(tmp_path, "Correggi il service")
    assert "├── src/" in report or "└── src/" in report
    assert "│   └── demo/" in report or "    └── demo/" in report or "├── demo/" in report
    assert "core/" in report
    assert "service.py" in report
    assert "`src/demo/core/service.py`" in report


def test_report_detects_dependencies_and_runtime_limits(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[build-system]\nrequires=["setuptools"]\nbuild-backend="setuptools.build_meta"\n'
        '[project]\nname="demo"\nversion="2.3.4"\nrequires-python=">=3.11"\n'
        'dependencies=["PySide6>=6.7", "platformdirs>=4"]\n'
        '[tool.pytest.ini_options]\ntestpaths=["tests"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text(
        "from dataclasses import dataclass\n\n@dataclass\nclass Config:\n    name: str\n",
        encoding="utf-8",
    )
    report = build_super_report(tmp_path, "Aggiorna la GUI")
    assert "PySide6 desktop GUI" in report
    assert "platformdirs" in report
    assert "pytest test suite" in report
    assert "Python package con layout src/" in report
    assert "Versione progetto rilevata:** `2.3.4`" in report
    assert "Import runtime: non verificati" in report
    assert "name: str" in report


def test_readme_is_not_duplicated_as_priority_note(tmp_path: Path) -> None:
    marker = "TESTO_README_UNICO_123"
    (tmp_path / "README.md").write_text(f"# Demo\n{marker}\n", encoding="utf-8")
    report = build_super_report(tmp_path)
    assert report.count(marker) == 1
    notes = report.split("## 12. Note locali prioritarie", 1)[1]
    assert "README.md" not in notes


def test_generated_reports_are_excluded_everywhere(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")
    marker = "VECCHIO_REPORT_DA_NON_INCLUDERE"
    (tmp_path / "AI_SUPER_REPORT.md").write_text(marker + "\n" * 400, encoding="utf-8")
    (tmp_path / "REPORT_DIAGNOSTIC_2026.md").write_text(marker, encoding="utf-8")
    report = build_super_report(tmp_path)
    assert marker not in report
    assert "AI_SUPER_REPORT.md" not in report
    assert "REPORT_DIAGNOSTIC_2026.md" not in report


def test_two_consecutive_reports_do_not_grow_by_self_inclusion(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")
    first = build_super_report(tmp_path)
    (tmp_path / "AI_SUPER_REPORT.md").write_text(first, encoding="utf-8")
    second = build_super_report(tmp_path)
    assert "AI_SUPER_REPORT.md" not in second
    assert abs(len(second) - len(first)) < 200


def test_report_identifies_generator_version(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\nversion="9.8.7"\n', encoding="utf-8"
    )
    report = build_super_report(tmp_path)
    assert "Versione progetto rilevata:** `9.8.7`" in report
    assert "Generatore report:** `BridgAI 1.0.0`" in report


def test_download_parse_and_export(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a=1", encoding="utf-8")
    requested = parse_download_requests("test\n#scarica src/a.py, README.md")
    assert requested == ["src/a.py", "README.md"]
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    destination = tmp_path / "out.zip"
    create_export_zip(tmp_path, requested, destination)
    with zipfile.ZipFile(destination) as zf:
        assert sorted(zf.namelist()) == ["README.md", "src/a.py"]



def test_download_parse_restores_dunder_names_rewritten_by_markdown() -> None:
    requested = parse_download_requests(
        "#scarica src/local_ai_bridge/**init**.py, "
        "src/local_ai_bridge/core/**init**.py"
    )
    assert requested == [
        "src/local_ai_bridge/__init__.py",
        "src/local_ai_bridge/core/__init__.py",
    ]


def test_download_export_accepts_markdown_rewritten_dunder_path(tmp_path: Path) -> None:
    package = tmp_path / "src" / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")

    requested = parse_download_requests("#scarica src/demo/**init**.py")
    destination = tmp_path / "context.zip"
    create_export_zip(tmp_path, requested, destination)

    with zipfile.ZipFile(destination) as zf:
        assert zf.namelist() == ["src/demo/__init__.py"]

def test_scanner_does_not_follow_symlink_cycles(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    loop = project / "loop"
    try:
        loop.symlink_to(project, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
    report = build_super_report(project)
    assert "app.py" in report
    assert "loop/" not in report


def test_scanner_skips_excluded_dirs_case_insensitively(tmp_path: Path) -> None:
    cache = tmp_path / "__PYCACHE__"
    cache.mkdir()
    (cache / "hidden.py").write_text("SECRET_MARKER = True\n", encoding="utf-8")
    (tmp_path / "visible.py").write_text("VISIBLE = True\n", encoding="utf-8")
    report = build_super_report(tmp_path)
    assert "visible.py" in report
    assert "SECRET_MARKER" not in report


def test_project_ignore_excludes_files_directories_candidates_and_notes(tmp_path: Path) -> None:
    config = tmp_path / ".bridgai"
    config.mkdir()
    (config / "ignore").write_text(
        "# Project-local report exclusions\n"
        "generated/\n"
        "*.sqlite\n"
        "docs/private/**\n"
        "TODO.md\n",
        encoding="utf-8",
    )
    (tmp_path / "visible.py").write_text("VISIBLE_MARKER = True\n", encoding="utf-8")
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "ignored.py").write_text("IGNORED_GENERATED = True\n", encoding="utf-8")
    (tmp_path / "local.sqlite").write_text("IGNORED_DATABASE", encoding="utf-8")
    private = tmp_path / "docs" / "private"
    private.mkdir(parents=True)
    (private / "secret.md").write_text("IGNORED_PRIVATE_DOC", encoding="utf-8")
    (tmp_path / "TODO.md").write_text("IGNORED_PRIORITY_NOTE", encoding="utf-8")

    report = build_super_report(tmp_path, "Modifica ignored.py e secret.md")

    assert "VISIBLE_MARKER" in report
    assert "IGNORED_GENERATED" not in report
    assert "IGNORED_DATABASE" not in report
    assert "IGNORED_PRIVATE_DOC" not in report
    assert "IGNORED_PRIORITY_NOTE" not in report
    assert "generated/" not in report
    assert "local.sqlite" not in report
    assert "docs/private" not in report
    assert "`TODO.md`" not in report
    assert ".bridgai/ignore" not in report


def test_project_ignore_does_not_replace_sensitive_path_rules(tmp_path: Path) -> None:
    config = tmp_path / ".bridgai"
    config.mkdir()
    (config / "ignore").write_text("visible.py\n", encoding="utf-8")
    (tmp_path / "visible.py").write_text("VISIBLE = True\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET_STILL_BLOCKED=1\n", encoding="utf-8")

    report = build_super_report(tmp_path)

    assert "VISIBLE = True" not in report
    assert "SECRET_STILL_BLOCKED" not in report


def test_report_includes_global_and_project_prompts(tmp_path: Path, monkeypatch) -> None:
    from local_ai_bridge.core.project_prompts import save_project_prompt
    from local_ai_bridge.core.settings import AppSettings
    from local_ai_bridge.services import reporting

    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    save_project_prompt(tmp_path, "Keep adapters separate.")

    class FakeStore:
        def load(self):
            return AppSettings(global_prompt="Use English and type hints.")

    monkeypatch.setattr(reporting, "SettingsStore", FakeStore)
    report = build_super_report(tmp_path, "Update app")
    assert "## 1.1 Istruzioni personalizzate" in report
    assert "### Prompt globale" in report
    assert "Use English and type hints." in report
    assert "### Prompt del progetto" in report
    assert "Keep adapters separate." in report


def test_report_can_disable_custom_prompts(tmp_path: Path, monkeypatch) -> None:
    from local_ai_bridge.core.project_prompts import save_project_prompt
    from local_ai_bridge.core.settings import AppSettings
    from local_ai_bridge.services import reporting

    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    save_project_prompt(tmp_path, "DO_NOT_INCLUDE_PROJECT")

    class FakeStore:
        def load(self):
            return AppSettings(
                include_custom_prompts=False,
                global_prompt="DO_NOT_INCLUDE_GLOBAL",
            )

    monkeypatch.setattr(reporting, "SettingsStore", FakeStore)
    report = build_super_report(tmp_path, "Update app")
    assert "Inclusione disabilitata nelle impostazioni." in report
    assert "DO_NOT_INCLUDE_PROJECT" not in report
    assert "DO_NOT_INCLUDE_GLOBAL" not in report


def test_report_can_include_composed_prompt_preset(tmp_path: Path) -> None:
    from local_ai_bridge.core.prompt_presets import compose_task_with_preset

    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    task = compose_task_with_preset("Correggi il problema.", "safe_refactor")
    report = build_super_report(tmp_path, task)
    assert "Correggi il problema." in report
    assert "Preset selezionato: Refactor sicuro" in report
    assert "senza sostituirlo" in report
