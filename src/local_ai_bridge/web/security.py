from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import struct
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path


LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_INVALID_PROJECT_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_PRIVATE_CLIENT_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)
_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class AuthenticationRateLimitError(PermissionError):
    """Raised when too many authentication attempts were made."""


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


def _ip_address(value: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    raw = (value or "").strip().strip("[]")
    if not raw:
        return None
    if "%" in raw:
        raw = raw.split("%", 1)[0]
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def is_loopback_address(value: str | None) -> bool:
    address = _ip_address(value)
    return bool(address and address.is_loopback)


def is_private_client_address(value: str | None) -> bool:
    address = _ip_address(value)
    if address is None:
        return False
    return any(address in network for network in _PRIVATE_CLIENT_NETWORKS)


def client_address_from_proxy(
    direct_address: str,
    forwarded_for: str | None = None,
    real_ip: str | None = None,
) -> str:
    """Return the client IP, trusting proxy headers only from a loopback proxy.

    The final X-Forwarded-For entry is used because a correctly configured local
    reverse proxy appends or overwrites the real peer address at the right side.
    Direct clients cannot spoof this path because headers are ignored unless the
    immediate TCP peer is loopback.
    """

    if not is_loopback_address(direct_address):
        return direct_address
    if forwarded_for:
        candidate = forwarded_for.rsplit(",", 1)[-1].strip()
        if _ip_address(candidate) is not None:
            return candidate
    if real_ip and _ip_address(real_ip) is not None:
        return real_ip.strip()
    return direct_address


def generate_totp_secret(byte_count: int = 20) -> str:
    if byte_count < 20:
        raise ValueError("Il segreto TOTP deve contenere almeno 160 bit.")
    return base64.b32encode(secrets.token_bytes(byte_count)).decode("ascii").rstrip("=")


def normalize_totp_secret(value: str) -> str:
    secret = re.sub(r"[\s-]+", "", value or "").upper().rstrip("=")
    if not secret:
        raise ValueError("Segreto TOTP mancante.")
    padding = "=" * ((8 - len(secret) % 8) % 8)
    try:
        decoded = base64.b32decode(secret + padding, casefold=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Segreto TOTP non valido.") from exc
    if len(decoded) < 20:
        raise ValueError("Il segreto TOTP deve contenere almeno 160 bit.")
    return secret


def _totp_key(secret: str) -> bytes:
    normalized = normalize_totp_secret(secret)
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    return base64.b32decode(normalized + padding, casefold=True)


def totp_at(
    secret: str,
    for_time: float | int | None = None,
    *,
    interval: int = 30,
    digits: int = 6,
    digest: str = "sha1",
) -> str:
    if interval <= 0:
        raise ValueError("Intervallo TOTP non valido.")
    if not 6 <= digits <= 8:
        raise ValueError("Il codice TOTP deve contenere da 6 a 8 cifre.")
    timestamp = time.time() if for_time is None else float(for_time)
    counter = int(timestamp // interval)
    mac = hmac.new(_totp_key(secret), struct.pack(">Q", counter), digest).digest()
    offset = mac[-1] & 0x0F
    binary = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10 ** digits)).zfill(digits)


def verify_totp(
    secret: str,
    code: str,
    *,
    for_time: float | int | None = None,
    valid_window: int = 1,
    last_counter: int = -1,
    interval: int = 30,
) -> int | None:
    candidate = re.sub(r"\s+", "", code or "")
    if not re.fullmatch(r"\d{6}", candidate):
        return None
    timestamp = time.time() if for_time is None else float(for_time)
    current_counter = int(timestamp // interval)
    for offset in range(-max(0, valid_window), max(0, valid_window) + 1):
        counter = current_counter + offset
        if counter <= last_counter or counter < 0:
            continue
        expected = totp_at(secret, counter * interval, interval=interval)
        if hmac.compare_digest(candidate, expected):
            return counter
    return None


def totp_provisioning_uri(secret: str, account_name: str, issuer: str = "BridgAI") -> str:
    normalized = normalize_totp_secret(secret)
    account = (account_name or "utente").strip() or "utente"
    label = urllib.parse.quote(f"{issuer}:{account}", safe="")
    query = urllib.parse.urlencode(
        {
            "secret": normalized,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": "6",
            "period": "30",
        }
    )
    return f"otpauth://totp/{label}?{query}"


def generate_recovery_codes(count: int = 8) -> tuple[str, ...]:
    if not 4 <= count <= 20:
        raise ValueError("Numero di codici di recupero non valido.")
    codes: list[str] = []
    while len(codes) < count:
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(12))
        code = "-".join(raw[index:index + 4] for index in range(0, 12, 4))
        if code not in codes:
            codes.append(code)
    return tuple(codes)


def normalize_recovery_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def hash_recovery_code(value: str) -> str:
    normalized = normalize_recovery_code(value)
    if len(normalized) != 12:
        raise ValueError("Codice di recupero non valido.")
    return hashlib.sha256(f"bridgai-recovery:{normalized}".encode("ascii")).hexdigest()


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
    totp_secret: str | None = None
    totp_local_bypass: bool = False
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
        totp_secret: str | None = None,
        totp_local_bypass: bool = False,
        workspace_root: str | Path | None = None,
        fixed_workspace: str | Path | None = None,
    ) -> "WebSecurityConfig":
        normalized_token = (auth_token or "").strip() or None
        normalized_username = (username or "").strip() or None
        normalized_password_hash = (password_hash or "").strip() or None
        normalized_totp_secret = (totp_secret or "").strip() or None
        if bool(normalized_username) != bool(normalized_password_hash):
            raise ValueError("Username e password devono essere configurati insieme.")
        if normalized_totp_secret is not None:
            if normalized_password_hash is None:
                raise ValueError("La 2FA TOTP richiede username e password.")
            normalized_totp_secret = normalize_totp_secret(normalized_totp_secret)
        elif totp_local_bypass:
            raise ValueError("L'esclusione 2FA per la rete locale richiede una 2FA configurata.")
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
            totp_secret=normalized_totp_secret,
            totp_local_bypass=bool(totp_local_bypass),
            workspace_root=root,
            fixed_workspace=fixed,
        )

    @property
    def remote_mode(self) -> bool:
        return not is_loopback_host(self.host)

    @property
    def requires_authentication(self) -> bool:
        return self.auth_token is not None or self.password_hash is not None

    @property
    def two_factor_enabled(self) -> bool:
        return self.totp_secret is not None

    def requires_two_factor(self, client_ip: str | None) -> bool:
        if not self.two_factor_enabled:
            return False
        return not (self.totp_local_bypass and is_private_client_address(client_ip))

    def accepts_static_token(self, header_value: str | None) -> bool:
        if self.auth_token is None or not header_value or not header_value.startswith("Bearer "):
            return False
        return hmac.compare_digest(header_value[7:].strip(), self.auth_token)

    def accepts_primary_authorization(self, header_value: str | None) -> bool:
        if self.username is None or self.password_hash is None or not header_value:
            return False
        if not header_value.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header_value[6:].strip(), validate=True).decode("utf-8")
            candidate_username, candidate_password = decoded.split(":", 1)
        except (ValueError, UnicodeDecodeError):
            return False
        return hmac.compare_digest(candidate_username, self.username) and verify_password(
            candidate_password,
            self.password_hash,
        )

    def accepts_authorization(self, header_value: str | None) -> bool:
        """Backward-compatible primary/static authorization check.

        Full API authorization with TOTP sessions is handled by BridgeState.
        """

        if not self.requires_authentication:
            return True
        return self.accepts_static_token(header_value) or self.accepts_primary_authorization(header_value)


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
