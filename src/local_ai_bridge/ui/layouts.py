from __future__ import annotations

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.tabs import (
    build_advanced_tab,
    build_changes_tab,
    build_publication_tab,
    build_settings_tab,
    build_tests_tab,
    build_workflow_tab,
)
from local_ai_bridge.ui.tabs.advanced import _build_ai_context_group
from local_ai_bridge.ui.widgets import (
    ProviderButton,
    ToggleSwitch,
    _button,
    _provider_button,
    _step_header,
)
from PySide6.QtCore import QDir, Qt
from PySide6.QtWidgets import QFileSystemModel, QLabel, QSplitter, QTabWidget, QTreeView, QVBoxLayout, QWidget

__all__ = [
    "build_central_ui",
    "build_workflow_tab",
    "build_changes_tab",
    "build_publication_tab",
    "build_tests_tab",
    "build_advanced_tab",
    "build_settings_tab",
    "ToggleSwitch",
    "ProviderButton",
]

def build_central_ui(window) -> QSplitter:
    splitter = QSplitter(Qt.Horizontal)
    window.project_panel = QWidget()
    left = window.project_panel
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(6, 6, 3, 6)
    left_layout.addWidget(QLabel(_('File del progetto')))
    window.file_model = QFileSystemModel(window)
    window.file_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
    window.file_tree = QTreeView()
    window.file_tree.setModel(window.file_model)
    window.file_tree.doubleClicked.connect(window._tree_double_clicked)
    for column in range(1, 4):
        window.file_tree.hideColumn(column)
    left_layout.addWidget(window.file_tree)
    splitter.addWidget(left)
    window.tabs = QTabWidget()
    window.workflow_tab = build_workflow_tab(window)
    window.changes_tab = build_changes_tab(window)
    window.tests_tab = build_tests_tab(window)
    window.publication_tab = build_publication_tab(window)
    window.advanced_tab = build_advanced_tab(window)
    window.settings_tab = build_settings_tab(window)
    window.tabs.addTab(window.workflow_tab, _('1. Report e risposta AI'))
    window.tabs.addTab(window.changes_tab, _('2. ZIP, diff e applicazione'))
    window.tabs.addTab(window.tests_tab, _('3. Test, Git e GitHub'))
    window.tabs.addTab(window.publication_tab, _('Pubblicazione'))
    window.tabs.addTab(window.advanced_tab, _('Avanzato'))
    window.tabs.addTab(window.settings_tab, _('Impostazioni'))
    splitter.addWidget(window.tabs)
    splitter.setSizes([320, 1060])
    return splitter
