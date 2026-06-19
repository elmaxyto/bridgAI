from __future__ import annotations

import secrets
import shutil
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path

from local_ai_bridge.core.models import ChangePlan
from local_ai_bridge.core.settings import SettingsStore
from local_ai_bridge.web.security import (
    AuthenticationRateLimitError,
    WebSecurityConfig,
    WorkspacePolicy,
    hash_recovery_code,
    normalize_recovery_code,
    verify_totp,
)


PLAN_TTL_SECONDS = 30 * 60
ARTIFACT_TTL_SECONDS = 60 * 60
AUTH_SESSION_TTL_SECONDS = 12 * 60 * 60
AUTH_FAILURE_WINDOW_SECONDS = 5 * 60
AUTH_FAILURE_LIMIT = 8


@dataclass(slots=True)
class PendingPlan:
    plan_id: str
    plan: ChangePlan
    created_at: float


@dataclass(slots=True)
class DownloadArtifact:
    artifact_id: str
    path: Path
    filename: str
    content_type: str
    created_at: float


@dataclass(slots=True)
class AuthSession:
    token: str
    created_at: float
    expires_at: float
    client_ip: str
    second_factor: str


class BridgeState:
    def __init__(
        self,
        *,
        security: WebSecurityConfig | None = None,
        initial_workspace: str | Path | None = None,
        workspace_root_locked: bool = False,
    ) -> None:
        self.security = security or WebSecurityConfig.build()
        self.workspace_policy = WorkspacePolicy(self.security)
        self.workspace_root_locked = bool(workspace_root_locked or self.security.fixed_workspace)
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self.workspace: Path | None = None
        self.pending_plan: PendingPlan | None = None
        self.artifacts: dict[str, DownloadArtifact] = {}
        self.auth_sessions: dict[str, AuthSession] = {}
        self.auth_failures: dict[str, list[float]] = {}
        self.csrf_token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self._sessions = None
        self._apply_service = None
        self._totp_last_counter = (
            self.settings.web_totp_last_counter
            if self.settings.web_totp_secret == (self.security.totp_secret or "")
            else -1
        )

        if self.security.workspace_root is not None and self.security.fixed_workspace is None:
            root_value = str(self.security.workspace_root)
            if self.settings.web_workspace_root != root_value:
                self.settings.web_workspace_root = root_value
                self.settings_store.save(self.settings)

        candidate: str | Path | None = initial_workspace or self.security.fixed_workspace
        if candidate is None and self.settings.last_workspace:
            candidate = self.settings.last_workspace
        if candidate is not None:
            try:
                self.workspace = self.workspace_policy.validate_existing(Path(candidate))
            except (OSError, ValueError):
                self.workspace = self.security.fixed_workspace

    @property
    def sessions(self):
        if self._sessions is None:
            from local_ai_bridge.core.sessions import SessionManager

            self._sessions = SessionManager()
        return self._sessions

    @property
    def apply_service(self):
        if self._apply_service is None:
            from local_ai_bridge.services.apply import ApplyService

            self._apply_service = ApplyService(self.sessions)
        return self._apply_service

    @property
    def can_manage_projects(self) -> bool:
        return self.security.fixed_workspace is None and self.security.workspace_root is not None

    def require_workspace(self) -> Path:
        if self.workspace is None:
            raise ValueError("Seleziona prima un workspace valido.")
        return self.workspace

    def require_project_root(self) -> Path:
        if self.security.fixed_workspace is not None:
            raise ValueError("Il server è configurato per un solo workspace.")
        if self.security.workspace_root is None:
            raise ValueError("Configura prima la cartella root dei progetti.")
        return self.security.workspace_root

    def _save_settings(self) -> None:
        self.settings_store.save(self.settings)

    def auth_info(self, client_ip: str) -> dict[str, object]:
        return {
            "requires_authentication": self.security.requires_authentication,
            "two_factor_enabled": self.security.two_factor_enabled,
            "two_factor_required": self.security.requires_two_factor(client_ip),
            "two_factor_local_bypass": self.security.totp_local_bypass,
        }

    def _drop_expired_auth_sessions(self) -> None:
        now = time.monotonic()
        for token in [
            token
            for token, session in self.auth_sessions.items()
            if session.expires_at <= now
        ]:
            self.auth_sessions.pop(token, None)

    def _session_from_header(self, header_value: str | None) -> AuthSession | None:
        if not header_value or not header_value.startswith("Bearer "):
            return None
        token = header_value[7:].strip()
        if not token:
            return None
        with self.lock:
            self._drop_expired_auth_sessions()
            for stored_token, session in self.auth_sessions.items():
                if secrets.compare_digest(stored_token, token):
                    return session
        return None

    def accepts_api_authorization(self, header_value: str | None, client_ip: str) -> bool:
        if not self.security.requires_authentication:
            return True
        if self.security.accepts_static_token(header_value):
            return True
        if self._session_from_header(header_value) is not None:
            return True
        if self.security.requires_two_factor(client_ip):
            return False
        return self.security.accepts_primary_authorization(header_value)

    def _prune_auth_failures(self, client_ip: str) -> list[float]:
        now = time.monotonic()
        recent = [
            timestamp
            for timestamp in self.auth_failures.get(client_ip, [])
            if now - timestamp <= AUTH_FAILURE_WINDOW_SECONDS
        ]
        if recent:
            self.auth_failures[client_ip] = recent
        else:
            self.auth_failures.pop(client_ip, None)
        return recent

    def _check_auth_rate_limit(self, client_ip: str) -> None:
        with self.lock:
            recent = self._prune_auth_failures(client_ip)
            if len(recent) >= AUTH_FAILURE_LIMIT:
                raise AuthenticationRateLimitError(
                    "Troppi tentativi di accesso. Attendi alcuni minuti e riprova."
                )

    def _record_auth_failure(self, client_ip: str) -> None:
        with self.lock:
            recent = self._prune_auth_failures(client_ip)
            recent.append(time.monotonic())
            self.auth_failures[client_ip] = recent

    def _record_auth_success(self, client_ip: str) -> None:
        with self.lock:
            self.auth_failures.pop(client_ip, None)

    def _consume_recovery_code(self, code: str) -> bool:
        # Recovery codes belong to the secret saved by the desktop settings.
        # When the server is configured with an environment-only secret, do not
        # accidentally accept recovery codes generated for a different secret.
        if self.settings.web_totp_secret != (self.security.totp_secret or ""):
            return False
        normalized = normalize_recovery_code(code)
        if len(normalized) != 12:
            return False
        try:
            candidate_hash = hash_recovery_code(normalized)
        except ValueError:
            return False
        with self.lock:
            for index, stored_hash in enumerate(self.settings.web_totp_recovery_hashes):
                if secrets.compare_digest(candidate_hash, str(stored_hash)):
                    del self.settings.web_totp_recovery_hashes[index]
                    self._save_settings()
                    return True
        return False

    def _verify_second_factor(self, code: str) -> str:
        secret = self.security.totp_secret
        if secret is None:
            return "not-required"
        normalized = (code or "").strip()
        if self._consume_recovery_code(normalized):
            return "recovery"
        with self.lock:
            counter = verify_totp(
                secret,
                normalized,
                valid_window=1,
                last_counter=self._totp_last_counter,
            )
            if counter is None:
                raise PermissionError("Codice di autenticazione a due fattori non valido o già utilizzato.")
            self._totp_last_counter = counter
            if self.settings.web_totp_secret == secret:
                self.settings.web_totp_last_counter = counter
                self._save_settings()
        return "totp"

    def create_auth_session(
        self,
        authorization_header: str | None,
        second_factor_code: str,
        client_ip: str,
    ) -> AuthSession:
        self._check_auth_rate_limit(client_ip)
        if not self.security.accepts_primary_authorization(authorization_header):
            self._record_auth_failure(client_ip)
            raise PermissionError("Username o password non validi.")
        try:
            factor = (
                self._verify_second_factor(second_factor_code)
                if self.security.requires_two_factor(client_ip)
                else "local-bypass" if self.security.two_factor_enabled else "password"
            )
        except PermissionError:
            self._record_auth_failure(client_ip)
            raise
        self._record_auth_success(client_ip)
        now = time.monotonic()
        session = AuthSession(
            token=secrets.token_urlsafe(32),
            created_at=now,
            expires_at=now + AUTH_SESSION_TTL_SECONDS,
            client_ip=client_ip,
            second_factor=factor,
        )
        with self.lock:
            self._drop_expired_auth_sessions()
            self.auth_sessions[session.token] = session
        return session

    def revoke_auth_session(self, authorization_header: str | None) -> None:
        if not authorization_header or not authorization_header.startswith("Bearer "):
            return
        token = authorization_header[7:].strip()
        with self.lock:
            for stored_token in list(self.auth_sessions):
                if secrets.compare_digest(stored_token, token):
                    self.auth_sessions.pop(stored_token, None)
                    break

    def set_workspace(self, raw_path: str) -> Path:
        path = self.workspace_policy.resolve_selection(raw_path)
        with self.lock:
            self.workspace = path
            self.pending_plan = None
            self.settings.last_workspace = str(path)
            self._save_settings()
        return path

    def set_workspace_root(self, raw_path: str) -> Path:
        if self.security.fixed_workspace is not None:
            raise ValueError("Il server è configurato per un solo workspace.")
        if self.workspace_root_locked:
            raise ValueError("La root progetti è bloccata dalla configurazione di avvio del server.")
        candidate = Path(raw_path.strip()).expanduser()
        if not raw_path.strip():
            raise ValueError("Inserisci la cartella root dei progetti.")
        if candidate.is_symlink():
            raise ValueError("La root progetti non può essere un link simbolico.")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("La root progetti non è una directory valida.")

        with self.lock:
            self.security = replace(self.security, workspace_root=resolved)
            self.workspace_policy = WorkspacePolicy(self.security)
            if self.workspace is not None:
                try:
                    self.workspace = self.workspace_policy.validate_existing(self.workspace)
                except (OSError, ValueError):
                    self.workspace = None
                    self.settings.last_workspace = ""
            self.pending_plan = None
            self.settings.web_workspace_root = str(resolved)
            self._save_settings()
        return resolved

    def workspace_choices(self) -> list[dict[str, str]]:
        return self.workspace_policy.available_workspaces()

    def create_project(self, name: str, *, initialize_git: bool = True) -> tuple[Path, str]:
        from local_ai_bridge.services.git import git_init

        with self.lock:
            target = self.workspace_policy.project_target(name)
            try:
                target.mkdir(mode=0o755)
                output = git_init(target) if initialize_git else "Cartella progetto creata."
            except Exception:
                if target.exists() and target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                raise
            self.workspace = target.resolve(strict=True)
            self.pending_plan = None
            self.settings.last_workspace = str(self.workspace)
            self._save_settings()
            return self.workspace, output

    def clone_project(self, repository_url: str, name: str = "") -> tuple[Path, str]:
        from local_ai_bridge.services.git_clone import clone_destination_name, clone_repository

        destination_name = name.strip() or clone_destination_name(repository_url)
        with self.lock:
            target = self.workspace_policy.project_target(destination_name)
            output = clone_repository(repository_url, target)
            self.workspace = self.workspace_policy.validate_existing(target)
            self.pending_plan = None
            self.settings.last_workspace = str(self.workspace)
            self._save_settings()
            return self.workspace, output

    def register_plan(self, plan: ChangePlan) -> str:
        workspace = self.require_workspace()
        if plan.workspace.resolve() != workspace.resolve():
            raise ValueError("Il piano non appartiene al workspace corrente.")
        plan_id = secrets.token_urlsafe(18)
        with self.lock:
            self.pending_plan = PendingPlan(plan_id, plan, time.monotonic())
        return plan_id

    def get_plan(self, plan_id: str) -> ChangePlan:
        with self.lock:
            pending = self.pending_plan
            if pending is None or not secrets.compare_digest(pending.plan_id, plan_id):
                raise ValueError("Piano non trovato o sostituito da un'analisi successiva.")
            if time.monotonic() - pending.created_at > PLAN_TTL_SECONDS:
                self.pending_plan = None
                raise ValueError("Il piano è scaduto. Analizza nuovamente la modifica.")
            if pending.plan.workspace.resolve() != self.require_workspace().resolve():
                self.pending_plan = None
                raise ValueError("Il workspace è cambiato dopo l'analisi.")
            return pending.plan

    def clear_plan(self, plan_id: str) -> None:
        with self.lock:
            if self.pending_plan and secrets.compare_digest(self.pending_plan.plan_id, plan_id):
                self.pending_plan = None

    def register_artifact(
        self,
        path: Path,
        *,
        filename: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> DownloadArtifact:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise ValueError("Il file da scaricare non è valido.")
        artifact = DownloadArtifact(
            artifact_id=secrets.token_urlsafe(18),
            path=resolved,
            filename=filename or resolved.name,
            content_type=content_type,
            created_at=time.monotonic(),
        )
        with self.lock:
            self._drop_expired_artifacts()
            self.artifacts[artifact.artifact_id] = artifact
        return artifact

    def get_artifact(self, artifact_id: str) -> DownloadArtifact:
        with self.lock:
            self._drop_expired_artifacts()
            artifact = self.artifacts.get(artifact_id)
            if artifact is None or not artifact.path.is_file():
                raise FileNotFoundError("File non trovato o link di download scaduto.")
            return artifact

    def _drop_expired_artifacts(self) -> None:
        now = time.monotonic()
        expired = [
            key
            for key, artifact in self.artifacts.items()
            if now - artifact.created_at > ARTIFACT_TTL_SECONDS
        ]
        for key in expired:
            self.artifacts.pop(key, None)
