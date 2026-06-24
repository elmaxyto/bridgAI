from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path

from local_ai_bridge.services.operational_execution_policy import (
    MissionExecutionError,
    ValidatedExecutionPaths,
)
from local_ai_bridge.services.operational_missions import OperationalMission


MAX_CSV_FILES = 100
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_TOTAL_ROWS = 1_000_000
MAX_COLUMNS = 250
_SAMPLE_BYTES = 64 * 1024
_DELIMITERS = ",;\t|"


@dataclass(frozen=True, slots=True)
class CsvMergeProducts:
    merged_csv: bytes
    summary_json: bytes
    summary_text: bytes


@dataclass(frozen=True, slots=True)
class _CsvSource:
    declared_path: str
    resolved_path: Path
    relative_name: str


def build_csv_merge_products(
    mission: OperationalMission,
    execution_id: str,
    procedure_id: str,
    paths: ValidatedExecutionPaths,
    generated_at: str,
) -> CsvMergeProducts:
    sources = _collect_csv_sources(paths)
    if not sources:
        raise MissionExecutionError("no CSV files were found in the authorized inputs")

    total_bytes = sum(source.resolved_path.stat().st_size for source in sources)
    if total_bytes > MAX_TOTAL_BYTES:
        raise MissionExecutionError(
            f"CSV inputs exceed the {MAX_TOTAL_BYTES // (1024 * 1024)} MiB safety limit"
        )

    union_headers: list[str] = []
    canonical_headers: dict[str, str] = {}
    parsed_sources: list[dict[str, object]] = []
    merged_rows: list[tuple[dict[str, str], str]] = []
    total_rows = 0

    for source in sources:
        text, encoding = _read_csv_text(source.resolved_path)
        delimiter = _detect_delimiter(text)
        headers, rows = _parse_csv_rows(text, delimiter, source.relative_name)
        total_rows += len(rows)
        if total_rows > MAX_TOTAL_ROWS:
            raise MissionExecutionError(
                f"CSV inputs exceed the {MAX_TOTAL_ROWS} row safety limit"
            )
        for header in headers:
            key = header.casefold()
            if key not in canonical_headers:
                canonical_headers[key] = header
                union_headers.append(header)
                if len(union_headers) > MAX_COLUMNS:
                    raise MissionExecutionError(
                        f"CSV inputs exceed the {MAX_COLUMNS} column safety limit"
                    )
        parsed_sources.append(
            {
                "declared_path": source.declared_path,
                "resolved_path": str(source.resolved_path),
                "relative_name": source.relative_name,
                "encoding": encoding,
                "delimiter": delimiter,
                "columns": headers,
                "row_count": len(rows),
                "size_bytes": source.resolved_path.stat().st_size,
            }
        )
        for row in rows:
            normalized: dict[str, str] = {}
            for header, value in row.items():
                normalized[canonical_headers[header.casefold()]] = value
            merged_rows.append((normalized, source.relative_name))

    source_column = _unique_source_column(union_headers)
    union_headers.append(source_column)

    merged_stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        merged_stream,
        fieldnames=union_headers,
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    for row, source_name in merged_rows:
        output_row = {header: row.get(header, "") for header in union_headers}
        output_row[source_column] = source_name
        writer.writerow(output_row)
    merged_bytes = ("\ufeff" + merged_stream.getvalue()).encode("utf-8")

    summary = {
        "schema_version": 1,
        "mission_id": mission.mission_id,
        "execution_id": execution_id,
        "procedure_id": procedure_id,
        "generated_at": generated_at,
        "request": mission.original_request,
        "file_count": len(sources),
        "row_count": total_rows,
        "column_count": len(union_headers),
        "columns": union_headers,
        "source_column": source_column,
        "total_input_bytes": total_bytes,
        "sources": parsed_sources,
        "guarantees": {
            "originals_modified": False,
            "network_used": False,
            "external_processes_used": False,
            "output_overwritten": False,
        },
    }
    summary_json = json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8")
    summary_text = _summary_text(summary).encode("utf-8")
    return CsvMergeProducts(merged_bytes, summary_json, summary_text)


def _collect_csv_sources(paths: ValidatedExecutionPaths) -> tuple[_CsvSource, ...]:
    sources: list[_CsvSource] = []
    seen: set[str] = set()
    for declared, resolved in paths.inputs:
        candidates: list[tuple[Path, str]]
        if resolved.is_file():
            if resolved.suffix.casefold() != ".csv":
                raise MissionExecutionError(f"authorized file is not CSV: {declared}")
            candidates = [(resolved, resolved.name)]
        else:
            candidates = list(_walk_csv_directory(resolved))
        for candidate, relative_name in candidates:
            key = os.path.normcase(str(candidate))
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                _CsvSource(
                    declared_path=declared,
                    resolved_path=candidate,
                    relative_name=relative_name,
                )
            )
            if len(sources) > MAX_CSV_FILES:
                raise MissionExecutionError(
                    f"more than {MAX_CSV_FILES} CSV files were selected"
                )
    sources.sort(key=lambda item: (item.relative_name.casefold(), str(item.resolved_path)))
    return _with_unique_source_names(tuple(sources))


def _with_unique_source_names(sources: tuple[_CsvSource, ...]) -> tuple[_CsvSource, ...]:
    used: set[str] = set()
    normalized: list[_CsvSource] = []
    for source in sources:
        candidate = source.relative_name
        if candidate.casefold() in used:
            candidate = f"{source.resolved_path.parent.name}/{source.resolved_path.name}"
        index = 2
        base = candidate
        while candidate.casefold() in used:
            candidate = f"{base} ({index})"
            index += 1
        used.add(candidate.casefold())
        normalized.append(
            _CsvSource(
                declared_path=source.declared_path,
                resolved_path=source.resolved_path,
                relative_name=candidate,
            )
        )
    return tuple(normalized)


def _walk_csv_directory(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name.casefold())
        except OSError as exc:
            raise MissionExecutionError(f"cannot read input directory: {current}") from exc
        directories: list[Path] = []
        for entry in entries:
            path = Path(entry.path)
            if entry.is_symlink():
                raise MissionExecutionError(f"symbolic links are not allowed inside CSV inputs: {path}")
            if entry.is_dir(follow_symlinks=False):
                directories.append(path)
            elif entry.is_file(follow_symlinks=False) and path.suffix.casefold() == ".csv":
                yield path.resolve(strict=True), path.relative_to(root).as_posix()
        stack.extend(reversed(directories))


def _read_csv_text(path: Path) -> tuple[str, str]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise MissionExecutionError(f"cannot read CSV input: {path}") from exc
    if b"\x00" in data:
        raise MissionExecutionError(f"CSV input appears to be binary: {path}")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise MissionExecutionError(f"CSV encoding is unsupported: {path}")


def _detect_delimiter(text: str) -> str:
    sample = text[:_SAMPLE_BYTES]
    try:
        return csv.Sniffer().sniff(sample, delimiters=_DELIMITERS).delimiter
    except csv.Error:
        counts = {delimiter: sample.count(delimiter) for delimiter in _DELIMITERS}
        return max(counts, key=counts.get) if any(counts.values()) else ","


def _parse_csv_rows(
    text: str,
    delimiter: str,
    display_name: str,
) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        raw_headers = next(reader)
    except StopIteration as exc:
        raise MissionExecutionError(f"CSV file is empty: {display_name}") from exc
    headers = [header.strip() for header in raw_headers]
    if not headers or any(not header for header in headers):
        raise MissionExecutionError(f"CSV has an empty column name: {display_name}")
    keys = [header.casefold() for header in headers]
    if len(set(keys)) != len(keys):
        raise MissionExecutionError(f"CSV has duplicate column names: {display_name}")
    if len(headers) > MAX_COLUMNS:
        raise MissionExecutionError(
            f"CSV has more than {MAX_COLUMNS} columns: {display_name}"
        )

    rows: list[dict[str, str]] = []
    for row_number, values in enumerate(reader, start=2):
        if not values or all(not value.strip() for value in values):
            continue
        if len(values) > len(headers):
            raise MissionExecutionError(
                f"CSV row {row_number} has extra values: {display_name}"
            )
        padded = values + [""] * (len(headers) - len(values))
        rows.append(dict(zip(headers, padded, strict=True)))
    return headers, rows


def _unique_source_column(headers: list[str]) -> str:
    existing = {header.casefold() for header in headers}
    candidate = "BridgAI source file"
    index = 2
    while candidate.casefold() in existing:
        candidate = f"BridgAI source file {index}"
        index += 1
    return candidate


def _summary_text(summary: dict[str, object]) -> str:
    lines = [
        "Riepilogo unione CSV BridgAI / BridgAI CSV merge summary",
        "",
        f"File uniti / Files merged: {summary['file_count']}",
        f"Righe scritte / Rows written: {summary['row_count']}",
        f"Colonne scritte / Columns written: {summary['column_count']}",
        f"Colonna sorgente / Source column: {summary['source_column']}",
        "",
        "Sorgenti / Sources:",
    ]
    for source in summary["sources"]:
        lines.append(
            f"- {source['relative_name']}: {source['row_count']} righe/rows, "
            f"delimitatore/delimiter {source['delimiter']!r}, "
            f"codifica/encoding {source['encoding']}"
        )
    lines.extend(
        [
            "",
            "Sicurezza / Safety:",
            "- I file originali non sono stati modificati / Original files were not modified.",
            "- I file esistenti non sono stati sovrascritti / Existing files were not overwritten.",
            "- Non sono stati usati rete o programmi esterni / No network or external programs were used.",
            "",
        ]
    )
    return "\n".join(lines)
