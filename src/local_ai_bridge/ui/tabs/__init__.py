"""Builders for the main application tabs."""

from local_ai_bridge.ui.tabs.advanced import _build_ai_context_group, build_advanced_tab
from local_ai_bridge.ui.tabs.changes import build_changes_tab
from local_ai_bridge.ui.tabs.publication import build_publication_tab
from local_ai_bridge.ui.tabs.settings import build_settings_tab
from local_ai_bridge.ui.tabs.tests import build_tests_tab
from local_ai_bridge.ui.tabs.workflow import build_workflow_tab

__all__ = [
    "build_workflow_tab",
    "build_changes_tab",
    "build_publication_tab",
    "build_tests_tab",
    "build_advanced_tab",
    "build_settings_tab",
]
