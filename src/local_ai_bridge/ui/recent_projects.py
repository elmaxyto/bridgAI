from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QMenu, QToolBar, QToolButton

from local_ai_bridge.core.settings import remember_recent_workspace
from local_ai_bridge.i18n import tr as _


def _recent_project_label(path: Path) -> str:
    name = path.name or str(path)
    parent = str(path.parent)
    return f"{name} — {parent}"


class RecentProjectsMixin:
    """Toolbar menu and persistence helpers for recently opened projects."""

    def add_recent_projects_widget(self, toolbar: QToolBar) -> None:
        self.recent_projects_menu = QMenu(self)
        self.recent_projects_menu.aboutToShow.connect(self._refresh_recent_projects_menu)

        self.recent_projects_button = QToolButton(self)
        self.recent_projects_button.setText(_('Recenti'))
        self.recent_projects_button.setToolTip(
            _('Apri rapidamente uno dei progetti usati di recente.')
        )
        self.recent_projects_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.recent_projects_button.setMenu(self.recent_projects_menu)
        toolbar.addWidget(self.recent_projects_button)

    def _remember_recent_workspace(self, path: Path) -> None:
        self.settings.recent_workspaces = remember_recent_workspace(
            self.settings.recent_workspaces,
            path,
        )
        self.settings_store.save(self.settings)
        if hasattr(self, 'recent_projects_menu'):
            self._refresh_recent_projects_menu()

    def _refresh_recent_projects_menu(self) -> None:
        menu = self.recent_projects_menu
        menu.clear()
        recent = list(self.settings.recent_workspaces)
        if not recent:
            empty_action = menu.addAction(_('Nessun progetto recente'))
            empty_action.setEnabled(False)
            return

        current_workspace = getattr(self, 'workspace', None)
        for raw_path in recent:
            path = Path(raw_path)
            label = _recent_project_label(path)
            available = path.is_dir()
            is_current = current_workspace == path
            if is_current:
                label = _('{name} (aperto)').format(name=label)
            elif not available:
                label = _('{name} (non disponibile)').format(name=label)

            action = menu.addAction(label)
            action.setToolTip(str(path))
            action.setEnabled(available and not is_current)
            if available and not is_current:
                action.triggered.connect(
                    lambda _checked=False, selected=path: self._open_recent_workspace(selected)
                )

        menu.addSeparator()
        clear_action = menu.addAction(_('Cancella elenco recenti'))
        clear_action.triggered.connect(self._clear_recent_workspaces)

    def _open_recent_workspace(self, path: Path) -> None:
        if not path.is_dir():
            self.settings.recent_workspaces = [
                item for item in self.settings.recent_workspaces if item != str(path)
            ]
            self.settings_store.save(self.settings)
            self._refresh_recent_projects_menu()
            QMessageBox.warning(
                self,
                _('Progetto recente non disponibile'),
                _('La cartella del progetto recente non esiste più:\n{path}').format(path=path),
            )
            return
        self.set_workspace(path)

    def _clear_recent_workspaces(self) -> None:
        self.settings.recent_workspaces = []
        self.settings_store.save(self.settings)
        self._refresh_recent_projects_menu()
        self._show_status(_('Elenco dei progetti recenti cancellato.'))
