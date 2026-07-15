from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from local_ai_bridge.i18n import tr as _


SIMPLE_MODE_WIDTH = 800
SIMPLE_MODE_HEIGHT = 900
OPERATIONS_MODE_WIDTH = 960
OPERATIONS_MODE_HEIGHT = 720


class SimpleModeManager:
    """Apply the tab, widget, and label changes for BridgAI desktop modes."""

    def __init__(self, window) -> None:
        self.window = window

    def apply(self, state: dict[str, Any]) -> None:
        operations = bool(state.get('operations'))
        if operations:
            self._apply_operations_mode()
            return

        simple = bool(state.get('simple'))
        markdown_files = bool(state.get('markdown_files'))
        text_updates = bool(state.get('text_updates'))
        drive_zip = bool(state.get('drive_zip'))
        update_zip_directory = str(state.get('update_zip_directory', ''))

        self._apply_window_size(simple)
        self._apply_tab_visibility(simple, text_updates)
        self._apply_workflow_visibility(simple, text_updates)
        self._apply_response_copy(simple, markdown_files, drive_zip)
        self._apply_change_visibility(simple, text_updates, update_zip_directory)
        self._apply_settings_visibility(simple, text_updates)
        self._apply_report_button(simple)
        self._ensure_allowed_tab(simple, text_updates)

    def _apply_operations_mode(self) -> None:
        self._set_tab_visible(self.window.operations_tab, True)
        self.window.project_panel.setVisible(True)
        for tab in (
            self.window.workflow_tab,
            self.window.changes_tab,
            self.window.tests_tab,
            self.window.publication_tab,
            self.window.advanced_tab,
        ):
            self._set_tab_visible(tab, False)
        self._set_tab_visible(self.window.settings_tab, True)
        self._set_tab_text(self.window.settings_tab, _('Impostazioni'))
        if self.window.tabs.currentWidget() is not self.window.settings_tab:
            self.window.tabs.setCurrentWidget(self.window.operations_tab)
        if self.window.isFullScreen() or self.window.isMaximized():
            self.window.showNormal()
        self.window.resize(OPERATIONS_MODE_WIDTH, OPERATIONS_MODE_HEIGHT)

    def _apply_window_size(self, simple: bool) -> None:
        if simple:
            if self.window.isFullScreen() or self.window.isMaximized():
                self.window.showNormal()
            self.window.resize(SIMPLE_MODE_WIDTH, SIMPLE_MODE_HEIGHT)
            return
        if self.window.isVisible():
            self.window.showMaximized()
        else:
            QTimer.singleShot(0, self.window.showMaximized)

    def _apply_tab_visibility(self, simple: bool, text_updates: bool) -> None:
        self._set_tab_visible(self.window.operations_tab, False)
        self.window.project_panel.setVisible(not simple)
        self._set_tab_visible(self.window.changes_tab, not simple or text_updates)
        self._set_tab_text(
            self.window.changes_tab,
            _('Anteprima e applicazione')
            if text_updates else _('2. ZIP, diff e applicazione'),
        )
        self._set_tab_visible(self.window.publication_tab, True)
        self._set_tab_text(self.window.publication_tab, _('Pubblicazione'))
        self._set_tab_visible(self.window.tests_tab, not simple)
        self._set_tab_visible(self.window.advanced_tab, not simple)
        self._set_tab_visible(self.window.workflow_tab, True)
        self._set_tab_text(
            self.window.workflow_tab,
            _('Assistente') if simple else _('1. Report e risposta AI'),
        )
        self._set_tab_visible(self.window.settings_tab, True)
        self._set_tab_text(
            self.window.settings_tab,
            _('Preferenze') if simple else _('Impostazioni'),
        )

    def _apply_workflow_visibility(self, simple: bool, text_updates: bool) -> None:
        visibility_rules = {
            simple: (
                self.window.simple_welcome,
                self.window.simple_subtitle,
                self.window.simple_restart_button,
            ),
            not simple: (
                self.window.report_edit,
                self.window.prompt_preset_label,
                self.window.prompt_preset_combo,
                self.window.target_edit,
            ),
        }
        for visible, widgets in visibility_rules.items():
            for widget in widgets:
                widget.setVisible(visible)

        self.window.simple_finish_hint.setVisible(simple and not text_updates)
        self.window.simple_finish_hint.setText(
            _('3  Quando ricevi uno ZIP dall’AI, salvalo nella cartella scelta e premi “Applica aggiornamento”. Prima dell’applicazione verrà sempre mostrata un’anteprima.')
        )
        for button in self.window.report_extra_buttons:
            button.setVisible(not simple)
        self.window._refresh_simple_provider_buttons()
        label = self.window.target_form.labelForField(self.window.target_edit)
        if label is not None:
            label.setVisible(not simple)
        self.window.restart_action.setVisible(not simple)

    def _apply_response_copy(
        self,
        simple: bool,
        markdown_files: bool,
        drive_zip: bool,
    ) -> None:
        if simple:
            response_title = _('Incolla la richiesta di file dell’AI')
            if markdown_files:
                response_description = _(
                    'Copia la risposta con la riga #scarica, poi prepara il Markdown con i file completi.'
                )
            elif drive_zip:
                response_description = _(
                    'Copia la risposta con la riga #scarica, poi prepara lo ZIP nella cartella Google Drive.'
                )
            else:
                response_description = _(
                    'Copia la risposta con la riga #scarica, poi prepara lo ZIP con i file richiesti.'
                )
            response_placeholder = _('Incolla qui la risposta dell’AI che contiene #scarica...')
        else:
            response_title = _('Incolla la risposta dell’AI')
            response_description = _(
                'Torna qui e incolla tutto il messaggio ricevuto, senza modificarlo.'
            )
            response_placeholder = _('Incolla qui la risposta completa dell’AI...')

        self.window.response_step_header.title_label.setText(response_title)
        self.window.response_step_header.description_label.setText(response_description)
        self.window.response_edit.setPlaceholderText(response_placeholder)
        self.window.simple_prepare_files_button.setText(
            _('Prepara Markdown')
            if markdown_files else _('Prepara ZIP su Google Drive')
            if drive_zip else _('Prepara ZIP richiesto')
        )

    def _apply_change_visibility(
        self,
        simple: bool,
        text_updates: bool,
        update_zip_directory: str,
    ) -> None:
        self.window.text_result_group.setVisible(text_updates)
        self.window.markdown_result_group.setVisible(False)
        for button in self.window.response_action_buttons:
            button.setVisible(not simple)
        for button in self.window.simple_response_buttons:
            button.setVisible(simple)
        self.window.simple_apply_zip_button.setVisible(simple and not text_updates)
        self.window.simple_patch_directory_button.setVisible(
            simple and not text_updates and not bool(update_zip_directory.strip())
        )
        self.window.update_zip_settings_group.setVisible(not text_updates)
        self.window.change_source_group.setVisible(not simple)
        self.window.change_rollback_button.setVisible(not simple)

    def _apply_settings_visibility(self, simple: bool, text_updates: bool) -> None:
        self.window.other_llm_settings_group.setVisible(not simple)
        for group in getattr(self.window, 'advanced_settings_groups', []):
            group.setVisible(not simple)
        self.window.gemini_drive_settings_group.setVisible(not simple)
        self.window.markdown_exchange_settings_group.setVisible(not simple)
        self.window.textual_file_operations_settings_group.setVisible(not simple)
        self.window.update_zip_settings_group.setVisible(not text_updates)

    def _apply_report_button(self, simple: bool) -> None:
        self.window.report_button.setText(
            _('Prepara richiesta per l’AI') if simple else _('Genera Super-Report')
        )

    def _ensure_allowed_tab(self, simple: bool, text_updates: bool) -> None:
        allowed_simple_tabs = (
            (
                self.window.workflow_tab,
                self.window.publication_tab,
                self.window.settings_tab,
                self.window.changes_tab,
            )
            if text_updates
            else (
                self.window.workflow_tab,
                self.window.publication_tab,
                self.window.settings_tab,
            )
        )
        if simple and self.window.tabs.currentWidget() not in allowed_simple_tabs:
            self.window.tabs.setCurrentWidget(self.window.workflow_tab)

    def _set_tab_visible(self, tab, visible: bool) -> None:
        index = self.window.tabs.indexOf(tab)
        if index >= 0:
            self.window.tabs.setTabVisible(index, visible)

    def _set_tab_text(self, tab, text: str) -> None:
        index = self.window.tabs.indexOf(tab)
        if index >= 0:
            self.window.tabs.setTabText(index, text)
