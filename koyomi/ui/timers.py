"""カウントダウンタイマーと、ストップウォッチの呼び出し口。

カウントダウンは秒数ではなく「いつ終わるか」を持たせてある。
そのおかげでアプリを閉じても走り続け、次に開いたときに残りが正しく出る。
月や年の単位で仕掛けるタイマーはこれが無いと成立しない。
"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDateTime, Qt, QTimer, Signal
from PySide6.QtWidgets import (QDialog, QGroupBox, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QPushButton, QScrollArea,
                               QSpinBox, QStackedWidget, QTabWidget, QVBoxLayout,
                               QWidget, QDateTimeEdit)

from ..models import SoundPlan, ToneKind
from ..planner import duration_text, span_text
from . import theme
from .stopwatch import StopwatchWindow
from ..i18n import tr

MAX_TIMERS = 10


class CountdownRow(QWidget):
    """タイマー 1 本ぶんの行。"""

    finished = Signal(object)
    removed = Signal(object)

    def __init__(self, name: str, seconds: int, deadline: str = "",
                 parent=None):
        super().__init__(parent)
        self.name = name
        self.total = max(1, int(seconds))
        self.deadline = None
        self.left = float(self.total)
        self._rang = False

        if deadline:
            try:
                self.deadline = dt.datetime.fromisoformat(deadline)
            except ValueError:
                self.deadline = None
        if self.deadline is not None:
            self.left = (self.deadline - dt.datetime.now()).total_seconds()
            if self.left <= 0:
                # 閉じている間に終わっていた
                self.left = 0.0
                self.deadline = None
                self._rang = True

        self.setStyleSheet(
            "CountdownRow { background: %s; border: 1px solid %s; border-radius: 10px; }"
            % (theme.SLATE, theme.LINE))
        self.setAttribute(Qt.WA_StyledBackground, True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        text = QVBoxLayout()
        text.setSpacing(0)
        self.title = QLabel(name)
        self.title.setStyleSheet("font-size: 13px; color: %s;" % theme.TEXT_SUB)
        text.addWidget(self.title)
        self.readout = QLabel(duration_text(self.total))
        self.readout.setStyleSheet("font-size: 24px; font-weight: bold;")
        text.addWidget(self.readout)
        self.ends_at = QLabel("")
        self.ends_at.setStyleSheet("font-size: 11px; color: %s;" % theme.TEXT_SUB)
        text.addWidget(self.ends_at)
        lay.addLayout(text, 1)

        self.play_btn = QPushButton(tr("開始"))
        self.play_btn.setProperty("tone", "accent")
        self.play_btn.clicked.connect(self.toggle)
        lay.addWidget(self.play_btn)

        reset = QPushButton(tr("戻す"))
        reset.clicked.connect(self.reset)
        lay.addWidget(reset)

        drop = QPushButton(tr("削除"))
        drop.setProperty("tone", "ghost")
        drop.clicked.connect(lambda: self.removed.emit(self))
        lay.addWidget(drop)

        # 走ったまま持ち越したタイマーは、開き直した直後から「一時停止」に見せる
        self._restyle_button()
        self.refresh()

    # ------------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self.deadline is not None

    def _restyle_button(self) -> None:
        self.play_btn.setText(tr("一時停止") if self.running else tr("開始"))
        self.play_btn.setProperty("tone", "ghost" if self.running else "accent")
        self.play_btn.style().unpolish(self.play_btn)
        self.play_btn.style().polish(self.play_btn)

    def toggle(self) -> None:
        if self.running:
            self.left = (self.deadline - dt.datetime.now()).total_seconds()
            self.deadline = None
        else:
            if self.left <= 0:
                self.left = float(self.total)
            self.deadline = dt.datetime.now() + dt.timedelta(seconds=self.left)
            self._rang = False
        self._restyle_button()
        self.refresh()

    def reset(self) -> None:
        self.deadline = None
        self._rang = False
        self.left = float(self.total)
        self._restyle_button()
        self.refresh()

    def advance(self) -> None:
        if not self.running:
            return
        self.left = (self.deadline - dt.datetime.now()).total_seconds()
        if self.left <= 0:
            self.left = 0.0
            self.deadline = None
            self._restyle_button()
            if not self._rang:
                self._rang = True
                self.finished.emit(self)
        self.refresh()

    def refresh(self) -> None:
        self.readout.setText(duration_text(int(round(self.left))))
        tint = theme.WARN if self.left <= 10 and self.running else theme.TEXT
        self.readout.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: %s;" % tint)
        if self.running:
            shape = "%m/%d %H:%M:%S" if self.left >= 86400 else "%H:%M:%S"
            self.ends_at.setText(tr("%s に終了") % self.deadline.strftime(shape))
        elif self.left <= 0:
            self.ends_at.setText(tr("終了しました"))
        else:
            self.ends_at.setText(tr("全体 %s") % span_text(self.total))

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "seconds": self.total,
            "deadline": self.deadline.isoformat(timespec="seconds")
                        if self.deadline else "",
        }


class TimerWindow(QDialog):
    """カウントダウンと、ストップウォッチの置き場。"""

    def __init__(self, vault, engine, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.engine = engine
        self.rows = []
        self.watches = []
        self.setWindowTitle(tr("タイマー"))
        self.setMinimumSize(560, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        tabs = QTabWidget()
        tabs.addTab(self._tab_timers(), tr("カウントダウン"))
        tabs.addTab(self._tab_watches(), tr("ストップウォッチ"))
        root.addWidget(tabs)

        self.beat = QTimer(self)
        self.beat.setInterval(200)
        self.beat.timeout.connect(self._on_beat)
        self.beat.start()

        for entry in self.vault.timers:
            try:
                self._spawn(str(entry.get("name", tr("タイマー"))),
                            int(entry["seconds"]),
                            str(entry.get("deadline", "")))
            except (KeyError, TypeError, ValueError):
                continue

    # ------------------------------------------------------------------
    def _tab_timers(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        presets = QGroupBox(tr("すぐ足す"))
        pl = QHBoxLayout(presets)
        self.preset_buttons = []
        for slot, seconds in enumerate(self.vault.timer_presets):
            btn = QPushButton(duration_text(seconds))
            btn.clicked.connect(lambda _=False, s=slot: self._add_preset(s))
            pl.addWidget(btn)
            self.preset_buttons.append(btn)
        edit = QPushButton(tr("よく使う時間を編集"))
        edit.setProperty("tone", "ghost")
        edit.clicked.connect(self._edit_presets)
        pl.addWidget(edit)
        lay.addWidget(presets)

        custom = QGroupBox(tr("新しいタイマー"))
        cl = QVBoxLayout(custom)

        top = QHBoxLayout()
        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText(tr("名前（省略可）"))
        top.addWidget(self.name_field, 1)
        self.mode_btn = QPushButton(tr("日時を指定して計る"))
        self.mode_btn.setProperty("tone", "ghost")
        self.mode_btn.clicked.connect(self._flip_mode)
        top.addWidget(self.mode_btn)
        cl.addLayout(top)

        self.mode_stack = QStackedWidget()

        # 期間で指定
        span = QWidget()
        sl = QHBoxLayout(span)
        sl.setContentsMargins(0, 0, 0, 0)
        self.day_box = QSpinBox()
        self.day_box.setRange(0, 3650)
        self.day_box.setSuffix(tr(" 日"))
        sl.addWidget(self.day_box)
        self.hour_box = QSpinBox()
        self.hour_box.setWrapping(True)
        self.hour_box.setRange(0, 23)
        self.hour_box.setSuffix(tr(" 時間"))
        sl.addWidget(self.hour_box)
        self.min_box = QSpinBox()
        self.min_box.setWrapping(True)
        self.min_box.setRange(0, 59)
        self.min_box.setSuffix(tr(" 分"))
        self.min_box.setValue(3)
        sl.addWidget(self.min_box)
        self.sec_box = QSpinBox()
        self.sec_box.setWrapping(True)
        self.sec_box.setRange(0, 59)
        self.sec_box.setSuffix(tr(" 秒"))
        sl.addWidget(self.sec_box)
        sl.addStretch(1)
        self.mode_stack.addWidget(span)

        # 日時で指定
        target = QWidget()
        tl = QHBoxLayout(target)
        tl.setContentsMargins(0, 0, 0, 0)
        self.target_field = QDateTimeEdit(
            QDateTime.currentDateTime().addDays(1))
        self.target_field.setCalendarPopup(True)
        self.target_field.setDisplayFormat("yyyy/MM/dd HH:mm:ss")
        self.target_field.setMinimumDateTime(QDateTime.currentDateTime())
        tl.addWidget(self.target_field, 1)
        self.mode_stack.addWidget(target)

        cl.addWidget(self.mode_stack)

        bottom = QHBoxLayout()
        self.span_note = QLabel("")
        self.span_note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        bottom.addWidget(self.span_note, 1)
        add = QPushButton(tr("追加"))
        add.setProperty("tone", "accent")
        add.clicked.connect(self._add_custom)
        bottom.addWidget(add)
        cl.addLayout(bottom)
        lay.addWidget(custom)

        for widget in (self.day_box, self.hour_box, self.min_box, self.sec_box):
            widget.valueChanged.connect(self._preview_span)
        self.target_field.dateTimeChanged.connect(self._preview_span)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        holder = QWidget()
        self.stack_layout = QVBoxLayout(holder)
        self.stack_layout.setSpacing(8)
        self.stack_layout.addStretch(1)
        area.setWidget(holder)
        lay.addWidget(area, 1)

        self.count_note = QLabel()
        self.count_note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        lay.addWidget(self.count_note)
        self._refresh_count()
        self._preview_span()
        return page

    def _tab_watches(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        note = QLabel(tr("ストップウォッチは 1 台ずつ別の窓で開きます。\n"
                      "何台でも並べられ、それぞれ独立して計れます。"))
        note.setWordWrap(True)
        note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        lay.addWidget(note)

        add = QPushButton(tr("＋ 新しいストップウォッチ"))
        add.setProperty("tone", "accent")
        add.setMinimumHeight(44)
        add.clicked.connect(self.open_stopwatch)
        lay.addWidget(add)

        self.watch_note = QLabel()
        self.watch_note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        lay.addWidget(self.watch_note)

        gather = QPushButton(tr("開いている窓をすべて前面に出す"))
        gather.setProperty("tone", "ghost")
        gather.clicked.connect(self._raise_watches)
        lay.addWidget(gather)

        lay.addStretch(1)
        self._refresh_watch_note()
        return page

    # ---- ストップウォッチ -------------------------------------------------
    def open_stopwatch(self) -> None:
        window = StopwatchWindow(tr("ストップウォッチ %d") % (len(self.watches) + 1), self)
        window.closed.connect(self._forget_watch)
        self.watches.append(window)
        window.show()
        self._refresh_watch_note()

    def _forget_watch(self, window) -> None:
        if window in self.watches:
            self.watches.remove(window)
        self._refresh_watch_note()

    def _raise_watches(self) -> None:
        for window in self.watches:
            window.show()
            window.raise_()

    def _refresh_watch_note(self) -> None:
        if hasattr(self, "watch_note"):
            self.watch_note.setText(tr("開いている台数: %d") % len(self.watches))

    # ---- カウントダウン ---------------------------------------------------
    def _flip_mode(self) -> None:
        to_target = self.mode_stack.currentIndex() == 0
        self.mode_stack.setCurrentIndex(1 if to_target else 0)
        self.mode_btn.setText(tr("長さで指定する") if to_target else tr("日時を指定して計る"))
        self._preview_span()

    def _requested_seconds(self) -> int:
        if self.mode_stack.currentIndex() == 0:
            return (self.day_box.value() * 86400 + self.hour_box.value() * 3600
                    + self.min_box.value() * 60 + self.sec_box.value())
        target = self.target_field.dateTime().toPython()
        return int((target - dt.datetime.now()).total_seconds())

    def _preview_span(self) -> None:
        seconds = self._requested_seconds()
        if seconds <= 0:
            self.span_note.setText(tr("未来の時刻を指定してください。"))
        else:
            self.span_note.setText(tr("いまから %s") % span_text(seconds))

    def _refresh_count(self) -> None:
        self.count_note.setText(tr("登録中 %d／%d 本") % (len(self.rows), MAX_TIMERS))

    def _spawn(self, name: str, seconds: int, deadline: str = "") -> None:
        if len(self.rows) >= MAX_TIMERS:
            return
        row = CountdownRow(name, seconds, deadline)
        row.finished.connect(self._on_finished)
        row.removed.connect(self._drop)
        self.stack_layout.insertWidget(self.stack_layout.count() - 1, row)
        self.rows.append(row)
        self._refresh_count()
        self._persist()

    def _drop(self, row: CountdownRow) -> None:
        if row in self.rows:
            self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._refresh_count()
        self._persist()

    def _persist(self) -> None:
        self.vault.timers = [r.snapshot() for r in self.rows]

    def _add_preset(self, slot: int) -> None:
        seconds = self.vault.timer_presets[slot]
        self._spawn(duration_text(seconds), seconds)

    def _add_custom(self) -> None:
        seconds = self._requested_seconds()
        if seconds <= 0:
            return
        name = self.name_field.text().strip() or span_text(seconds)
        self._spawn(name, seconds)
        self.name_field.clear()

    def _edit_presets(self) -> None:
        for slot in range(3):
            current = self.vault.timer_presets[slot]
            value, ok = QInputDialog.getInt(
                self, tr("よく使う時間 %d") % (slot + 1), tr("秒数"), current, 1, 31536000)
            if not ok:
                return
            self.vault.timer_presets[slot] = value
            self.preset_buttons[slot].setText(duration_text(value))

    def _on_finished(self, row: CountdownRow) -> None:
        self.engine.start(SoundPlan(kind=ToneKind.BUILTIN, source="hibiki",
                                    volume=70, loop=True))
        box = QDialog(self)
        box.setWindowTitle(tr("タイマー"))
        box.setMinimumWidth(340)
        box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        lay = QVBoxLayout(box)
        label = QLabel(tr("「%s」の時間になりました。") % row.name)
        label.setStyleSheet("font-size: 16px;")
        label.setWordWrap(True)
        lay.addWidget(label)
        ok = QPushButton(tr("止める"))
        ok.setProperty("tone", "accent")
        ok.clicked.connect(box.accept)
        lay.addWidget(ok)
        box.exec()
        self.engine.stop()
        self._persist()

    def _on_beat(self) -> None:
        for row in list(self.rows):
            row.advance()

    def closeEvent(self, event):
        self._persist()
        self.beat.stop()
        for window in list(self.watches):
            window.close()
        super().closeEvent(event)
