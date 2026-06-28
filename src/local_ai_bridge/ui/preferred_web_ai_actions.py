from __future__ import annotations

from PySide6.QtWidgets import QInputDialog

from local_ai_bridge.core.settings import (
    PREFERRED_WEB_AI_CHATGPT,
    PREFERRED_WEB_AI_CLAUDE,
    PREFERRED_WEB_AI_CUSTOM,
    PREFERRED_WEB_AI_GEMINI,
    PREFERRED_WEB_AI_VALUES,
    preferred_web_ai_exchange_formats,
)
from local_ai_bridge.i18n import tr as _


class PreferredWebAIActionsMixin:
    def _refresh_simple_provider_buttons(self) -> None:
        buttons = {
            PREFERRED_WEB_AI_CHATGPT: getattr(self, "simple_chatgpt_button", None),
            PREFERRED_WEB_AI_CLAUDE: getattr(self, "simple_claude_button", None),
            PREFERRED_WEB_AI_GEMINI: getattr(self, "simple_gemini_button", None),
        }
        preferred = self.settings.preferred_web_ai
        selected = [
            button
            for name, button in buttons.items()
            if button is not None
            and (preferred == PREFERRED_WEB_AI_CUSTOM or name == preferred)
        ]
        self.simple_report_buttons = selected
        simple = bool(self.settings.simple_mode)
        for name, button in buttons.items():
            if button is not None:
                button.setVisible(
                    simple
                    and (preferred == PREFERRED_WEB_AI_CUSTOM or name == preferred)
                )

    def refresh_preferred_web_ai_settings(self) -> None:
        combo = getattr(self, "preferred_web_ai_combo", None)
        if combo is not None:
            self._set_combo_value(combo, self.settings.preferred_web_ai)
        flow_label = getattr(self, "preferred_web_ai_flow_label", None)
        if flow_label is not None:
            requested = _("Markdown") if self.settings.markdown_exchange_mode else "ZIP"
            updates = (
                _("File Markdown di aggiornamento")
                if self.settings.textual_file_operations_mode
                else "ZIP"
            )
            flow_label.setText(
                _("Flusso attivo: {requested} → {updates}.").format(
                    requested=requested,
                    updates=updates,
                )
            )
        self._refresh_simple_provider_buttons()

    def choose_custom_exchange_flow(self) -> tuple[bool, bool] | None:
        choices = (
            ("ZIP → ZIP", (False, False)),
            (_("ZIP → File Markdown di aggiornamento"), (False, True)),
            (_("Markdown → ZIP"), (True, False)),
            (_("Markdown → File Markdown di aggiornamento"), (True, True)),
        )
        current = (
            bool(self.settings.markdown_exchange_mode),
            bool(self.settings.textual_file_operations_mode),
        )
        current_index = next(
            (index for index, (_label, value) in enumerate(choices) if value == current),
            0,
        )
        selected, accepted = QInputDialog.getItem(
            self,
            _("Flusso personalizzato"),
            _("Scegli il flusso di scambio:"),
            [label for label, _value in choices],
            current_index,
            False,
        )
        if not accepted:
            return None
        return next(value for label, value in choices if label == selected)

    def set_preferred_web_ai(
        self,
        value: object,
        custom_flow: tuple[bool, bool] | None = None,
    ) -> None:
        preferred = str(value)
        if preferred not in PREFERRED_WEB_AI_VALUES:
            return
        formats = preferred_web_ai_exchange_formats(preferred)
        if preferred == PREFERRED_WEB_AI_CUSTOM:
            formats = (
                custom_flow
                if custom_flow is not None
                else self.choose_custom_exchange_flow()
            )
            if formats is None:
                self.refresh_preferred_web_ai_settings()
                return
        self.settings.preferred_web_ai = preferred
        (
            self.settings.markdown_exchange_mode,
            self.settings.textual_file_operations_mode,
        ) = formats
        self.settings_store.save(self.settings)
        if getattr(self, "requested_files_format_combo", None) is not None:
            self.refresh_markdown_exchange_settings()
        if getattr(self, "update_format_combo", None) is not None:
            self.refresh_textual_file_operations_settings()
        self.apply_simple_mode()
        self.refresh_preferred_web_ai_settings()
        model_names = {
            PREFERRED_WEB_AI_CHATGPT: "ChatGPT",
            PREFERRED_WEB_AI_CLAUDE: "Claude",
            PREFERRED_WEB_AI_GEMINI: "Gemini",
            PREFERRED_WEB_AI_CUSTOM: _("Personalizzato"),
        }
        self._show_status(
            _("Modello preferito salvato: {model}.").format(
                model=model_names[preferred]
            )
        )
