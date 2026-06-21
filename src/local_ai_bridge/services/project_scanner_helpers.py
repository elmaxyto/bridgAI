from __future__ import annotations

import ast
import json
import re
import tomllib
import xml.etree.ElementTree as ET
from html import unescape
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


def _short(value: str, limit: int = 220) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else compact[: limit - 3].rstrip() + "..."


def _unique(values: list[str], limit: int) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))[:limit]


def summarize_js(content: str) -> str:
    """Extract a bounded structural outline from JavaScript/TypeScript text."""
    rows: list[str] = []
    import_sources = _unique(
        [
            match.group(1) or match.group(2)
            for match in re.finditer(
                r'''(?mx)
                ^[ \t]*import[ \t]+(?:type[ \t]+)?(?:[^;\n"']+?[ \t]+from[ \t]+)?["']([^"']+)["']
                |^[ \t]*export[ \t]+\*[ \t]+from[ \t]+["']([^"']+)["']
                ''',
                content,
            )
        ],
        12,
    )
    if import_sources:
        rows.append("Import/moduli principali: " + ", ".join(import_sources))

    signatures: list[str] = []
    signature_patterns = (
        r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\([^)]*\)",
        r"(?:export\s+)?(?:default\s+)?class\s+[A-Za-z_$][\w$]*(?:\s+extends\s+[^\n{]+)?",
        r"(?:export\s+)?(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
        r"(?:export\s+)?(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*(?:async\s*)?[A-Za-z_$][\w$]*\s*=>",
        r"(?:export\s+)?(?:interface|type|enum)\s+[A-Za-z_$][\w$]*",
    )
    for pattern in signature_patterns:
        signatures.extend(_short(match.group(0)) + " ..." for match in re.finditer(pattern, content))
    rows.extend(_unique(signatures, 24))

    export_names = _unique(
        re.findall(
            r"(?m)^\s*export\s+(?:default\s+)?(?:const|let|var|function|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)",
            content,
        ),
        20,
    )
    reexport_blocks = re.findall(r"(?m)^\s*export\s*\{([^}]+)\}", content)
    for block in reexport_blocks:
        for value in block.split(","):
            export_names.append(value.strip().split(" as ")[-1].strip())
    export_names = _unique(export_names, 20)
    if export_names:
        rows.append("Export rilevati: " + ", ".join(export_names))

    if len(rows) <= (1 if import_sources else 0):
        declarations = _unique(
            re.findall(
                r"(?m)^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=",
                content,
            ),
            15,
        )
        if declarations:
            rows.append("Dichiarazioni principali: " + ", ".join(declarations))

    if not rows:
        line_count = content.count("\n") + (1 if content else 0)
        return f"Modulo JavaScript/TypeScript ({line_count} righe); nessuna API di primo livello rilevata."
    return "\n".join(rows)


def _without_boilerplate_comments(content: str) -> str:
    value = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    return value


def _markdown_summary(content: str) -> str:
    lines = content.splitlines()
    headings = _unique(
        [re.sub(r"^#{1,6}\s*", "", line).strip() for line in lines if re.match(r"^\s*#{1,6}\s+", line)],
        12,
    )
    prose = _unique(
        [
            _short(line.strip())
            for line in lines
            if line.strip()
            and not line.lstrip().startswith(("#", "```", "<!--", "!["))
        ],
        6,
    )
    rows = [f"Documento Markdown: {len(lines)} righe."]
    if headings:
        rows.append("Sezioni: " + " | ".join(headings))
    if prose:
        rows.append("Contenuti iniziali: " + " / ".join(prose))
    return "\n".join(rows)


def _html_summary(content: str) -> str:
    cleaned = _without_boilerplate_comments(content)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", cleaned, flags=re.I | re.S)
    description_match = re.search(
        r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']+)",
        cleaned,
        flags=re.I,
    )
    headings = _unique(
        [unescape(re.sub(r"<[^>]+>", "", match)).strip() for match in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", cleaned, flags=re.I | re.S)],
        8,
    )
    rows = ["Documento HTML."]
    if title_match:
        rows.append("Titolo: " + _short(unescape(title_match.group(1))))
    if description_match:
        rows.append("Descrizione: " + _short(unescape(description_match.group(1))))
    if headings:
        rows.append("Intestazioni: " + " | ".join(headings))
    scripts = len(re.findall(r"<script\b", cleaned, flags=re.I))
    styles = len(re.findall(r"<(?:link[^>]+stylesheet|style)\b", cleaned, flags=re.I))
    rows.append(f"Struttura: {scripts} script, {styles} riferimenti/blocchi stile.")
    return "\n".join(rows)


def _xml_summary(content: str) -> str:
    cleaned = _without_boilerplate_comments(content).strip()
    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError as exc:
        return f"XML non valido: {exc}"

    def local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    tags = _unique([local_name(node.tag) for node in root.iter()], 20)
    rows = [f"XML root: {local_name(root.tag)}", "Elementi principali: " + ", ".join(tags)]
    permissions: list[str] = []
    for node in root.iter():
        if local_name(node.tag) != "uses-permission":
            continue
        for key, value in node.attrib.items():
            if key.rsplit("}", 1)[-1] == "name":
                permissions.append(value)
    if permissions:
        rows.append("Permessi dichiarati: " + ", ".join(_unique(permissions, 12)))
    return "\n".join(rows)


def _css_summary(content: str) -> str:
    cleaned = _without_boilerplate_comments(content)
    variables = _unique(re.findall(r"(--[A-Za-z0-9_-]+)\s*:", cleaned), 20)
    selectors = _unique(
        [_short(value) for value in re.findall(r"(?m)^\s*([^@\n][^\n{]+)\s*\{", cleaned)],
        12,
    )
    rows = [f"Foglio di stile: {content.count(chr(10)) + (1 if content else 0)} righe."]
    if variables:
        rows.append("Variabili CSS: " + ", ".join(variables))
    if selectors:
        rows.append("Selettori principali: " + " | ".join(selectors))
    return "\n".join(rows)


def summarize_generic(path: Path, content: str) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        try:
            value = json.loads(content)
            if isinstance(value, dict):
                return "JSON keys: " + ", ".join(list(value)[:80])
            return f"JSON {type(value).__name__}"
        except Exception as exc:
            return f"JSON non valido: {exc}"
    if suffix in {".md", ".mdx", ".rst"}:
        return _markdown_summary(content)
    if suffix in {".html", ".htm"}:
        return _html_summary(content)
    if suffix in {".xml", ".xaml", ".plist"}:
        return _xml_summary(content)
    if suffix in {".css", ".scss", ".sass", ".less"}:
        return _css_summary(content)

    cleaned = _without_boilerplate_comments(content)
    lines = [
        _short(line.strip())
        for line in cleaned.splitlines()
        if line.strip()
        and not line.lstrip().startswith(("#", "//", ";"))
        and "copyright" not in line.casefold()
        and "licensed under" not in line.casefold()
    ]
    selected = _unique(lines, 18)
    if not selected:
        return "(File vuoto o senza elementi riassumibili)"
    return "\n".join(selected)

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
