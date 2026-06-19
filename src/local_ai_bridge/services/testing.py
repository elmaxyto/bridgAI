from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from local_ai_bridge.core.models import TestResult


MAX_OUTPUT = 30_000
_PYTHON_PROJECT_DIRS = ("src", "tests")
_PYTHON_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "backups",
    "build",
    "dist",
    "env",
    "htmlcov",
    "node_modules",
    "venv",
}


_PYTEST_COUNT_PATTERN = re.compile(
    r"(?P<count>\d+)\s+(?P<label>passed|failed|errors?|skipped|xfailed|xpassed|warnings?)\b",
    re.IGNORECASE,
)
_STRUCTURAL_CHECKS = {"Python compileall", "npm build", "TypeScript"}


def _pytest_counts(output: str) -> dict[str, int]:
    counts = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "warnings": 0,
    }
    aliases = {"error": "errors", "warning": "warnings"}
    for match in _PYTEST_COUNT_PATTERN.finditer(output or ""):
        label = match.group("label").lower()
        label = aliases.get(label, label)
        counts[label] = max(counts.get(label, 0), int(match.group("count")))
    return counts


def interpret_test_results(results: list[TestResult]) -> dict[str, object]:
    """Describe test results without turning every failed assertion into a total failure.

    The checks remain authoritative and their raw output is always preserved.  This
    interpretation only explains whether the run completed, partially succeeded,
    or exposed a structural problem that deserves immediate attention.
    """
    passed_checks = sum(result.status == "passed" for result in results)
    failed_checks = sum(result.status in {"failed", "timeout", "error"} for result in results)
    unavailable_checks = sum(result.status == "unavailable" for result in results)
    structural_failures = [
        result.name
        for result in results
        if result.name in _STRUCTURAL_CHECKS
        and result.status in {"failed", "timeout", "error"}
    ]
    pytest_result = next((result for result in results if result.name == "Pytest"), None)
    pytest = _pytest_counts(pytest_result.output if pytest_result else "")
    pytest_not_passed = pytest["failed"] + pytest["errors"]

    if structural_failures:
        names = ", ".join(structural_failures)
        level = "error"
        title = "Controllo strutturale non superato"
        summary = (
            f"{names} non è riuscito. L'aggiornamento resta applicato, ma è consigliato "
            "correggere questo problema prima di considerare concluso o pubblicare il lavoro."
        )
    elif failed_checks:
        level = "warning"
        title = "Verifica parziale: alcuni controlli richiedono attenzione"
        if pytest["passed"] or pytest_not_passed:
            summary = (
                f"Pytest ha completato la suite: {pytest['passed']} test superati e "
                f"{pytest_not_passed} non superati"
            )
            if pytest["skipped"]:
                summary += f", {pytest['skipped']} saltati"
            summary += (
                ". Questo non significa che l'intera applicazione non funzioni: può trattarsi "
                "di una regressione reale oppure di aspettative dei test da aggiornare. "
                "L'aggiornamento non viene annullato automaticamente; esamina i dettagli."
            )
        else:
            summary = (
                f"{failed_checks} controlli non sono stati superati e {passed_checks} sono riusciti. "
                "L'aggiornamento non viene annullato automaticamente; esamina i dettagli prima "
                "di considerare concluso il lavoro."
            )
    elif unavailable_checks:
        level = "warning"
        title = "Verifica incompleta"
        summary = (
            f"{passed_checks} controlli superati e {unavailable_checks} non disponibili. "
            "Non risultano errori nei controlli eseguiti, ma la verifica non è completa."
        )
    else:
        level = "ok"
        title = "Verifiche completate con successo"
        summary = f"Tutti i {passed_checks} controlli eseguiti sono stati superati."

    return {
        "level": level,
        "title": title,
        "summary": summary,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "unavailable_checks": unavailable_checks,
        "structural_failures": structural_failures,
        "pytest": pytest,
        "automatic_rollback": False,
    }


def _has_pytest_suite(workspace: Path) -> bool:
    if (workspace / "tests").is_dir():
        return True
    if any((workspace / name).exists() for name in ("pytest.ini", "conftest.py")):
        return True
    pyproject = workspace / "pyproject.toml"
    if not pyproject.exists():
        return False
    try:
        return "pytest" in pyproject.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _python_compile_targets(workspace: Path) -> list[str]:
    """Return project-owned paths without traversing environments or backups."""
    targets = [name for name in _PYTHON_PROJECT_DIRS if (workspace / name).is_dir()]
    targets.extend(path.name for path in sorted(workspace.glob("*.py")) if path.is_file())

    if targets:
        return targets

    for path in sorted(workspace.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_dir() or path.name.casefold() in _PYTHON_IGNORED_DIRS:
            continue
        if (path / "__init__.py").is_file():
            targets.append(path.name)
    return targets


def _pytest_command(workspace: Path) -> list[str]:
    command = [sys.executable, "-m", "pytest", "-q"]
    if (workspace / "tests").is_dir():
        command.append("tests")
    return command


def _run(name: str, command: list[str], cwd: Path, timeout: int = 120, env: dict[str, str] | None = None) -> TestResult:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            check=False, env=env,
        )
        output = ((result.stdout or "") + (result.stderr or ""))[-MAX_OUTPUT:]
        return TestResult(
            name=name, command=command, status="passed" if result.returncode == 0 else "failed",
            returncode=result.returncode, output=output, duration_seconds=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") + (exc.stderr or ""))[-MAX_OUTPUT:] if isinstance(exc.stdout, str) else ""
        return TestResult(name, command, "timeout", None, output, time.monotonic() - started)
    except FileNotFoundError as exc:
        return TestResult(name, command, "unavailable", None, str(exc), time.monotonic() - started)
    except Exception as exc:
        return TestResult(name, command, "error", None, str(exc), time.monotonic() - started)


def detect_test_commands(workspace: Path) -> list[tuple[str, list[str], int, dict[str, str] | None]]:
    commands: list[tuple[str, list[str], int, dict[str, str] | None]] = []
    compile_targets = _python_compile_targets(workspace)
    if compile_targets:
        commands.append(
            ("Python compileall", [sys.executable, "-m", "compileall", "-q", *compile_targets], 120, None)
        )
        pyproject = workspace / "pyproject.toml"
        if _has_pytest_suite(workspace) and _module_available("pytest"):
            commands.append(("Pytest", _pytest_command(workspace), 180, None))
        if shutil.which("ruff"):
            commands.append(("Ruff", ["ruff", "check", "."], 120, None))
        if shutil.which("mypy") and pyproject.exists():
            commands.append(("Mypy", ["mypy", "."], 180, None))
    package = workspace / "package.json"
    if package.exists() and shutil.which("npm"):
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})} if isinstance(data, dict) else {}
        except Exception:
            scripts, deps = {}, {}
        env = os.environ.copy()
        env["CI"] = "1"
        if "lint" in scripts:
            commands.append(("npm lint", ["npm", "run", "lint"], 180, env))
        if "build" in scripts:
            commands.append(("npm build", ["npm", "run", "build"], 240, env))
        if "test" in scripts:
            if "vitest" in deps:
                command = ["npm", "test", "--", "--run"]
            elif "jest" in deps:
                command = ["npm", "test", "--", "--runInBand"]
            else:
                command = ["npm", "test", "--", "--watch=false"]
            commands.append(("npm test", command, 240, env))
        if (workspace / "tsconfig.json").exists() and shutil.which("npx"):
            commands.append(("TypeScript", ["npx", "tsc", "--noEmit"], 180, env))
    return commands


def run_detected_tests(workspace: Path) -> list[TestResult]:
    workspace = workspace.expanduser().resolve(strict=True)
    commands = detect_test_commands(workspace)
    if not commands:
        return [TestResult("Rilevamento test", [], "unavailable", None, "Nessun test rilevato.", 0.0)]
    results = [_run(name, command, workspace, timeout, env) for name, command, timeout, env in commands]
    if _has_pytest_suite(workspace) and not _module_available("pytest"):
        results.append(
            TestResult(
                "Pytest",
                _pytest_command(workspace),
                "unavailable",
                None,
                "Pytest non è installato nell'ambiente Python corrente; suite non eseguita.",
                0.0,
            )
        )
    return results


def format_test_results(results: list[TestResult]) -> str:
    interpretation = interpret_test_results(results)
    interpretation_icons = {"ok": "✅", "warning": "⚠️", "error": "❌"}
    chunks: list[str] = [
        f"{interpretation_icons[str(interpretation['level'])]} {interpretation['title']}\n"
        f"{interpretation['summary']}"
    ]
    icons = {"passed": "✅", "failed": "❌", "unavailable": "⚪", "timeout": "⏱️", "error": "⚠️"}
    for result in results:
        chunks.append(
            f"{icons[result.status]} {result.name} — {result.status} ({result.duration_seconds:.1f}s)\n"
            f"Comando: {' '.join(result.command) if result.command else '-'}\n"
            f"{result.output.strip() or '[nessun output]'}"
        )
    return "\n\n".join(chunks)


def test_results_to_dicts(results: list[TestResult]) -> list[dict]:
    return [
        {
            "name": result.name,
            "command": list(result.command),
            "status": result.status,
            "returncode": result.returncode,
            "output": result.output,
            "duration_seconds": result.duration_seconds,
        }
        for result in results
    ]


def test_summary(results: list[TestResult]) -> str:
    passed = sum(result.status == "passed" for result in results)
    failed = sum(result.status in {"failed", "timeout", "error"} for result in results)
    unavailable = sum(result.status == "unavailable" for result in results)
    return f"{passed} superati, {failed} non superati, {unavailable} non disponibili"
