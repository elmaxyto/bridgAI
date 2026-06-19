from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from pathlib import Path


LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_INVALID_PROJECT_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')



def hash_password(password: str, *, iterations: int = 600_000) -> str:
    if len(password) < 10:
        raise ValueError("La password deve contenere almeno 10 caratteri.")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(raw_iterations)
        salt = base64.urlsafe_b64decode(raw_salt.encode())
        expected = base64.urlsafe_b64decode(raw_digest.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def is_loopback_host(host: str) -> bool:
    return host.strip().lower() in LOOPBACK_HOSTS


def _resolved_directory(value: str | Path | None, label: str) -> Path | None:
    if value is None or not str(value).strip():
        return None
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError(f"{label} non è una directory valida: {path}")
    return path


def validate_project_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError("Inserisci un nome per il progetto.")
    if len(name) > 120:
        raise ValueError("Il nome del progetto non può superare 120 caratteri.")
    if name in {".", ".."} or name.startswith("."):
        raise ValueError("Il nome del progetto non può essere nascosto o relativo.")
    if name.endswith((" ", ".")):
        raise ValueError("Il nome del progetto non può terminare con spazio o punto.")
    if _INVALID_PROJECT_CHARS.search(name):
        raise ValueError("Il nome del progetto contiene caratteri non validi.")
    if name.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        raise ValueError("Il nome del progetto è riservato dal sistema operativo.")
    return name


@dataclass(frozen=True, slots=True)
class WebSecurityConfig:
    host: str = "127.0.0.1"
    auth_token: str | None = None
    username: str | None = None
    password_hash: str | None = None
    workspace_root: Path | None = None
    fixed_workspace: Path | None = None

    @classmethod
    def build(
        cls,
        *,
        host: str = "127.0.0.1",
        auth_token: str | None = None,
        username: str | None = None,
        password_hash: str | None = None,
        workspace_root: str | Path | None = None,
        fixed_workspace: str | Path | None = None,
    ) -> "WebSecurityConfig":
        normalized_token = (auth_token or "").strip() or None
        normalized_username = (username or "").strip() or None
        normalized_password_hash = (password_hash or "").strip() or None
        if bool(normalized_username) != bool(normalized_password_hash):
            raise ValueError("Username e password devono essere configurati insieme.")
        root = _resolved_directory(workspace_root, "La root dei workspace")
        fixed = _resolved_directory(fixed_workspace, "Il workspace")

        if root is not None and fixed is not None:
            try:
                fixed.relative_to(root)
            except ValueError as exc:
                raise ValueError("Il workspace fisso deve trovarsi dentro la root autorizzata.") from exc

        if not is_loopback_host(host):
            if normalized_token is None and normalized_password_hash is None:
                raise ValueError(
                    "Per l'accesso remoto configura un token oppure username e password."
                )
            if normalized_token is not None and len(normalized_token) < 24:
                raise ValueError("Il token remoto deve contenere almeno 24 caratteri.")
            if root is None and fixed is None:
                raise ValueError(
                    "Per l'accesso remoto configura --workspace-root oppure --workspace."
                )

        return cls(
            host=host,
            auth_token=normalized_token,
            username=normalized_username,
            password_hash=normalized_password_hash,
            workspace_root=root,
            fixed_workspace=fixed,
        )

    @property
    def remote_mode(self) -> bool:
        return not is_loopback_host(self.host)

    @property
    def requires_authentication(self) -> bool:
        return self.auth_token is not None or self.password_hash is not None

    def accepts_authorization(self, header_value: str | None) -> bool:
        if not self.requires_authentication:
            return True
        if not header_value:
            return False
        if self.auth_token is not None and header_value.startswith("Bearer "):
            return hmac.compare_digest(header_value[7:].strip(), self.auth_token)
        if self.username is not None and self.password_hash is not None and header_value.startswith("Basic "):
            try:
                decoded = base64.b64decode(header_value[6:].strip(), validate=True).decode("utf-8")
                candidate_username, candidate_password = decoded.split(":", 1)
            except (ValueError, UnicodeDecodeError):
                return False
            return hmac.compare_digest(candidate_username, self.username) and verify_password(candidate_password, self.password_hash)
        return False


class WorkspacePolicy:
    def __init__(self, config: WebSecurityConfig) -> None:
        self.root = config.workspace_root
        self.fixed = config.fixed_workspace

    def _inside_root(self, path: Path) -> bool:
        if self.root is None:
            return True
        try:
            path.relative_to(self.root)
            return True
        except ValueError:
            return False

    def validate_existing(self, path: Path) -> Path:
        candidate = path.expanduser()
        if candidate.is_symlink():
            raise ValueError("I workspace non possono essere link simbolici.")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("Il percorso non è una directory.")
        if self.fixed is not None and resolved != self.fixed:
            raise ValueError("Il server è configurato per un solo workspace.")
        if not self._inside_root(resolved):
            raise ValueError("Il workspace è fuori dalla root autorizzata.")
        if self.root is not None and self.fixed is None and resolved.parent != self.root:
            raise ValueError("Sono selezionabili soltanto le cartelle di primo livello della root progetti.")
        return resolved

    def resolve_selection(self, raw_path: str) -> Path:
        value = raw_path.strip()
        if self.fixed is not None:
            if not value:
                return self.fixed
            candidate = Path(value).expanduser()
            if not candidate.is_absolute() and self.root is not None:
                candidate = self.root / candidate
            return self.validate_existing(candidate)

        if not value:
            raise ValueError("Seleziona un workspace valido.")
        candidate = Path(value).expanduser()
        if self.root is not None and not candidate.is_absolute():
            candidate = self.root / candidate
        return self.validate_existing(candidate)

    def project_target(self, raw_name: str) -> Path:
        if self.fixed is not None:
            raise ValueError("Il server è configurato per un solo workspace.")
        if self.root is None:
            raise ValueError("Configura prima la cartella root dei progetti.")
        name = validate_project_name(raw_name)
        target = self.root / name
        if target.exists() or target.is_symlink():
            raise ValueError("Esiste già un file o una cartella con questo nome.")
        return target

    def available_workspaces(self) -> list[dict[str, str]]:
        if self.fixed is not None:
            return [{"name": self.fixed.name, "value": str(self.fixed)}]
        if self.root is None:
            return []

        workspaces: list[dict[str, str]] = []
        try:
            entries = sorted(self.root.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            return []
        for item in entries:
            try:
                if item.name.startswith(".") or item.is_symlink() or not item.is_dir():
                    continue
                resolved = item.resolve(strict=True)
            except OSError:
                continue
            workspaces.append({"name": item.name, "value": str(resolved)})
        return workspaces
