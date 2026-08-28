"""ストップウォッチ。1 台につき 1 つの小窓を開き、何台でも並べられる。"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QPushButton, QVBoxLayout)

from . import theme
from ..i18n import tr


def watch_text(value: float, decimals: int = 1) -> str:
    """経過秒を 1:23.4 のように整える。"""
    value = max(0.0, value)
    minutes, seconds = divmod(value, 60)
    hours, minutes = divmod(int(minutes), 60)
    if decimals <= 0:
        body = "%02d" % int(seconds)
    else:
        width = decimals + 3
        body = "%0*.*f" % (width, decimals, seconds)
    if hours:
        return "%d:%02d:%s" % (hours, minutes, body)
    return "%d:%s" % (minutes, body)


class StopwatchWindow(QDialog):
    """独立した 1 台のストップウォッチ。"""

    closed = Signal(object)

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(label)
        self.setMinimumWidth(340)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self.running = False
        self.base = 0.0
        self.elapsed = 0.0
        self.last_lap = 0.0
        self.decimals = 1

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        head = QHBoxLayout()
        self.name_field = QLineEdit(label)
        self.name_field.setPlaceholderText(tr("名前"))
        self.name_field.textChanged.connect(
            lambda t: self.setWindowTitle(t.strip() or tr("ストップウォッチ")))
        head.addWidget(self.name_field, 1)
        self.on_top = QCheckBox(tr("最前面"))
        self.on_top.toggled.connect(self._set_on_top)
        head.addWidget(self.on_top)
        root.addLayout(head)

        self.display = QLabel(watch_text(0.0))
        self.display.setAlignment(Qt.AlignCenter)
        self.display.setStyleSheet("font-size: 44px; font-weight: bold;")
        root.addWidget(self.display)

        row = QHBoxLayout()
        self.go_btn = QPushButton(tr("スタート"))
        self.go_btn.setProperty("tone", "accent")
        self.go_btn.clicked.connect(self.toggle)
        row.addWidget(self.go_btn)
        lap = QPushButton(tr("ラップ"))
        lap.clicked.connect(self.take_lap)
        row.addWidget(lap)
        clear = QPushButton(tr("リセット"))
        clear.setProperty("tone", "ghost")
        clear.clicked.connect(self.reset)
        row.addWidget(clear)
        root.addLayout(row)

        precision = QHBoxLayout()
        precision.addWidget(QLabel(tr("秒の表示")))
        for caption, digits in ((tr("1秒"), 0), (tr("0.1秒"), 1), (tr("0.01秒"), 2), (tr("0.001秒"), 3)):
            btn = QPushButton(caption)
            btn.setProperty("tone", "ghost")
            btn.clicked.connect(lambda _=False, d=digits: self.set_decimals(d))
            precision.addWidget(btn)
        precision.addStretch(1)
        root.addLayout(precision)

        self.laps = QListWidget()
        root.addWidget(self.laps, 1)

        self.beat = QTimer(self)
        self.beat.setInterval(40)
        self.beat.timeout.connect(self._on_beat)
        self.beat.start()

    # ------------------------------------------------------------------
    def _set_on_top(self, on: bool) -> None:
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.show()

    def set_decimals(self, digits: int) -> None:
        self.decimals = digits
        self.beat.setInterval(200 if digits <= 0 else max(10, 10 ** (2 - digits)))
        self._refresh()

    def toggle(self) -> None:
        if self.running:
            self.running = False
            self.go_btn.setText(tr("再開"))
        else:
            self.base = time.monotonic() - self.elapsed
            self.running = True
            self.go_btn.setText(tr("停止"))

    def reset(self) -> None:
        self.running = False
        self.elapsed = 0.0
        self.last_lap = 0.0
        self.go_btn.setText(tr("スタート"))
        self.laps.clear()
        self._refresh()

    def take_lap(self) -> None:
        if self.elapsed <= 0:
            return
        split = self.elapsed - self.last_lap
        self.last_lap = self.elapsed
        self.laps.insertItem(
            0, tr("ラップ %d   %s   （通算 %s）")
            % (self.laps.count() + 1, watch_text(split, self.decimals),
               watch_text(self.elapsed, self.decimals)))

    def _on_beat(self) -> None:
        if self.running:
            self.elapsed = time.monotonic() - self.base
            self._refresh()

    def _refresh(self) -> None:
        self.display.setText(watch_text(self.elapsed, self.decimals))
        tint = theme.ACCENT if self.running else theme.TEXT
        self.display.setStyleSheet(
            "font-size: 44px; font-weight: bold; color: %s;" % tint)

    def closeEvent(self, event):
        self.beat.stop()
        self.closed.emit(self)
        super().closeEvent(event)
