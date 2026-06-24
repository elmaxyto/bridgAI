from __future__ import annotations

from pathlib import Path, PurePosixPath

from local_ai_bridge.services.git import GitIntegrationError


MANAGED_START = "# >>> BridgAI managed GitHub ignores >>>"
MANAGED_END = "# <<< BridgAI managed GitHub ignores <<<"
_ENV_EXAMPLES = {".env.example", ".env.sample", ".env.template"}

_BASE_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Dependencies and virtual environments",
        (
            "node_modules/",
            "__pycache__/",
            ".venv/",
            ".pytest_cache/",
            ".mypy_cache/",
            ".ruff_cache/",
            ".tox/",
            ".nox/",
        ),
    ),
    (
        "Local secrets and logs",
        (
            ".env",
            ".env.*",
            "!.env.example",
            "!.env.sample",
            "!.env.template",
            "*.log",
            "npm-debug.log*",
            "yarn-debug.log*",
            "yarn-error.log*",
            "pnpm-debug.log*",
        ),
    ),
    ("Operating-system metadata", (".DS_Store", "Thumbs.db", "Desktop.ini")),
)

_STACK_SECTIONS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "node": (
        (
            "Node and frontend build output",
            (
                ".pnpm-store/",
                ".yarn/cache/",
                ".yarn/unplugged/",
                ".pnp.*",
                ".next/",
                ".nuxt/",
                ".output/",
                ".svelte-kit/",
                ".vite/",
                ".turbo/",
                ".vercel/",
                ".cache/",
                "coverage/",
                "dist/",
                "build/",
            ),
        ),
    ),
    "python": (
        (
            "Python bytecode, environments, and build output",
            (
                "*.py[cod]",
                "*$py.class",
                "venv/",
                ".coverage",
                ".coverage.*",
                "htmlcov/",
                "build/",
                "dist/",
                "*.egg-info/",
            ),
        ),
    ),
    "java": (
        ("Java and JVM build output", (".gradle/", "target/", "build/", "out/", "*.class")),
    ),
    "dotnet": ((".NET build output", (".vs/", "bin/", "obj/", "TestResults/")),),
    "rust": (("Rust build output", ("target/",)),),
    "php": (("PHP dependencies", ("vendor/",)),),
    "ruby": (("Ruby dependencies and coverage", (".bundle/", "vendor/bundle/", "coverage/")),),
}


def detect_stacks(workspace: Path) -> tuple[str, ...]:
    try:
        names = {entry.name.lower() for entry in workspace.iterdir()}
    except OSError as exc:
        raise GitIntegrationError(f"Impossibile analizzare il workspace: {exc}") from exc

    stacks: list[str] = []
    if names.intersection(
        {
            "package.json",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "bun.lock",
            "bun.lockb",
            "node_modules",
        }
    ):
        stacks.append("node")
    if names.intersection(
        {
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "setup.py",
            "setup.cfg",
            "pipfile",
            "poetry.lock",
            "uv.lock",
            ".venv",
            "__pycache__",
        }
    ):
        stacks.append("python")
    if names.intersection(
        {
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
            "gradlew",
        }
    ):
        stacks.append("java")
    if any(name.endswith((".sln", ".csproj", ".fsproj", ".vbproj")) for name in names):
        stacks.append("dotnet")
    if "cargo.toml" in names:
        stacks.append("rust")
    if "composer.json" in names:
        stacks.append("php")
    if "gemfile" in names:
        stacks.append("ruby")
    return tuple(stacks)


def _sections_for(stacks: tuple[str, ...]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    sections: list[tuple[str, tuple[str, ...]]] = list(_BASE_SECTIONS)
    seen = {pattern for _title, patterns in sections for pattern in patterns}
    for stack in stacks:
        for title, patterns in _STACK_SECTIONS.get(stack, ()):
            unique = tuple(pattern for pattern in patterns if pattern not in seen)
            if unique:
                sections.append((title, unique))
                seen.update(unique)
    return tuple(sections)


def managed_block(stacks: tuple[str, ...]) -> str:
    lines = [
        MANAGED_START,
        "# Rules maintained automatically before GitHub publishing.",
        "# Keep custom project rules outside this block.",
    ]
    if stacks:
        lines.append(f"# Detected stacks: {', '.join(stacks)}")
    for title, patterns in _sections_for(stacks):
        lines.extend(("", f"# {title}", *patterns))
    lines.extend(("", MANAGED_END))
    return "\n".join(lines)


def _is_env_secret(name: str) -> bool:
    return (name == ".env" or name.startswith(".env.")) and name not in _ENV_EXAMPLES


def is_managed_generated_path(relative: str, stacks: tuple[str, ...]) -> bool:
    parts = tuple(part.lower() for part in PurePosixPath(relative.replace("\\", "/")).parts)
    if not parts or parts[0] == ".git":
        return False
    basename = parts[-1]

    if any(
        part
        in {
            "node_modules",
            "__pycache__",
            ".venv",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".tox",
            ".nox",
        }
        for part in parts
    ):
        return True
    if _is_env_secret(basename):
        return True
    if basename in {".ds_store", "thumbs.db", "desktop.ini"} or basename.endswith(".log"):
        return True
    if basename.startswith(("npm-debug.log", "yarn-debug.log", "yarn-error.log", "pnpm-debug.log")):
        return True

    if "node" in stacks:
        generated = {
            ".pnpm-store",
            ".cache",
            ".next",
            ".nuxt",
            ".output",
            ".svelte-kit",
            ".vite",
            ".turbo",
            ".vercel",
            "coverage",
            "dist",
            "build",
        }
        if any(part in generated for part in parts):
            return True
        if ".yarn" in parts and any(part in {"cache", "unplugged"} for part in parts):
            return True
        if basename.startswith(".pnp."):
            return True

    if "python" in stacks:
        if any(part in {"venv", "htmlcov", "build", "dist"} for part in parts):
            return True
        if any(part.endswith(".egg-info") for part in parts):
            return True
        if basename.endswith((".pyc", ".pyo", ".pyd")) or basename.startswith(".coverage"):
            return True

    if "java" in stacks:
        if any(part in {".gradle", "target", "build", "out"} for part in parts):
            return True
        if basename.endswith(".class"):
            return True
    if "dotnet" in stacks and any(part in {".vs", "bin", "obj", "testresults"} for part in parts):
        return True
    if "rust" in stacks and "target" in parts:
        return True
    if "php" in stacks and "vendor" in parts:
        return True
    if "ruby" in stacks:
        if ".bundle" in parts or "coverage" in parts:
            return True
        if any(left == "vendor" and right == "bundle" for left, right in zip(parts, parts[1:])):
            return True
    return False
