from __future__ import annotations

import zipfile
from pathlib import Path

from local_ai_bridge.services.exporting import create_export_zip
from local_ai_bridge.services.reporting import build_super_report


def test_summary_selection_deduplicates_paths_stably(tmp_path: Path) -> None:
    from local_ai_bridge.services.project_scanner_summary import select_summary_files

    target = tmp_path / "src" / "app.ts"
    target.parent.mkdir()
    target.write_text("export const app = true;\n", encoding="utf-8")
    selected, omitted = select_summary_files(
        [(target, "src/app.ts"), (target, "./src/app.ts"), (target, "src\\app.ts")],
        limit=10,
    )

    assert selected == [(target, "src/app.ts")]
    assert omitted == 0


def test_adaptive_summary_limit_responds_to_task_specificity() -> None:
    from local_ai_bridge.services.project_scanner_summary import adaptive_summary_limit

    assert adaptive_summary_limit(500, "", 240) == 180
    assert adaptive_summary_limit(500, "Correggi login", 240) == 120
    assert adaptive_summary_limit(
        500,
        "Correggi il flusso login Firebase e aggiorna i test relativi",
        240,
    ) == 100
    assert adaptive_summary_limit(500, "Esegui una analisi completa di tutti i file", 240) == 240


def test_javascript_summary_reports_imports_exports_and_declarations() -> None:
    from local_ai_bridge.services.project_scanner_helpers import summarize_js

    summary = summarize_js(
        "import { initializeApp } from 'firebase/app';\n"
        "export const firebaseApp = initializeApp({});\n"
        "export type AppMode = 'demo' | 'live';\n"
    )

    assert "firebase/app" in summary
    assert "firebaseApp" in summary
    assert "AppMode" in summary
    assert "Nessuna firma rilevata" not in summary


def test_document_summaries_are_compact_and_remove_license_boilerplate() -> None:
    from local_ai_bridge.services.project_scanner_helpers import summarize_generic

    markdown = summarize_generic(
        Path("README.md"),
        "# Demo\n\nTESTO_IMPORTANTE\n\n## Installazione\n" + "dettaglio\n" * 50,
    )
    html = summarize_generic(
        Path("index.html"),
        '<html><head><title>Demo App</title><meta name="description" content="Descrizione breve"></head><body><h1>Benvenuto</h1></body></html>',
    )
    gradle = summarize_generic(
        Path("build.gradle"),
        "/* Copyright 2019 Google Inc. Licensed under the Apache License */\nplugins { id 'com.android.application' }\n",
    )

    assert "TESTO_IMPORTANTE" in markdown
    assert "Installazione" in markdown
    assert len(markdown.splitlines()) <= 3
    assert "Demo App" in html
    assert "Descrizione breve" in html
    assert "Copyright" not in gradle
    assert "plugins" in gradle


def test_non_expanded_indexed_file_remains_exportable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from local_ai_bridge.services import project_scanner

    source = tmp_path / "src"
    source.mkdir()
    relatives: list[str] = []
    for index in range(6):
        relative = f"src/module_{index}.ts"
        relatives.append(relative)
        (tmp_path / relative).write_text(
            f"export const module_{index} = {index};\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(project_scanner, "MAX_SUMMARY_FILES", 2)
    result = project_scanner.scan_project(tmp_path)
    omitted = next(relative for relative in relatives if f"### `{relative}`" not in result.summaries)

    destination = tmp_path / "context.zip"
    create_export_zip(tmp_path, [omitted], destination)

    assert result.omitted_files == 4
    with zipfile.ZipFile(destination) as archive:
        assert omitted in archive.namelist()


def test_report_explains_index_and_download_coverage(tmp_path: Path, monkeypatch) -> None:
    from local_ai_bridge.services import project_scanner

    source = tmp_path / "src"
    source.mkdir()
    for index in range(4):
        (source / f"part_{index}.ts").write_text(
            f"export const part_{index} = {index};\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(project_scanner, "MAX_SUMMARY_FILES", 2)

    report = build_super_report(tmp_path)

    assert "tutti i file indicizzati restano richiedibili" in report
    assert "soltanto i sottoalberi composti esclusivamente da file multimediali" in report
    assert "Scansione: completata." in report
    assert "Scansione: completata con avvisi." not in report
