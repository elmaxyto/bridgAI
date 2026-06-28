from __future__ import annotations

import shutil
import subprocess
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
    assert "Generatore report:** `BridgAI 1.1.0`" in report


def test_download_parse_and_export(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a=1", encoding="utf-8")
    requested = parse_download_requests("test\n#scarica src/a.py, README.md")
    assert requested == ["src/a.py", "README.md"]
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    destination = tmp_path / "out.zip"
    create_export_zip(tmp_path, requested, destination)
    with zipfile.ZipFile(destination) as zf:
        assert sorted(zf.namelist()) == ["README.md", "bridgai-project.json", "src/a.py"]



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
        assert zf.namelist() == ["bridgai-project.json", "src/demo/__init__.py"]

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


def test_scanner_excludes_generated_gradle_and_dependency_trees(
    tmp_path: Path, monkeypatch
) -> None:
    from local_ai_bridge.services import project_scanner

    source = tmp_path / "src"
    source.mkdir()
    (source / "main.ts").write_text(
        "export function startRoadtrip() { return true; }\n",
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text(
        '{"name":"roadtrip","version":"1.0.0"}',
        encoding="utf-8",
    )

    gradle_cache = tmp_path / ".gradle-build-aab"
    nested = gradle_cache
    for index in range(12):
        nested = nested / f"cache-{index}"
        nested.mkdir(parents=True)
        (nested / "generated.ts").write_text(
            "export function GENERATED_NOISE() {}\n",
            encoding="utf-8",
        )
    dependencies = tmp_path / "node_modules" / "example"
    dependencies.mkdir(parents=True)
    (dependencies / "index.js").write_text(
        "function DEPENDENCY_NOISE() {}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(project_scanner, "MAX_DISCOVERED_DIRS", 4)
    report = build_super_report(tmp_path)

    assert "startRoadtrip" in report
    assert ".gradle-build-aab" not in report
    assert "node_modules" not in report
    assert "GENERATED_NOISE" not in report
    assert "DEPENDENCY_NOISE" not in report
    assert "Scansione filesystem interrotta" not in report
    assert "Sottoalberi tecnici esclusi:** 2" in report


def test_scanner_keeps_priority_source_files_when_discovery_is_truncated(
    tmp_path: Path, monkeypatch
) -> None:
    from local_ai_bridge.services import project_scanner

    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text(
        "def preserved_entrypoint():\n    return True\n",
        encoding="utf-8",
    )
    noisy = tmp_path / "aaa-unclassified-cache"
    noisy.mkdir()
    (noisy / "payload.py").write_text("VALUE = 1\n", encoding="utf-8")

    monkeypatch.setattr(project_scanner, "MAX_DISCOVERED_DIRS", 2)
    result = project_scanner.scan_project(tmp_path)

    assert result.scanned_files == 1
    assert "src/main.py" in result.summaries
    assert "preserved_entrypoint" in result.summaries
    assert any("Conservati 1 file già individuati" in item for item in result.diagnostics)


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

    assert "`visible.py`" in report
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


def test_scanner_excludes_noise_from_common_development_ecosystems(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.kt").write_text(
        "fun main() { println(\"clean-source\") }\n",
        encoding="utf-8",
    )
    (source / "ui.tsx").write_text(
        "export function CleanUi() { return null; }\n",
        encoding="utf-8",
    )
    (tmp_path / "build.gradle.kts").write_text(
        'plugins { kotlin("jvm") version "2.0.0" }\n',
        encoding="utf-8",
    )

    noise = {
        ".venv/lib/site-packages/pkg/module.py": "VENV_NOISE = True\n",
        "node_modules/pkg/index.js": "const NODE_NOISE = true;\n",
        ".gradle-build-release/caches/generated.kt": "val GRADLE_NOISE = true\n",
        "target/generated/source.rs": "const TARGET_NOISE: bool = true;\n",
        "dist/app.min.js": "const DIST_NOISE=true;\n",
        "coverage/lcov.info": "COVERAGE_NOISE\n",
        ".yarn/cache/package.zip": "YARN_NOISE\n",
        "Pods/Library/source.m": "PODS_NOISE\n",
        "tmp/debug.log": "TEMP_NOISE\n",
    }
    for relative, content in noise.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    report = build_super_report(tmp_path)

    assert "clean-source" in report
    assert "CleanUi" in report
    assert "build.gradle.kts" in report
    for marker in (
        "VENV_NOISE", "NODE_NOISE", "GRADLE_NOISE", "TARGET_NOISE",
        "DIST_NOISE", "COVERAGE_NOISE", "YARN_NOISE", "PODS_NOISE",
        "TEMP_NOISE",
    ):
        assert marker not in report
    assert "Sottoalberi tecnici esclusi:" in report
    assert "Dettaglio esclusioni:" in report


def test_scanner_detects_renamed_python_virtual_environment(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "app.py").write_text("def app_marker():\n    return True\n", encoding="utf-8")

    runtime = tmp_path / "python-runtime-311"
    runtime.mkdir()
    (runtime / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    (runtime / "hidden.py").write_text("RENAMED_VENV_NOISE = True\n", encoding="utf-8")

    report = build_super_report(tmp_path)

    assert "app_marker" in report
    assert "RENAMED_VENV_NOISE" not in report
    assert "ambiente virtuale rilevato" in report


def test_scanner_excludes_compiled_temporary_and_generated_files_inside_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "app.ts").write_text(
        "export function retainedSource() { return true; }\n",
        encoding="utf-8",
    )
    (source / "app.min.js").write_text("const MINIFIED_NOISE=true;", encoding="utf-8")
    (source / "app.js.map").write_text('{"MAP_NOISE":true}', encoding="utf-8")
    (source / "cache.pyc").write_bytes(b"PYC_NOISE")
    (source / "debug.log").write_text("LOG_NOISE", encoding="utf-8")
    (source / "model_pb2.py").write_text("PROTO_NOISE = True\n", encoding="utf-8")

    report = build_super_report(tmp_path)

    assert "retainedSource" in report
    for name in ("app.min.js", "app.js.map", "cache.pyc", "debug.log", "model_pb2.py"):
        assert name not in report
    for marker in ("MINIFIED_NOISE", "MAP_NOISE", "PYC_NOISE", "LOG_NOISE", "PROTO_NOISE"):
        assert marker not in report
    assert "File tecnici esclusi:" in report


def test_non_code_assets_do_not_consume_relevant_file_limit(tmp_path: Path, monkeypatch) -> None:
    from local_ai_bridge.services import project_scanner

    assets = tmp_path / "assets"
    assets.mkdir()
    for index in range(30):
        (assets / f"image-{index:02d}.png").write_bytes(b"not-a-real-png")

    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text(
        "def source_survives_asset_noise():\n    return True\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(project_scanner, "MAX_DISCOVERED_FILES", 1)
    result = project_scanner.scan_project(tmp_path)

    assert "source_survives_asset_noise" in result.summaries
    assert result.scanned_files == 1
    assert not any("limite massimo di file" in item for item in result.diagnostics)


def test_dependency_lockfiles_are_compacted_instead_of_expanded(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name":"demo","version":"1.0.0"}',
        encoding="utf-8",
    )
    marker = "LOCKFILE_CONTENT_THAT_MUST_NOT_BE_EXPANDED"
    (tmp_path / "package-lock.json").write_text(
        '{"name":"demo","packages":{"node_modules/example":{"marker":"'
        + marker
        + '"}}}',
        encoding="utf-8",
    )

    report = build_super_report(tmp_path)

    assert "package-lock.json" in report
    assert "contenuto non espanso nel report" in report
    assert marker not in report


def test_scanner_keeps_legitimate_cache_module_inside_source(tmp_path: Path) -> None:
    source_cache = tmp_path / "src" / "cache"
    source_cache.mkdir(parents=True)
    (source_cache / "manager.py").write_text(
        "def build_cache_key():\n    return 'kept'\n",
        encoding="utf-8",
    )
    runtime_cache = tmp_path / "cache"
    runtime_cache.mkdir()
    (runtime_cache / "payload.py").write_text(
        "def root_cache_noise():\n    return 'ignored'\n",
        encoding="utf-8",
    )

    report = build_super_report(tmp_path)

    assert "build_cache_key" in report
    assert "src/cache/manager.py" in report
    assert "root_cache_noise" not in report


def test_git_manifest_respects_repository_ignore_rules(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        return

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(
        "custom-output/\n*.trace\n",
        encoding="utf-8",
    )
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text(
        "def git_visible_source():\n    return True\n",
        encoding="utf-8",
    )
    ignored = tmp_path / "custom-output"
    ignored.mkdir()
    (ignored / "generated.py").write_text(
        "def gitignored_noise():\n    return True\n",
        encoding="utf-8",
    )
    (tmp_path / "debug.trace").write_text("TRACE_NOISE", encoding="utf-8")

    report = build_super_report(tmp_path)

    assert "Modalità scansione:** manifest Git + filtri BridgAI" in report
    assert "git_visible_source" in report
    tree_section = report.split("## 10. Struttura reale del progetto", 1)[1].split(
        "## 11. Firme, dipendenze e configurazioni principali", 1
    )[0]
    assert "custom-output/" not in tree_section
    assert "debug.trace" not in tree_section
    assert "gitignored_noise" not in report
    assert "TRACE_NOISE" not in report


def test_project_ignore_can_explicitly_reinclude_default_exclusions(tmp_path: Path) -> None:
    config = tmp_path / ".bridgai"
    config.mkdir()
    (config / "ignore").write_text(
        "!vendor/\n"
        "!src/model_pb2.py\n",
        encoding="utf-8",
    )
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "local_library.py").write_text(
        "def explicitly_included_vendor_code():\n    return True\n",
        encoding="utf-8",
    )
    source = tmp_path / "src"
    source.mkdir()
    (source / "model_pb2.py").write_text(
        "def explicitly_included_generated_code():\n    return True\n",
        encoding="utf-8",
    )

    report = build_super_report(tmp_path)

    assert "explicitly_included_vendor_code" in report
    assert "explicitly_included_generated_code" in report


def test_git_discovery_timeout_falls_back_to_filtered_filesystem(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from local_ai_bridge.services import project_scanner

    (tmp_path / ".git").mkdir()
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.ts").write_text(
        "export function fallbackSourceMarker() { return true; }\n",
        encoding="utf-8",
    )
    dependencies = tmp_path / "node_modules" / "pkg"
    dependencies.mkdir(parents=True)
    (dependencies / "index.js").write_text(
        "export const FALLBACK_DEPENDENCY_NOISE = true;\n",
        encoding="utf-8",
    )

    def timeout_manifest(*args, **kwargs):
        raise project_scanner.GitDiscoveryBudgetExceeded(
            "limite di tempo della scansione Git raggiunto"
        )

    monkeypatch.setattr(project_scanner, "git_manifest", timeout_manifest)

    result = project_scanner.scan_project(tmp_path, time_budget=6.0)

    assert result.discovery_mode == "filesystem filtrato (fallback Git)"
    assert result.scanned_files == 1
    assert "fallbackSourceMarker" in result.summaries
    assert "FALLBACK_DEPENDENCY_NOISE" not in result.summaries
    assert any("fallback sul filesystem filtrato" in item for item in result.diagnostics)
    assert not any("Conservati 0 file" in item for item in result.diagnostics)


def test_task_candidates_fall_back_when_git_discovery_times_out(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from local_ai_bridge.services import project_scanner

    (tmp_path / ".git").mkdir()
    source = tmp_path / "src"
    source.mkdir()
    (source / "booking_service.ts").write_text(
        "export function calculateBookingTotal() { return 42; }\n",
        encoding="utf-8",
    )

    def timeout_manifest(*args, **kwargs):
        raise project_scanner.GitDiscoveryBudgetExceeded(
            "limite di tempo della scansione Git raggiunto"
        )

    monkeypatch.setattr(project_scanner, "git_manifest", timeout_manifest)

    candidates = project_scanner.rank_task_candidates(
        tmp_path,
        "Correggi calculateBookingTotal nel booking service",
    )

    assert "src/booking_service.ts" in candidates


def test_git_manifest_prefilters_dependency_paths_before_filesystem_checks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import time
    from types import SimpleNamespace

    from local_ai_bridge.services import project_scanner_git
    from local_ai_bridge.services.project_scanner_policy import load_project_ignore

    (tmp_path / ".git").mkdir()
    source = tmp_path / "src"
    source.mkdir()
    source_file = source / "main.py"
    source_file.write_text("VALUE = 1\n", encoding="utf-8")

    dependencies = tmp_path / "node_modules" / "pkg"
    dependencies.mkdir(parents=True)
    dependency_file = dependencies / "index.js"
    dependency_file.write_text("DEPENDENCY = true;\n", encoding="utf-8")

    stdout = b"node_modules/pkg/index.js\0src/main.py\0"
    monkeypatch.setattr(
        project_scanner_git.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=stdout),
    )

    checked_paths: list[str] = []

    def record_check(path: Path) -> bool:
        checked_paths.append(path.relative_to(tmp_path).as_posix())
        return False

    monkeypatch.setattr(
        project_scanner_git,
        "_is_path_link_or_reparse",
        record_check,
    )

    manifest = project_scanner_git.git_manifest(
        tmp_path,
        time.monotonic() + 5.0,
        load_project_ignore(tmp_path),
    )

    assert manifest == [(source_file, "src/main.py")]
    assert checked_paths == ["src/main.py"]


def test_scanner_hides_local_android_credentials_and_machine_configuration(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.ts").write_text(
        "export function visibleProjectCode() { return true; }\n",
        encoding="utf-8",
    )
    android = tmp_path / "android-build"
    android.mkdir()
    (android / "android.keystore").write_bytes(b"PRIVATE_KEY_MATERIAL")
    (android / "local.properties").write_text(
        "sdk.dir=C:\\\\private\\\\Android\\\\Sdk\n",
        encoding="utf-8",
    )

    report = build_super_report(tmp_path)

    assert "visibleProjectCode" in report
    assert "android.keystore" not in report
    assert "local.properties" not in report
    assert "PRIVATE_KEY_MATERIAL" not in report
    assert "C:\\\\private\\\\Android\\\\Sdk" not in report


def test_scanner_excludes_scratch_and_generated_diagnostic_outputs(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.ts").write_text(
        "export function productionEntry() { return true; }\n",
        encoding="utf-8",
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "prototype.ts").write_text(
        "export function SCRATCH_NOISE() { return false; }\n",
        encoding="utf-8",
    )
    (tmp_path / "final_report.txt").write_text(
        "HISTORICAL_AI_OUTPUT",
        encoding="utf-8",
    )
    (tmp_path / "tsc_output_2.txt").write_text(
        "HISTORICAL_TSC_OUTPUT",
        encoding="utf-8",
    )

    report = build_super_report(tmp_path)

    assert "productionEntry" in report
    assert "SCRATCH_NOISE" not in report
    assert "HISTORICAL_AI_OUTPUT" not in report
    assert "HISTORICAL_TSC_OUTPUT" not in report
    assert "materiale sperimentale" in report
    assert "output diagnostici generati" in report


def test_summary_selection_balances_project_areas_and_reports_omissions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from local_ai_bridge.services import project_scanner
    from local_ai_bridge.services import project_scanner_summary

    (tmp_path / "package.json").write_text(
        '{"name":"balanced-demo","version":"1.0.0"}',
        encoding="utf-8",
    )
    for area, count in (("components", 12), ("services", 6), ("hooks", 6)):
        directory = tmp_path / "src" / area
        directory.mkdir(parents=True)
        for index in range(count):
            (directory / f"{area}_{index}.ts").write_text(
                f"export function {area}_{index}() {{ return {index}; }}\n",
                encoding="utf-8",
            )
    (tmp_path / "src" / "main.ts").write_text(
        "export function mainEntry() { return true; }\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(project_scanner, "MAX_SUMMARY_FILES", 8)
    monkeypatch.setattr(project_scanner_summary, "LARGE_CODE_RESERVE", 2)

    result = project_scanner.scan_project(tmp_path)

    assert result.scanned_files == 8
    assert result.omitted_files > 0
    assert "src/main.ts" in result.summaries
    assert "src/components/" in result.summaries
    assert "src/services/" in result.summaries
    assert "src/hooks/" in result.summaries
    assert any("Contesto sintetico:" in item for item in result.diagnostics)


def test_git_manifest_tree_compacts_media_only_subtrees(tmp_path: Path) -> None:
    from local_ai_bridge.services.project_scanner_git import tree_from_manifest

    files = [
        (tmp_path / f"public/assets/image-{index}.png", f"public/assets/image-{index}.png")
        for index in range(5)
    ]
    files.append((tmp_path / "src/main.ts", "src/main.ts"))

    tree, truncated = tree_from_manifest(
        tmp_path,
        files,
        max_entries=100,
        max_depth=20,
    )

    assert not truncated
    assert "public/ [5 file multimediali]" in tree
    assert "image-0.png" not in tree
    assert "src/" in tree
    assert "main.ts" in tree


def test_git_status_hides_technical_paths_but_keeps_project_changes(tmp_path: Path) -> None:
    from local_ai_bridge.services.reporting_git import compact_git_status

    output = (
        "## main...origin/main\n"
        " M src/app.ts\n"
        " M node_modules/example/index.js\n"
        " M .gradle/cache.bin\n"
    )

    compact = compact_git_status(tmp_path, output)

    assert "src/app.ts" in compact
    assert "node_modules/example/index.js" not in compact
    assert ".gradle/cache.bin" not in compact
    assert "2 modifiche in percorsi tecnici omesse" in compact
    assert "dipendenze installate: 1" in compact
    assert "cache strumenti: 1" in compact


def test_typescript_diagnostics_do_not_claim_python_validation(tmp_path: Path) -> None:
    (tmp_path / "main.ts").write_text(
        "export function start() { return true; }\n",
        encoding="utf-8",
    )

    report = build_super_report(tmp_path)

    assert "Parsing AST Python: nessun file Python incluso nel contesto sintetico." in report
    assert "JavaScript/TypeScript: firme estratte euristicamente da 1 file" in report
    assert "sintassi non validata durante il report" in report


def test_report_text_file_operations_mode_is_explicit_and_optional(tmp_path: Path) -> None:
    from local_ai_bridge.core.settings import AppSettings

    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    standard = build_super_report(
        tmp_path,
        "Aggiorna app",
        settings=AppSettings(textual_file_operations_mode=False),
    )
    structured = build_super_report(
        tmp_path,
        "Aggiorna app",
        settings=AppSettings(textual_file_operations_mode=True),
    )

    assert "**FORMATO FILE RICHIESTI — ZIP**" in standard
    assert "**FORMATO MODIFICHE — ZIP**" in standard
    assert "SEARCH/REPLACE" not in standard
    assert "**FORMATO MODIFICHE — File Markdown di aggiornamento**" not in standard
    assert "**FORMATO MODIFICHE — File Markdown di aggiornamento**" in structured
    assert "OPERATION: REPLACE" in structured
    assert "OPERATION: CREATE" in structured
    assert "OPERATION: DELETE" in structured
    assert "FINAL_NEWLINE: YES" in structured
    assert "FINAL_NEWLINE: NO" in structured
    assert "OPERATION: CREATE oppure REPLACE" not in structured
    assert "FINAL_NEWLINE: YES oppure NO" not in structured
    assert "Non racchiudere l'intera risposta" in structured
    assert "non produrre ZIP, non usare SEARCH/REPLACE" in structured
    assert "`bridgai-update.md`" in structured
    assert "crea un singolo file scaricabile" in structured
    assert "usa il copia-incolla soltanto" in structured
    assert "**FORMATO MODIFICHE — ZIP**" not in structured


def test_empty_workspace_uses_create_operations_when_text_mode_is_active(tmp_path: Path) -> None:
    from local_ai_bridge.core.settings import AppSettings

    report = build_super_report(
        tmp_path,
        "Crea il progetto",
        settings=AppSettings(textual_file_operations_mode=True),
    )

    assert "un unico file `bridgai-update.md`" in report
    assert "operazioni `CREATE` complete" in report
    assert "Non usare ZIP né `#scarica`" in report
    assert "**Applica ZIP**" not in report


def test_report_combines_markdown_download_with_text_or_zip_updates(tmp_path: Path) -> None:
    from local_ai_bridge.core.settings import AppSettings

    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    markdown_zip = build_super_report(
        tmp_path,
        "Aggiorna app",
        settings=AppSettings(
            markdown_exchange_mode=True,
            textual_file_operations_mode=False,
        ),
    )
    markdown_text = build_super_report(
        tmp_path,
        "Aggiorna app",
        settings=AppSettings(
            markdown_exchange_mode=True,
            textual_file_operations_mode=True,
        ),
    )

    assert "**FORMATO FILE RICHIESTI — Markdown**" in markdown_zip
    assert "**FORMATO MODIFICHE — ZIP**" in markdown_zip
    assert "**FORMATO FILE RICHIESTI — Markdown**" in markdown_text
    assert "**FORMATO MODIFICHE — File Markdown di aggiornamento**" in markdown_text
    assert "`bridgai-update.md`" in markdown_text


def test_gemini_preference_selects_zip_requests_and_markdown_updates(
    tmp_path: Path,
) -> None:
    from local_ai_bridge.core.settings import AppSettings, SettingsStore

    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    store = SettingsStore()
    store.path = tmp_path / "settings.json"
    store.save(AppSettings(preferred_web_ai="gemini"))

    report = build_super_report(
        tmp_path,
        "Aggiorna app",
        settings=store.load(),
    )

    assert "**FORMATO FILE RICHIESTI — ZIP**" in report
    assert "**FORMATO MODIFICHE — File Markdown di aggiornamento**" in report
