from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
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
_ENVIRONMENT_SENSITIVE_CHECKS = {
    "Python compileall",
    "npm build",
    "TypeScript",
    "Ruff",
    "Mypy",
}
_PYTHON_CHECKS = {"Python compileall", "Pytest", "Mypy"}
_ENVIRONMENT_FAILURE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bPermissionError\b",
        r"\bFileNotFoundError\b",
        r"\bNotADirectoryError\b",
        r"\[WinError\s+5\]",
        r"\bEACCES\b",
        r"\bEPERM\b",
        r"access(?:o)? (?:is )?denied",
        r"accesso negato",
        r"read-only file system",
        r"used by another process",
        r"impossibile accedere al file.*utilizzato da un altro processo",
        r"command not found",
        r"is not recognized as an internal or external command",
        r"cannot find module",
        r"no module named",
    )
)
_PYTHON_SYNTAX_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bSyntaxError\b",
        r"\bIndentationError\b",
        r"\bTabError\b",
    )
)


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


def _matches_any(output: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(output or "") for pattern in patterns)


def _is_environment_failure(result: TestResult) -> bool:
    return (
        result.name in _ENVIRONMENT_SENSITIVE_CHECKS
        and _matches_any(result.output, _ENVIRONMENT_FAILURE_PATTERNS)
    )


def _is_confirmed_structural_failure(result: TestResult) -> bool:
    if result.status != "failed" or result.name not in _STRUCTURAL_CHECKS:
        return False
    if result.name == "Python compileall":
        return _matches_any(result.output, _PYTHON_SYNTAX_PATTERNS)
    return not _is_environment_failure(result)


def _normalize_result(result: TestResult) -> TestResult:
    """Turn tooling/environment failures into an inconclusive result.

    A non-zero exit code is not always evidence that the proposed code is broken.
    In particular, permission errors while creating caches should not be presented
    as structural failures caused by the applied patch.
    """
    if result.status != "failed":
        return result
    if result.name == "Python compileall" and _matches_any(
        result.output, _PYTHON_SYNTAX_PATTERNS
    ):
        return result
    if not _is_environment_failure(result):
        return result
    explanation = (
        "Controllo non conclusivo: il comando è stato bloccato dall'ambiente o dai "
        "permessi. Nessun errore strutturale del codice è stato confermato."
    )
    details = result.output.strip()
    output = explanation if not details else f"{explanation}\n\nDettagli originali:\n{details}"
    return TestResult(
        name=result.name,
        command=list(result.command),
        status="unavailable",
        returncode=result.returncode,
        output=output,
        duration_seconds=result.duration_seconds,
    )


def interpret_test_results(results: list[TestResult]) -> dict[str, object]:
    """Explain checks without attributing environmental failures to the patch."""
    normalized_results = [_normalize_result(result) for result in results]
    passed_checks = sum(result.status == "passed" for result in normalized_results)
    failed_checks = sum(result.status == "failed" for result in normalized_results)
    unavailable_checks = sum(result.status == "unavailable" for result in normalized_results)
    interrupted_checks = sum(
        result.status in {"timeout", "error"} for result in normalized_results
    )
    inconclusive_checks = unavailable_checks + interrupted_checks
    structural_failures = [
        result.name
        for result in normalized_results
        if _is_confirmed_structural_failure(result)
    ]
    pytest_result = next(
        (result for result in normalized_results if result.name == "Pytest"), None
    )
    pytest = _pytest_counts(pytest_result.output if pytest_result else "")
    pytest_not_passed = pytest["failed"] + pytest["errors"]

    if structural_failures:
        names = ", ".join(structural_failures)
        level = "error"
        title = "Controllo strutturale non superato"
        summary = (
            f"{names} ha rilevato un errore strutturale confermato nel codice. "
            "L'aggiornamento resta applicato: esamina i dettagli prima di pubblicarlo."
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
                ". Questo non significa automaticamente che l'intera applicazione non "
                "funzioni. Esamina i dettagli prima di considerare concluso il lavoro."
            )
        else:
            summary = (
                f"{failed_checks} controlli non sono stati superati e {passed_checks} sono riusciti. "
                "Non è stato confermato un errore strutturale; esamina i dettagli."
            )
        if inconclusive_checks:
            summary += f" Inoltre, {inconclusive_checks} controlli non sono stati completati."
    elif inconclusive_checks:
        level = "warning"
        title = "Verifica incompleta"
        summary = (
            f"{passed_checks} controlli superati e {inconclusive_checks} non completati o "
            "non disponibili. Nessun errore della patch è stato confermato dai controlli eseguiti."
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
        "interrupted_checks": interrupted_checks,
        "inconclusive_checks": inconclusive_checks,
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
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
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


def _isolated_check_env(
    name: str,
    base_env: dict[str, str] | None,
    temporary_root: Path,
) -> dict[str, str] | None:
    if name not in _PYTHON_CHECKS and name not in {"Ruff"}:
        return base_env
    env = (base_env or os.environ).copy()
    pycache = temporary_root / "pycache"
    pycache.mkdir(parents=True, exist_ok=True)
    env["PYTHONPYCACHEPREFIX"] = str(pycache)
    if name == "Mypy":
        mypy_cache = temporary_root / "mypy"
        mypy_cache.mkdir(parents=True, exist_ok=True)
        env["MYPY_CACHE_DIR"] = str(mypy_cache)
    if name == "Ruff":
        ruff_cache = temporary_root / "ruff"
        ruff_cache.mkdir(parents=True, exist_ok=True)
        env["RUFF_CACHE_DIR"] = str(ruff_cache)
    return env


def run_detected_tests(workspace: Path) -> list[TestResult]:
    workspace = workspace.expanduser().resolve(strict=True)
    commands = detect_test_commands(workspace)
    if not commands:
        return [TestResult("Rilevamento test", [], "unavailable", None, "Nessun test rilevato.", 0.0)]

    temporary_root = Path(tempfile.mkdtemp(prefix="bridgai-checks-"))
    try:
        results = []
        for name, command, timeout, env in commands:
            isolated_env = _isolated_check_env(name, env, temporary_root)
            result = _run(name, command, workspace, timeout, isolated_env)
            results.append(_normalize_result(result))
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)

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
    normalized_results = [_normalize_result(result) for result in results]
    interpretation = interpret_test_results(normalized_results)
    interpretation_icons = {"ok": "✅", "warning": "⚠️", "error": "❌"}
    chunks: list[str] = [
        f"{interpretation_icons[str(interpretation['level'])]} {interpretation['title']}\n"
        f"{interpretation['summary']}"
    ]
    icons = {"passed": "✅", "failed": "❌", "unavailable": "⚪", "timeout": "⏱️", "error": "⚠️"}
    labels = {
        "passed": "superato",
        "failed": "non superato",
        "unavailable": "non disponibile",
        "timeout": "interrotto per timeout",
        "error": "non completato",
    }
    for result in normalized_results:
        chunks.append(
            f"{icons[result.status]} {result.name} — {labels[result.status]} ({result.duration_seconds:.1f}s)\n"
            f"Comando: {' '.join(result.command) if result.command else '-'}\n"
            f"{result.output.strip() or '[nessun output]'}"
        )
    return "\n\n".join(chunks)


def test_results_to_dicts(results: list[TestResult]) -> list[dict]:
    normalized_results = [_normalize_result(result) for result in results]
    return [
        {
            "name": result.name,
            "command": list(result.command),
            "status": result.status,
            "returncode": result.returncode,
            "output": result.output,
            "duration_seconds": result.duration_seconds,
        }
        for result in normalized_results
    ]


def test_summary(results: list[TestResult]) -> str:
    normalized_results = [_normalize_result(result) for result in results]
    passed = sum(result.status == "passed" for result in normalized_results)
    failed = sum(result.status == "failed" for result in normalized_results)
    unavailable = sum(
        result.status in {"unavailable", "timeout", "error"}
        for result in normalized_results
    )
    return f"{passed} superati, {failed} non superati, {unavailable} non disponibili"
