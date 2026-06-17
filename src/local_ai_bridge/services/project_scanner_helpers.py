from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path


def _annotation(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args: list[str] = []
    positional = list(node.args.posonlyargs) + list(node.args.args)
    defaults_offset = len(positional) - len(node.args.defaults)
    for index, arg in enumerate(positional):
        value = arg.arg
        annotation = _annotation(arg.annotation)
        if annotation:
            value += f": {annotation}"
        if index >= defaults_offset:
            value += " = ..."
        args.append(value)
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        value = arg.arg
        annotation = _annotation(arg.annotation)
        if annotation:
            value += f": {annotation}"
        if default is not None:
            value += " = ..."
        args.append(value)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = _annotation(node.returns)
    return f"{prefix} {node.name}({', '.join(args)})" + (f" -> {returns}" if returns else "") + ": ..."


def summarize_python(content: str, relative: str) -> tuple[str, list[str]]:
    try:
        tree = ast.parse(content, filename=relative)
    except SyntaxError as exc:
        return f"[SyntaxError: {exc}]", [f"{relative}: {exc}"]

    rows: list[str] = []
    module_doc = ast.get_docstring(tree)
    if module_doc:
        rows.append('"""' + module_doc[:500].strip() + '"""')

    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append("." * node.level + (node.module or ""))
    if imports:
        rows.append("Import principali: " + ", ".join(list(dict.fromkeys(imports))[:20]))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rows.append(_function_signature(node))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(_annotation(base) for base in node.bases)
            rows.append(f"class {node.name}" + (f"({bases})" if bases else "") + ":")
            fields: list[str] = []
            for child in node.body:
                if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                    fields.append(f"    {child.target.id}: {_annotation(child.annotation)}")
            rows.extend(fields[:30])
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    rows.append("    " + _function_signature(child))
    return "\n".join(rows) or "(Nessuna definizione di primo livello)", []


def summarize_js(content: str) -> str:
    patterns = (
        r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)",
        r"(?:export\s+)?class\s+([A-Za-z_$][\w$]*)",
        r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
    )
    rows: list[str] = []
    for pattern in patterns:
        rows.extend(match.group(0).strip()[:240] + " ..." for match in re.finditer(pattern, content))
    return "\n".join(dict.fromkeys(rows)) or "(Nessuna firma rilevata)"


def summarize_generic(path: Path, content: str) -> str:
    if path.suffix == ".json":
        try:
            value = json.loads(content)
            if isinstance(value, dict):
                return "JSON keys: " + ", ".join(list(value)[:80])
            return f"JSON {type(value).__name__}"
        except Exception as exc:
            return f"JSON non valido: {exc}"
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return "\n".join(lines[:25]) or "(File vuoto o senza elementi riassumibili)"


def _read_pyproject(root: Path) -> dict:
    path = root / "pyproject.toml"
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def detect_project_version(root: Path) -> str | None:
    pyproject = _read_pyproject(root)
    value = pyproject.get("project", {}).get("version")
    if value:
        return str(value)
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            value = json.loads(package_json.read_text(encoding="utf-8")).get("version")
            if value:
                return str(value)
        except Exception:
            pass
    return None


def _dependency_names(root: Path) -> set[str]:
    names: set[str] = set()
    pyproject = _read_pyproject(root)
    for item in pyproject.get("project", {}).get("dependencies", []):
        names.add(re.split(r"[<>=!~\[]", str(item), maxsplit=1)[0].strip())
    requirements = root / "requirements.txt"
    if requirements.is_file():
        try:
            for line in requirements.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    names.add(re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip())
        except OSError:
            pass
    return {name for name in names if name}


def detect_stack(root: Path) -> str:
    markers: list[str] = []
    pyproject = _read_pyproject(root)
    checks = (
        ("Python", ("pyproject.toml", "requirements.txt")),
        ("Node.js / JavaScript", ("package.json",)),
        ("TypeScript", ("tsconfig.json",)),
        ("Rust", ("Cargo.toml",)),
        ("Go", ("go.mod",)),
        ("Java", ("pom.xml", "build.gradle")),
        ("Docker", ("Dockerfile", "docker-compose.yml")),
    )
    for label, names in checks:
        if any((root / name).exists() for name in names):
            markers.append(label)

    requires_python = pyproject.get("project", {}).get("requires-python")
    if requires_python:
        markers.append(f"Python richiesto: {requires_python}")

    build_backend = pyproject.get("build-system", {}).get("build-backend")
    if build_backend:
        markers.append(f"Build backend: {build_backend}")

    dependencies = {name.lower() for name in _dependency_names(root)}
    known = {
        "pyside6": "PySide6 desktop GUI",
        "pyqt6": "PyQt6 desktop GUI",
        "pytest": "pytest test suite",
        "platformdirs": "platformdirs",
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
    }
    for key, label in known.items():
        if key in dependencies:
            markers.append(label)

    pytest_options = pyproject.get("tool", {}).get("pytest")
    if pytest_options or any((root / name).exists() for name in ("pytest.ini", "conftest.py")):
        markers.append("pytest test suite")
    if (root / "tests").is_dir() and any((root / "tests").glob("test_*.py")):
        markers.append("Test Python presenti")
    if (root / "src").is_dir() and (root / "pyproject.toml").is_file():
        markers.append("Python package con layout src/")

    return "\n".join(f"- {item}" for item in dict.fromkeys(markers)) if markers else "Stack non determinato automaticamente"
