"""画面のすみに置いておく小さな窓。

次に鳴るアラームと、走っているタイマーの残りだけを出す。
枠が無く、どこを掴んでも動かせる。
"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from .. import planner
from . import theme
from ..i18n import tr


class FloatBar(QWidget):
    """常に手前に出る、細長い情報帯。"""

    opened = Signal()      # 本体を開いてほしい
    closed = Signal()      # 利用者が閉じた

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self._drag_from = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool
                            | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumWidth(250)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 8, 10)
        root.setSpacing(12)

        column = QVBoxLayout()
        column.setSpacing(0)
        self.clock = QLabel("--:--:--")
        self.clock.setStyleSheet("font-size: 22px; font-weight: bold;"
                                 "background: transparent;")
        column.addWidget(self.clock)
        self.detail = QLabel("")
        self.detail.setStyleSheet("font-size: 11px; background: transparent;"
                                  "color: %s;" % theme.TEXT_SUB)
        column.addWidget(self.detail)
        root.addLayout(column, 1)

        buttons = QVBoxLayout()
        buttons.setSpacing(3)
        open_btn = QPushButton(tr("開く"))
        open_btn.setProperty("tone", "flat")
        open_btn.setFixedHeight(22)
        open_btn.clicked.connect(self.opened.emit)
        buttons.addWidget(open_btn)
        shut = QPushButton(tr("閉じる"))
        shut.setProperty("tone", "flat")
        shut.setFixedHeight(22)
        shut.clicked.connect(self._dismiss)
        buttons.addWidget(shut)
        root.addLayout(buttons)

        self.beat = QTimer(self)
        self.beat.setInterval(1000)
        self.beat.timeout.connect(self.refresh)
        self.beat.start()
        self.refresh()
        self._settle()

    # ------------------------------------------------------------------
    def _settle(self) -> None:
        """初期位置は右下の少し内側。"""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        self.adjustSize()
        self.move(area.right() - self.width() - 24,
                  area.bottom() - self.height() - 24)

    def refresh(self) -> None:
        now = dt.datetime.now()
        self.clock.setText(now.strftime("%H:%M:%S"))

        lines = []
        soonest, owner = self.window.next_ring()
        if soonest is None:
            lines.append(tr("アラームの予定なし"))
        else:
            lines.append("%s  %s（%s）"
                         % (soonest.strftime("%m/%d %H:%M"),
                            owner.display_title(), planner.humanize_gap(soonest)))

        running = self.window.running_timers()
        if running:
            nearest = min(running, key=lambda r: r.left)
            lines.append(tr("タイマー %d本 ／ 最短 %s")
                         % (len(running), planner.duration_text(int(nearest.left))))
        self.detail.setText("　".join(lines))
        self.adjustSize()

    def _dismiss(self) -> None:
        self.closed.emit()
        self.hide()

    # ---- どこを掴んでも動かせるように --------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_from = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_from is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_from)

    def mouseReleaseEvent(self, _event):
        self._drag_from = None

    def mouseDoubleClickEvent(self, _event):
        self.opened.emit()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor(theme.LINE))
        body = QColor(theme.SLATE)
        body.setAlpha(238)
        p.setBrush(body)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)
        p.end()

    def closeEvent(self, event):
        self.beat.stop()
        super().closeEvent(event)
