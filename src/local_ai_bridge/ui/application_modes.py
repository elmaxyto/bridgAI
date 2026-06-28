from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from local_ai_bridge.core.settings import (
    DEVELOPMENT_MODE,
    OPERATIONS_MODE,
    PREFERRED_WEB_AI_CHATGPT,
    PREFERRED_WEB_AI_CLAUDE,
    PREFERRED_WEB_AI_CUSTOM,
    PREFERRED_WEB_AI_GEMINI,
)
from local_ai_bridge.i18n import tr as _


def choose_initial_setup(
    parent: QWidget | None = None,
    current_mode: str = DEVELOPMENT_MODE,
    current_provider: str = PREFERRED_WEB_AI_CHATGPT,
    allow_cancel: bool = False,
) -> tuple[str, str] | None:
    """Ask for the two choices that define the initial BridgAI experience."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(_('Configura BridgAI'))
    dialog.setModal(True)
    dialog.setMinimumWidth(520)

    title = QLabel(_('Come vuoi usare BridgAI?'))
    title.setStyleSheet('font-size: 18px; font-weight: 600;')
    introduction = QLabel(
        _(
            'Scegli la modalità principale e l’AI Web che usi più spesso. '
            'Potrai cambiare entrambe in qualsiasi momento dalle Impostazioni.'
        )
    )
    introduction.setWordWrap(True)

    mode_combo = QComboBox(dialog)
    mode_combo.addItem(_('Modalità Sviluppo'), DEVELOPMENT_MODE)
    mode_combo.addItem(_('Modalità Operativa'), OPERATIONS_MODE)
    mode_index = mode_combo.findData(current_mode)
    mode_combo.setCurrentIndex(max(0, mode_index))

    mode_help = QLabel(
        _(
            '<b>Sviluppo:</b> crea o modifica programmi, siti, script e automazioni.<br>'
            '<b>Operativa:</b> lavora sui tuoi file e ottieni documenti, analisi e altri risultati.'
        )
    )
    mode_help.setWordWrap(True)

    provider_combo = QComboBox(dialog)
    provider_combo.addItem('ChatGPT', PREFERRED_WEB_AI_CHATGPT)
    provider_combo.addItem('Claude', PREFERRED_WEB_AI_CLAUDE)
    provider_combo.addItem('Gemini', PREFERRED_WEB_AI_GEMINI)
    provider_combo.addItem(_('Personalizzato'), PREFERRED_WEB_AI_CUSTOM)
    provider_index = provider_combo.findData(current_provider)
    provider_combo.setCurrentIndex(max(0, provider_index))

    provider_help = QLabel(
        _(
            'ChatGPT e Claude usano il flusso ZIP → ZIP; Gemini usa ZIP → File Markdown '
            'di aggiornamento. Personalizzato mantiene il flusso configurabile nelle Impostazioni.'
        )
    )
    provider_help.setWordWrap(True)

    form = QFormLayout()
    form.addRow(_('Modalità di utilizzo:'), mode_combo)
    form.addRow('', mode_help)
    form.addRow(_('AI Web preferita:'), provider_combo)
    form.addRow('', provider_help)

    button_flags = QDialogButtonBox.StandardButton.Ok
    if allow_cancel:
        button_flags |= QDialogButtonBox.StandardButton.Cancel
    buttons = QDialogButtonBox(button_flags, parent=dialog)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_('Inizia'))
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    layout = QVBoxLayout(dialog)
    layout.addWidget(title)
    layout.addWidget(introduction)
    layout.addSpacing(8)
    layout.addLayout(form)
    layout.addSpacing(8)
    layout.addWidget(buttons)

    result = dialog.exec()
    if result != QDialog.DialogCode.Accepted and allow_cancel:
        return None
    return str(mode_combo.currentData()), str(provider_combo.currentData())


def choose_initial_primary_mode(parent: QWidget | None = None) -> str:
    """Backward-compatible helper for callers that only need the primary mode."""
    result = choose_initial_setup(parent)
    if result is None:
        return DEVELOPMENT_MODE
    mode, _preferred_web_ai = result
    return mode
