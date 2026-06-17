from __future__ import annotations

import secrets
import shutil
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path

from local_ai_bridge.core.models import ChangePlan
from local_ai_bridge.core.settings import SettingsStore
from local_ai_bridge.web.security import WebSecurityConfig, WorkspacePolicy


PLAN_TTL_SECONDS = 30 * 60
ARTIFACT_TTL_SECONDS = 60 * 60


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
        self.csrf_token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self._sessions = None
        self._apply_service = None

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
