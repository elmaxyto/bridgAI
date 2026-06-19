from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.web.security import (
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_code,
    totp_provisioning_uri,
    verify_totp,
)
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class TotpEnrollment:
    secret: str
    recovery_codes: tuple[str, ...]

    @property
    def recovery_hashes(self) -> list[str]:
        return [hash_recovery_code(code) for code in self.recovery_codes]


def qr_svg_for_uri(uri: str) -> bytes:
    import qrcode
    import qrcode.image.svg

    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathFillImage, border=4)
    output = BytesIO()
    image.save(output)
    return output.getvalue()


def _qr_pixmap(uri: str, size: int = 280) -> QPixmap | None:
    try:
        renderer = QSvgRenderer(QByteArray(qr_svg_for_uri(uri)))
        if not renderer.isValid():
            return None
        image = QImage(size, size, QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        return QPixmap.fromImage(image)
    except Exception:
        return None


def _setup_dialog(parent: QWidget, username: str, secret: str) -> tuple[QDialog, QLineEdit]:
    dialog = QDialog(parent)
    dialog.setWindowTitle(_("Configura autenticazione a due fattori"))
    dialog.setMinimumWidth(430)
    layout = QVBoxLayout(dialog)

    intro = QLabel(
        _(
            "Scansiona il QR con Google Authenticator, Microsoft Authenticator, 2FAS "
            "o un’altra app TOTP compatibile. Poi inserisci il codice a 6 cifre."
        )
    )
    intro.setWordWrap(True)
    layout.addWidget(intro)

    uri = totp_provisioning_uri(secret, username or "BridgAI")
    pixmap = _qr_pixmap(uri)
    if pixmap is not None:
        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignCenter)
        qr_label.setPixmap(pixmap)
        layout.addWidget(qr_label)

    form = QFormLayout()
    secret_edit = QLineEdit(secret)
    secret_edit.setReadOnly(True)
    secret_edit.setCursorPosition(0)
    code_edit = QLineEdit()
    code_edit.setPlaceholderText("123456")
    code_edit.setMaxLength(6)
    code_edit.setInputMask("000000")
    form.addRow(_("Chiave manuale:"), secret_edit)
    form.addRow(_("Codice di verifica:"), code_edit)
    layout.addLayout(form)

    warning = QLabel(
        _(
            "Il QR contiene il segreto 2FA: non fotografarlo e non condividerlo. "
            "La configurazione sarà salvata solo dopo la verifica del codice."
        )
    )
    warning.setWordWrap(True)
    layout.addWidget(warning)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_("Attiva 2FA"))
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return dialog, code_edit


def _show_recovery_codes(parent: QWidget, codes: tuple[str, ...]) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(_("Codici di recupero 2FA"))
    dialog.setMinimumWidth(430)
    layout = QVBoxLayout(dialog)
    label = QLabel(
        _(
            "Salva questi codici in un luogo sicuro. Ogni codice può essere usato una sola "
            "volta al posto del codice dell’app Authenticator. Non verranno mostrati di nuovo."
        )
    )
    label.setWordWrap(True)
    layout.addWidget(label)
    codes_edit = QPlainTextEdit("\n".join(codes))
    codes_edit.setReadOnly(True)
    codes_edit.setMinimumHeight(190)
    layout.addWidget(codes_edit)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()


def enroll_totp(parent: QWidget, username: str) -> TotpEnrollment | None:
    secret = generate_totp_secret()
    while True:
        dialog, code_edit = _setup_dialog(parent, username, secret)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        if verify_totp(secret, code_edit.text(), valid_window=1) is None:
            QMessageBox.warning(
                parent,
                _("Codice non valido"),
                _(
                    "Il codice non corrisponde. Controlla che data e ora del computer e del "
                    "telefono siano corrette, poi riprova."
                ),
            )
            continue
        codes = generate_recovery_codes()
        enrollment = TotpEnrollment(secret=secret, recovery_codes=codes)
        _show_recovery_codes(parent, codes)
        return enrollment
