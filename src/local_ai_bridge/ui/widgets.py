from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

class ToggleSwitch(QCheckBox):
    """Checkbox-compatible control rendered as a modern on/off switch."""

    TRACK_WIDTH = 34
    TRACK_HEIGHT = 18
    KNOB_MARGIN = 2
    TEXT_GAP = 8

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setMinimumHeight(self.TRACK_HEIGHT + 4)

    def sizeHint(self) -> QSize:
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(self.TRACK_WIDTH + self.TEXT_GAP + text_width + 6, self.TRACK_HEIGHT + 6)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        enabled = self.isEnabled()
        checked = self.isChecked()
        palette = self.palette()
        dark_theme = palette.window().color().lightness() < 128

        if checked:
            # Use a restrained blue accent instead of the platform highlight,
            # which can appear purple on some Linux themes.
            track_color = QColor("#3b82f6" if dark_theme else "#2563eb")
            track_border = QColor("#60a5fa" if dark_theme else "#1d4ed8")
            knob_color = QColor("#ffffff")
        elif dark_theme:
            track_color = QColor("#374151")
            track_border = QColor("#4b5563")
            knob_color = QColor("#d1d5db")
        else:
            # Keep the inactive control light and neutral in the light theme.
            # Explicit colors avoid inheriting a stale/dark platform palette.
            track_color = QColor("#e5e7eb")
            track_border = QColor("#c7cdd6")
            knob_color = QColor("#ffffff")

        if self.underMouse() and enabled:
            if checked:
                track_color = track_color.lighter(112 if dark_theme else 104)
            else:
                track_color = QColor("#4b5563" if dark_theme else "#d8dde5")
                track_border = QColor("#6b7280" if dark_theme else "#aeb7c3")

        text_color = palette.text().color() if enabled else palette.mid().color()
        if not enabled:
            track_color.setAlpha(105)
            track_border.setAlpha(105)
            knob_color.setAlpha(125)

        top = (self.height() - self.TRACK_HEIGHT) / 2
        track = QRectF(1, top, self.TRACK_WIDTH, self.TRACK_HEIGHT)
        painter.setPen(QPen(track_border, 1))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, self.TRACK_HEIGHT / 2, self.TRACK_HEIGHT / 2)

        knob_size = self.TRACK_HEIGHT - (self.KNOB_MARGIN * 2)
        knob_x = (
            self.TRACK_WIDTH - self.KNOB_MARGIN - knob_size
            if checked
            else self.KNOB_MARGIN + 1
        )
        painter.setBrush(knob_color)
        painter.drawEllipse(QRectF(knob_x, top + self.KNOB_MARGIN, knob_size, knob_size))

        painter.setPen(text_color)
        text_rect = self.rect().adjusted(self.TRACK_WIDTH + self.TEXT_GAP, 0, 0, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())

        if self.hasFocus():
            focus_color = QColor("#60a5fa" if dark_theme else "#2563eb")
            focus_color.setAlpha(190)
            painter.setPen(focus_color)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(track.adjusted(-1, -1, 1, 1), self.TRACK_HEIGHT / 2, self.TRACK_HEIGHT / 2)

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

def _button(label: str, callback, role: str = 'secondary') -> QPushButton:
    button = QPushButton(label)
    button.setProperty('role', role)
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(callback)
    return button

class ProviderButton(QPushButton):
    def __init__(self, label: str, callback, dot_color: str | None = None) -> None:
        super().__init__(label)
        self.setProperty('role', 'secondary')
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet('padding-right: 30px;')
        self.clicked.connect(callback)
        self._provider_dot_color = QColor(dot_color) if dot_color else None

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        color = self._provider_dot_color or self.palette().color(self.foregroundRole())
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        radius = 5
        center_x = self.width() - 16
        center_y = self.height() // 2
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

def _provider_button(label: str, callback, dot_color: str | None = None) -> ProviderButton:
    return ProviderButton(label, callback, dot_color)

def _step_header(number: str, title: str, description: str) -> QWidget:
    container = QWidget()
    container.setProperty('class', 'stepHeader')
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    badge = QLabel(number)
    badge.setProperty('class', 'stepBadge')
    badge.setAlignment(Qt.AlignCenter)
    badge.setFixedSize(34, 34)
    row.addWidget(badge, 0, Qt.AlignTop)
    text_box = QVBoxLayout()
    text_box.setSpacing(2)
    heading = QLabel(title)
    heading.setProperty('class', 'stepTitle')
    detail = QLabel(description)
    detail.setProperty('class', 'stepDescription')
    detail.setWordWrap(True)
    text_box.addWidget(heading)
    text_box.addWidget(detail)
    row.addLayout(text_box, 1)
    container.badge_label = badge
    container.title_label = heading
    container.description_label = detail
    return container
