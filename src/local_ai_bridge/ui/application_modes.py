from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from local_ai_bridge.core.settings import DEVELOPMENT_MODE, OPERATIONS_MODE
from local_ai_bridge.i18n import tr as _


def choose_initial_primary_mode(parent: QWidget | None = None) -> str:
    """Ask for the initial experience without changing any workspace."""
    dialog = QMessageBox(parent)
    dialog.setWindowTitle(_('Scegli la modalità principale'))
    dialog.setIcon(QMessageBox.Icon.Question)
    dialog.setText(_('Che cosa vuoi fare con BridgAI?'))
    dialog.setInformativeText(
        _(
            '<b>Modalità Sviluppo</b><br>'
            'Crea o modifica programmi, siti, script e automazioni.<br><br>'
            '<b>Modalità Operativa</b><br>'
            'Lavora sui tuoi file e ottieni direttamente documenti, analisi e altri risultati.<br><br>'
            'Puoi cambiare modalità in qualsiasi momento dalle Impostazioni.'
        )
    )
    development_button = dialog.addButton(
        _('Modalità Sviluppo'), QMessageBox.ButtonRole.AcceptRole
    )
    operations_button = dialog.addButton(
        _('Modalità Operativa'), QMessageBox.ButtonRole.ActionRole
    )
    dialog.setDefaultButton(development_button)
    dialog.exec()
    if dialog.clickedButton() is operations_button:
        return OPERATIONS_MODE
    return DEVELOPMENT_MODE
