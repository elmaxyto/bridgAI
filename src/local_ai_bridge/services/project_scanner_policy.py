from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from local_ai_bridge.core.safety import is_sensitive_relative_path


# The policy is grouped by reason so defaults remain auditable and diagnostics
# can explain why content was omitted.
EXCLUDED_DIRS_BY_REASON = {
    "controllo versione": {
        ".git", ".hg", ".svn", ".bzr", "_darcs",
    },
    "dipendenze installate": {
        "node_modules", "bower_components", "jspm_packages", "vendor",
        "site-packages", "dist-packages", "pods", "carthage", ".bundle",
        ".pnpm", ".pub-cache",
    },
    "ambienti virtuali": {
        ".venv", "venv", ".virtualenv", "virtualenv",
    },
    "cache strumenti": {
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        ".hypothesis", ".tox", ".nox", ".cache", ".parcel-cache",
        ".turbo", ".nx", ".vite", ".sass-cache", ".gradle", ".m2",
        ".ivy2", ".npm", ".npm-cache", ".nyc_output", ".dart_tool",
        ".angular", "cmakefiles", "_deps", ".cxx", ".externalnativebuild",
        "unplugged",
    },
    "output di build": {
        "dist", "build", "out", "target", "obj", ".output", ".next",
        ".nuxt", ".svelte-kit", ".serverless", ".webpack", ".expo",
        "intermediates", "outputs", "binaries", "deriveddatacache",
        "intermediate",
    },
    "risultati test e copertura": {
        "coverage", "htmlcov", "test-results", "playwright-report",
        "allure-results", "allure-report", "pytest-report", "junit-reports",
    },
    "file temporanei o runtime": {
        ".tmp", ".temp", ".bridgai",
    },
    "configurazione IDE": {
        ".idea", ".vscode", ".vs", ".fleet", ".history", ".settings",
    },
    "metadati sistema": {
        "__macosx",
    },
}

ROOT_LEVEL_EXCLUDED_DIRS_BY_REASON = {
    "cache o runtime locale": {
        "cache", "caches", "tmp", "temp", "logs", "log", "backups",
        "backup", "incoming_media", "uploads", "downloads",
    },
    "materiale sperimentale": {
        "scratch", "sandbox", "experiments", "experiment", "drafts", "playground",
    },
}

EXCLUDED_PATHS_BY_REASON = {
    "cache package manager": (
        ".yarn/cache", ".yarn/unplugged", ".angular/cache",
    ),
}

EXCLUDED_DIR_PATTERNS_BY_REASON = {
    "cache Gradle": (".gradle-*",),
    "output CMake/Bazel": ("cmake-build-*", "bazel-*"),
    "metadati pacchetto Python": ("*.egg-info", "*.dist-info"),
    "directory temporanee": (".tmp-*", "tmp-*", ".temp-*"),
}

EXCLUDED_FILE_NAMES_BY_REASON = {
    "metadati sistema": {
        ".ds_store", "thumbs.db", "desktop.ini",
    },
    "configurazione locale sensibile": {
        "local.properties",
    },
    "cache strumenti": {
        ".coverage", ".eslintcache", ".stylelintcache", ".ninja_deps",
        ".ninja_log", "lcov.info", "coverage.xml", "junit.xml",
    },
}

EXCLUDED_FILE_PATTERNS_BY_REASON = {
    "file temporanei": (
        "*.tmp", "*.temp", "*.bak", "*.old", "*.orig", "*.rej",
        "*.swp", "*.swo", "*~", ".#*", "*.log",
    ),
    "bundle generati": (
        "*.min.js", "*.min.css", "*.bundle.js", "*.bundle.css",
        "*.chunk.js", "*.chunk.css", "*.js.map", "*.css.map",
    ),
    "codice generato": (
        "*.g.dart", "*.freezed.dart", "*.designer.cs", "*.generated.cs",
        "*.g.cs", "*.pb.go", "*.pb.cc", "*.pb.h", "*_pb2.py",
        "*_pb2_grpc.py",
    ),
    "output diagnostici generati": (
        "final_report.txt", "*_final_report.txt",
        "tsc_output*.txt", "ts_errors*.txt",
        "typecheck_output*.txt", "pytest_output*.txt",
        "compile_output*.txt", "check_bridge.txt",
    ),
}

EXCLUDED_FILE_EXTENSIONS_BY_REASON = {
    "chiavi, certificati o archivi credenziali": {
        ".keystore", ".jks", ".p12", ".pfx", ".pem", ".key", ".der",
    },
    "bytecode o binari compilati": {
        ".pyc", ".pyo", ".pyd", ".class", ".o", ".obj", ".so", ".dll",
        ".dylib", ".a", ".lib", ".pdb", ".ilk", ".exp", ".idb", ".tlog",
        ".dex", ".aar", ".apk", ".aab", ".ipa", ".exe", ".msi", ".wasm",
        ".beam", ".elc",
    },
    "archivi o pacchetti generati": {
        ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".tgz",
        ".jar", ".war", ".ear", ".whl", ".egg",
    },
    "dati runtime": {
        ".sqlite", ".sqlite3", ".db", ".db-shm", ".db-wal",
    },
}

PRIORITY_DIRS = (
    "src", "app", "lib", "packages", "apps", "services", "core", "server",
    "client", "web", "api", "tests", "test", "spec", "android", "ios",
    "scripts", "tools", "config", "configs", ".github", ".gitlab",
    ".devcontainer",
)
PRIORITY_DIR_RANK = {name: index for index, name in enumerate(PRIORITY_DIRS)}

CODE_EXTENSIONS = {
    ".py", ".pyi", ".pyx", ".js", ".jsx", ".mjs", ".cjs", ".ts",
    ".tsx", ".mts", ".cts", ".vue", ".svelte", ".astro", ".java", ".kt",
    ".kts", ".groovy", ".gradle", ".scala", ".clj", ".cljs", ".go", ".rs",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".m", ".mm",
    ".swift", ".cs", ".fs", ".fsx", ".vb", ".rb", ".php", ".dart",
    ".lua", ".r", ".pl", ".pm", ".sh", ".bash", ".zsh", ".fish",
    ".ps1", ".bat", ".cmd", ".sql", ".graphql", ".gql", ".proto",
}
CONFIG_AND_DOC_EXTENSIONS = {
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".xml", ".xaml",
    ".plist", ".properties", ".ini", ".cfg", ".conf", ".html", ".htm",
    ".css", ".scss", ".sass", ".less", ".md", ".mdx", ".rst", ".txt",
}
SUPPORTED_EXTENSIONS = CODE_EXTENSIONS | CONFIG_AND_DOC_EXTENSIONS

MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".tif",
    ".tiff", ".ico", ".icns", ".svg", ".mp3", ".wav", ".ogg", ".m4a",
    ".flac", ".mp4", ".mov", ".mkv", ".webm", ".avi", ".woff", ".woff2",
    ".ttf", ".otf", ".eot",
}

SPECIAL_FILES = {
    "dockerfile", "makefile", "gnumakefile", "cmakelists.txt", "jenkinsfile",
    "procfile", "vagrantfile", "rakefile", "gemfile", "gemfile.lock", "podfile",
    "podfile.lock", "fastfile", "brewfile", "tiltfile", "justfile", "pipfile",
    "pipfile.lock", "poetry.lock", "uv.lock", "cargo.toml", "cargo.lock",
    "go.mod", "go.sum", "pom.xml", "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts", "gradle.properties",
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
    "pnpm-lock.yaml", "bun.lock", "bun.lockb", "composer.json", "composer.lock",
    "pubspec.yaml", "pubspec.lock", "pyproject.toml", "setup.py", "setup.cfg",
    "tox.ini", "pytest.ini", "requirements.txt", "environment.yml",
    "package.resolved", "packages.lock.json", "gradle.lockfile", ".gitignore",
    ".gitattributes", ".editorconfig", ".dockerignore",
}
SPECIAL_FILE_PATTERNS = (
    "dockerfile.*", "requirements*.txt", "taskfile*.yml", "taskfile*.yaml",
    "compose*.yml", "compose*.yaml", "docker-compose*.yml", "docker-compose*.yaml",
)
COMPACT_METADATA_FILES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "bun.lock", "bun.lockb", "pipfile.lock", "poetry.lock", "uv.lock",
    "cargo.lock", "go.sum", "gemfile.lock", "podfile.lock", "composer.lock",
    "pubspec.lock", "package.resolved", "packages.lock.json", "gradle.lockfile",
}

GENERATED_REPORT_PATTERNS = (
    "ai_super_report.md",
    "ai_super_report_*.md",
    "report_diagnostic.md",
    "report_diagnostic_*.md",
    "super_report.md",
    "super_report_*.md",
)
PROJECT_IGNORE_FILE = ".bridgai/ignore"


@dataclass(frozen=True, slots=True)
class ProjectIgnoreRules:
    """Project-local exclusions and explicit built-in-filter overrides."""

    patterns: tuple[str, ...] = ()
    include_patterns: tuple[str, ...] = ()

    @classmethod
    def load(cls, root: Path) -> "ProjectIgnoreRules":
        path = root / PROJECT_IGNORE_FILE
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return cls()

        patterns: list[str] = []
        include_patterns: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            normalized = line.replace("\\", "/")
            while normalized.startswith("./"):
                normalized = normalized[2:]
            if not normalized:
                continue
            if normalized.startswith("!") and len(normalized) > 1:
                include_patterns.append(normalized[1:])
            else:
                patterns.append(normalized)
        return cls(tuple(patterns), tuple(include_patterns))

    def matches(self, relative: str, *, is_dir: bool = False) -> bool:
        return self._matches_any(self.patterns, relative, is_dir=is_dir)

    def explicitly_includes(self, relative: str, *, is_dir: bool = False) -> bool:
        return self._matches_any(self.include_patterns, relative, is_dir=is_dir)

    @classmethod
    def _matches_any(
        cls,
        patterns: tuple[str, ...],
        relative: str,
        *,
        is_dir: bool,
    ) -> bool:
        candidate = relative.replace("\\", "/").strip("/")
        if not candidate:
            return False

        parts = candidate.split("/")
        for raw_pattern in patterns:
            directory_only = raw_pattern.endswith("/")
            pattern = raw_pattern.rstrip("/")
            if not pattern:
                continue

            anchored = raw_pattern.startswith("/")
            pattern = pattern.lstrip("/")
            if directory_only:
                if cls._directory_match(candidate, parts, pattern, anchored):
                    return True
                continue

            recursive_base = pattern[:-3].rstrip("/") if pattern.endswith("/**") else ""
            if recursive_base and (
                candidate == recursive_base or candidate.startswith(recursive_base + "/")
            ):
                return True

            if "/" in pattern or anchored:
                if fnmatch.fnmatchcase(candidate, pattern):
                    return True
            elif any(fnmatch.fnmatchcase(part, pattern) for part in parts):
                return True
        return False

    @staticmethod
    def _directory_match(candidate: str, parts: list[str], pattern: str, anchored: bool) -> bool:
        if "/" in pattern or anchored:
            prefixes = ["/".join(parts[:index]) for index in range(1, len(parts) + 1)]
            return any(fnmatch.fnmatchcase(prefix, pattern) for prefix in prefixes)
        return any(fnmatch.fnmatchcase(part, pattern) for part in parts)


def load_project_ignore(root: Path) -> ProjectIgnoreRules:
    return ProjectIgnoreRules.load(root)


def is_generated_report(relative: str) -> bool:
    name = Path(relative).name.casefold()
    return any(fnmatch.fnmatch(name, pattern) for pattern in GENERATED_REPORT_PATTERNS)


def relative_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _matches_reason(value: str, rules: dict[str, set[str]]) -> str | None:
    candidate = value.casefold()
    for reason, names in rules.items():
        if candidate in names:
            return reason
    return None


def _matches_patterns(value: str, rules: dict[str, tuple[str, ...]]) -> str | None:
    candidate = value.casefold()
    for reason, patterns in rules.items():
        if any(fnmatch.fnmatchcase(candidate, pattern.casefold()) for pattern in patterns):
            return reason
    return None


def _matches_relative_path(relative: str, rules: dict[str, tuple[str, ...]]) -> str | None:
    candidate = relative.replace("\\", "/").strip("/").casefold()
    for reason, patterns in rules.items():
        for pattern in patterns:
            normalized = pattern.strip("/").casefold()
            if candidate == normalized or candidate.endswith("/" + normalized):
                return reason
    return None


def _looks_like_virtual_environment(path: Path) -> bool:
    try:
        if (path / "pyvenv.cfg").is_file():
            return True
        name = path.name.casefold()
        if name not in {"env", ".env", "python-env", "python_env", "runtime-env"}:
            return False
        return (
            (path / "bin" / "activate").is_file()
            or (path / "Scripts" / "activate").is_file()
            or (path / "Scripts" / "python.exe").is_file()
        )
    except OSError:
        return False


def directory_exclusion_reason(
    root: Path,
    current: Path,
    name: str,
    ignore: ProjectIgnoreRules,
) -> str | None:
    path = current / name
    relative = relative_posix(root, path)
    sensitive = is_sensitive_relative_path(relative)
    if name.casefold() == ".bridgai":
        return "configurazione interna BridgAI"
    if not sensitive and ignore.explicitly_includes(relative, is_dir=True):
        return None

    # Prefer the most actionable technical category over the generic sensitive
    # label. The path remains excluded either way; this only improves diagnostics.
    reason = _matches_relative_path(relative, EXCLUDED_PATHS_BY_REASON)
    if reason:
        return reason
    reason = _matches_reason(name, EXCLUDED_DIRS_BY_REASON)
    if reason:
        return reason
    if current == root:
        reason = _matches_reason(name, ROOT_LEVEL_EXCLUDED_DIRS_BY_REASON)
        if reason:
            return reason
    reason = _matches_patterns(name, EXCLUDED_DIR_PATTERNS_BY_REASON)
    if reason:
        return reason
    if _looks_like_virtual_environment(path):
        return "ambiente virtuale rilevato"
    if sensitive:
        return "percorso sensibile"
    if ignore.matches(relative, is_dir=True):
        return "regola progetto"
    return None


def file_exclusion_reason(
    root: Path,
    path: Path,
    ignore: ProjectIgnoreRules,
) -> str | None:
    relative = relative_posix(root, path)
    if relative == PROJECT_IGNORE_FILE:
        return "configurazione interna BridgAI"
    if is_generated_report(relative):
        return "report generato"

    sensitive = is_sensitive_relative_path(relative)
    if not sensitive and ignore.explicitly_includes(relative):
        return None

    name = path.name.casefold()
    reason = _matches_reason(name, EXCLUDED_FILE_NAMES_BY_REASON)
    if reason:
        return reason
    reason = _matches_patterns(name, EXCLUDED_FILE_PATTERNS_BY_REASON)
    if reason:
        return reason
    extension = path.suffix.casefold()
    for category, extensions in EXCLUDED_FILE_EXTENSIONS_BY_REASON.items():
        if extension in extensions:
            return category
    if sensitive:
        return "percorso sensibile"
    if ignore.matches(relative):
        return "regola progetto"
    return None

def is_special_file(path: Path) -> bool:
    name = path.name.casefold()
    return name in SPECIAL_FILES or any(
        fnmatch.fnmatchcase(name, pattern.casefold()) for pattern in SPECIAL_FILE_PATTERNS
    )


def is_context_file(path: Path) -> bool:
    return path.suffix.casefold() in SUPPORTED_EXTENSIONS or is_special_file(path)


def is_compact_metadata_file(path: Path) -> bool:
    return path.name.casefold() in COMPACT_METADATA_FILES


def is_media_file(path: Path | str) -> bool:
    return Path(path).suffix.casefold() in MEDIA_EXTENSIONS


def directory_scan_key(path: Path) -> tuple[int, int, str]:
    name = path.name.casefold()
    priority = PRIORITY_DIR_RANK.get(name, len(PRIORITY_DIR_RANK))
    hidden = int(name.startswith("."))
    return priority, hidden, name


def project_file_sort_key(item: tuple[Path, str]) -> tuple[int, int, str]:
    _, relative = item
    parts = [part.casefold() for part in Path(relative).parts]
    rank = min(
        (PRIORITY_DIR_RANK[part] for part in parts if part in PRIORITY_DIR_RANK),
        default=len(PRIORITY_DIR_RANK),
    )
    return rank, len(parts), relative.casefold()
