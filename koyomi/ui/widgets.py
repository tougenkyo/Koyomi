"""自作の小さな部品。"""
from __future__ import annotations

from PySide6.QtCore import (Property, QEasingCurve, QPropertyAnimation, QRectF,
                            QSize, Qt, Signal)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QWidget

from . import theme


class ToggleSwitch(QWidget):
    """ON/OFF を切り替える横長スイッチ。錠前が掛かっていると弾く。"""

    toggled = Signal(bool)
    blocked = Signal()

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._knob = 1.0 if checked else 0.0
        self._locked = False
        self.setFixedSize(48, 26)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    # -- プロパティ ---------------------------------------------------------
    def get_knob(self) -> float:
        return self._knob

    def set_knob(self, value: float) -> None:
        self._knob = value
        self.update()

    knob = Property(float, get_knob, set_knob)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool, animate: bool = True) -> None:
        value = bool(value)
        if value == self._checked:
            return
        self._checked = value
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._knob)
            self._anim.setEndValue(1.0 if value else 0.0)
            self._anim.start()
        else:
            self.set_knob(1.0 if value else 0.0)

    def setLocked(self, value: bool) -> None:
        self._locked = bool(value)
        self.setCursor(Qt.ForbiddenCursor if value else Qt.PointingHandCursor)
        self.update()

    def isLocked(self) -> bool:
        return self._locked

    # -- 操作 ---------------------------------------------------------------
    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._locked:
            self.blocked.emit()
            return
        self.setChecked(not self._checked)
        self.toggled.emit(self._checked)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        off = QColor(theme.SWITCH_OFF)
        on = QColor(theme.ACCENT)
        if self._locked:
            on = QColor(theme.ACCENT_DIM)
        blend = QColor(
            int(off.red() + (on.red() - off.red()) * self._knob),
            int(off.green() + (on.green() - off.green()) * self._knob),
            int(off.blue() + (on.blue() - off.blue()) * self._knob),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(blend)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._knob
        p.setBrush(QColor("#ffffff") if not self._locked else QColor("#c9cfd9"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))

        if self._locked:
            # 錠前の代わりに小さな横棒を 1 本引く
            p.setPen(QPen(QColor(theme.INK), 2))
            p.drawLine(int(x + d * 0.3), int(r.center().y()),
                       int(x + d * 0.7), int(r.center().y()))
        p.end()


class Pill(QLabel):
    """種別や状態を示す小さなラベル。"""

    def __init__(self, text: str = "", tint: str = "", parent=None):
        super().__init__(text, parent)
        self.setTint(tint or theme.TEXT_SUB)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

    def setTint(self, tint: str) -> None:
        self.setStyleSheet(
            "color: %s; border: 1px solid %s; border-radius: 8px;"
            "padding: 3px 8px; font-size: 11px; background: transparent;" % (tint, tint)
        )


class Hairline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet("background: %s;" % theme.LINE)


class HoldButton(QPushButton):
    """押し続けると輪が満ちて確定するボタン。"""

    completed = Signal()

    def __init__(self, text: str, seconds: float = 2.0, tint: str = "",
                 parent=None):
        super().__init__(text, parent)
        self._need = max(0.3, seconds)
        self._progress = 0.0
        self._tint = tint or theme.ACCENT
        self.setMinimumHeight(58)
        self.setCursor(Qt.PointingHandCursor)
        from PySide6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._advance)

    def _advance(self):
        self._progress += 0.03 / self._need
        if self._progress >= 1.0:
            self._progress = 1.0
            self._timer.stop()
            self.update()
            self.completed.emit()
            self._progress = 0.0
        self.update()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._progress = 0.0
        self._timer.start()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._timer.stop()
        self._progress = 0.0
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._progress <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        w = self.width() * self._progress
        path.addRoundedRect(QRectF(0, self.height() - 4, w, 4), 2, 2)
        p.fillPath(path, QColor(self._tint))
        p.end()


class SlideToAct(QWidget):
    """つまみを右端までドラッグすると確定する帯。"""

    completed = Signal()

    def __init__(self, caption: str, tint: str = "", parent=None):
        super().__init__(parent)
        self._caption = caption
        self._tint = tint or theme.ACCENT
        self._pos = 0.0
        self._dragging = False
        self.setMinimumHeight(62)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.OpenHandCursor)

    def _knob_rect(self) -> QRectF:
        d = self.height() - 12
        span = self.width() - d - 12
        return QRectF(6 + span * self._pos, 6, d, d)

    def mousePressEvent(self, event):
        if self._knob_rect().adjusted(-8, -8, 8, 8).contains(event.position()):
            self._dragging = True
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        d = self.height() - 12
        span = max(1.0, self.width() - d - 12)
        self._pos = max(0.0, min(1.0, (event.position().x() - 6 - d / 2) / span))
        self.update()

    def mouseReleaseEvent(self, _event):
        if not self._dragging:
            return
        self._dragging = False
        self.setCursor(Qt.OpenHandCursor)
        if self._pos > 0.9:
            self._pos = 1.0
            self.update()
            self.completed.emit()
        self._pos = 0.0
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.SLATE_HI))
        p.drawRoundedRect(r, self.height() / 2, self.height() / 2)

        tint = QColor(self._tint)
        fill = QRectF(r)
        fill.setWidth(max(self.height(), r.width() * self._pos + self.height() / 2))
        p.setBrush(QColor(tint.red(), tint.green(), tint.blue(), 70))
        p.drawRoundedRect(fill, self.height() / 2, self.height() / 2)

        p.setPen(QColor(theme.TEXT_SUB))
        f = p.font()
        f.setPointSize(11)
        p.setFont(f)
        p.drawText(r.adjusted(self.height(), 0, -12, 0),
                   Qt.AlignVCenter | Qt.AlignLeft, self._caption)

        knob = self._knob_rect()
        p.setPen(Qt.NoPen)
        p.setBrush(tint)
        p.drawEllipse(knob)
        p.setPen(QPen(QColor(theme.INK), 2))
        cy = knob.center().y()
        cx = knob.center().x()
        for k in (-4, 1):
            p.drawLine(int(cx + k), int(cy - 5), int(cx + k + 5), int(cy))
            p.drawLine(int(cx + k + 5), int(cy), int(cx + k), int(cy + 5))
        p.end()

    def sizeHint(self) -> QSize:
        return QSize(320, 62)
