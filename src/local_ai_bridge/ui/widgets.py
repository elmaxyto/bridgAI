from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)


class _ClearTextButton(QPushButton):
    """Small overlay button with a platform-independent clear glyph."""

    SIZE = 22

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFlat(True)
        self.setStyleSheet('border: none; background: transparent; padding: 0;')

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        dark_theme = self.palette().window().color().lightness() < 128
        hovered = self.underMouse()

        foreground = QColor('#dbeafe' if dark_theme else '#334155')
        foreground.setAlpha(220 if hovered else 105)
        if hovered:
            background = QColor('#ffffff' if dark_theme else '#0f172a')
            background.setAlpha(22 if dark_theme else 14)
            painter.setPen(Qt.NoPen)
            painter.setBrush(background)
            painter.drawEllipse(QRectF(1, 1, self.SIZE - 2, self.SIZE - 2))

        pen = QPen(foreground, 1.35 if hovered else 1.1)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        inset = 7.0
        painter.drawLine(QPointF(inset, inset), QPointF(self.SIZE - inset, self.SIZE - inset))
        painter.drawLine(QPointF(self.SIZE - inset, inset), QPointF(inset, self.SIZE - inset))


class ClearablePlainTextEdit(QPlainTextEdit):
    """Plain-text editor with a subtle clear button revealed on hover."""

    def __init__(self, parent: QWidget | None = None, clear_tooltip: str = '') -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._clear_button = _ClearTextButton(self)
        self._clear_button.hide()
        self._clear_button.clicked.connect(self.clear)
        self._clear_button.installEventFilter(self)
        self.textChanged.connect(self._update_clear_button)
        if clear_tooltip:
            self._clear_button.setToolTip(clear_tooltip)
            self._clear_button.setAccessibleName(clear_tooltip)

    @property
    def clear_button(self) -> QPushButton:
        return self._clear_button

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        margin = 6
        self._clear_button.move(
            self.width() - self._clear_button.width() - margin,
            margin,
        )

    def enterEvent(self, event) -> None:
        self._update_clear_button()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        QTimer.singleShot(0, self._update_clear_button)
        super().leaveEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._clear_button and event.type() in (QEvent.Type.Enter, QEvent.Type.Leave):
            QTimer.singleShot(0, self._update_clear_button)
        return super().eventFilter(watched, event)

    def _update_clear_button(self) -> None:
        has_content = bool(self.toPlainText())
        hovered = (
            self.underMouse()
            or self.viewport().underMouse()
            or self._clear_button.underMouse()
        )
        self._clear_button.setVisible(has_content and hovered)
        if self._clear_button.isVisible():
            self._clear_button.raise_()


class ToggleSwitch(QCheckBox):
    """Checkbox-compatible control rendered as a modern on/off switch."""

    TRACK_WIDTH = 38
    TRACK_HEIGHT = 21
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

class IconButton(QPushButton):
    """Circular icon-only button that paints its own vector glyph.

    Avoids relying on emoji/system-font characters (✎, +, ←), whose size and
    centering vary across fonts/platforms and can look clipped or off-center.
    """

    SIZE = 34
    KINDS = ('add', 'back', 'edit', 'microphone')

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if kind not in self.KINDS:
            raise ValueError(f'Unknown icon kind: {kind}')
        self._kind = kind
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setFlat(True)
        self.setStyleSheet('border: none; background: transparent;')

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        dark_theme = self.palette().window().color().lightness() < 128
        if not self.isEnabled():
            background = QColor('#303b4b' if dark_theme else '#f3f4f6')
            foreground = QColor('#7f8a9b' if dark_theme else '#9ca3af')
        elif self.underMouse() or self.hasFocus():
            background = QColor('#2c517f' if dark_theme else '#d7e6ff')
            foreground = QColor('#93c5fd' if dark_theme else '#1d4ed8')
        else:
            background = QColor('#1e3a5f' if dark_theme else '#e8f0ff')
            foreground = QColor('#60a5fa' if dark_theme else '#2563eb')

        bounds = QRectF(1, 1, self.SIZE - 2, self.SIZE - 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        painter.drawEllipse(bounds)

        pen = QPen(foreground, 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        center = bounds.center()

        if self._kind == 'add':
            half = 6.0
            painter.drawLine(QPointF(center.x() - half, center.y()), QPointF(center.x() + half, center.y()))
            painter.drawLine(QPointF(center.x(), center.y() - half), QPointF(center.x(), center.y() + half))
        elif self._kind == 'back':
            painter.drawLine(QPointF(center.x() + 5, center.y() - 6), QPointF(center.x() - 5, center.y()))
            painter.drawLine(QPointF(center.x() - 5, center.y()), QPointF(center.x() + 5, center.y() + 6))
        elif self._kind == 'edit':
            painter.drawLine(QPointF(center.x() - 6, center.y() + 6), QPointF(center.x() + 4, center.y() - 4))
            painter.setPen(Qt.NoPen)
            painter.setBrush(foreground)
            tip = QPolygonF([
                QPointF(center.x() + 4, center.y() - 4),
                QPointF(center.x() + 7, center.y() - 2),
                QPointF(center.x() + 6, center.y() - 6.5),
            ])
            painter.drawPolygon(tip)
        elif self._kind == 'microphone':
            # Lucide Mic geometry, adapted to QPainter from the SVG path:
            # <path d="M12 19v3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            # <rect x="9" y="2" width="6" height="13" rx="3"/>
            scale = 20.0 / 24.0
            left = center.x() - 10.0
            top = center.y() - 10.0

            def point(x: float, y: float) -> QPointF:
                return QPointF(left + x * scale, top + y * scale)

            def rect(x: float, y: float, width: float, height: float) -> QRectF:
                return QRectF(left + x * scale, top + y * scale, width * scale, height * scale)

            painter.drawLine(point(12, 19), point(12, 22))
            painter.drawLine(point(19, 10), point(19, 12))
            painter.drawArc(rect(5, 5, 14, 14), 0, -180 * 16)
            painter.drawLine(point(5, 12), point(5, 10))
            painter.drawRoundedRect(rect(9, 2, 6, 13), 3 * scale, 3 * scale)


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

class FlowLayout(QLayout):
    """Wraps child widgets onto new rows as needed, like tag/chip lists."""

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 6) -> None:
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing
        self._items: list = []

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x, y = effective.x(), effective.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


def _chip_button(label: str, callback) -> QPushButton:
    """Small removable pill button, used for 'active item' style lists."""
    button = QPushButton(f'{label}  \u2715')
    button.setProperty('role', 'chip')
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(callback)
    return button


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
