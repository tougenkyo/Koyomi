"""アラームが鳴っているときに前面へ出る画面。"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QSpinBox, QStackedWidget, QVBoxLayout,
                               QWidget)

from .. import power
from ..models import Guard, SoundPlan, WakeItem
from ..player import SoundEngine
from . import guards, theme
from ..i18n import tr

SIMPLE_GUARDS = (Guard.TAP, Guard.HOLD, Guard.SLIDE)
MUTE_SECONDS = 30


class RingWindow(QWidget):
    """1 件のアラームの鳴動画面。"""

    stopped = Signal(object)            # WakeItem
    snoozed = Signal(object, int)       # WakeItem, 分
    auto_stopped = Signal(object)       # WakeItem

    def __init__(self, item: WakeItem, engine: SoundEngine, round_no: int = 0,
                 snooze_left: int = -1, parent=None, hold_awake: bool = True):
        super().__init__(parent)
        self.item = item
        self.engine = engine
        self.round_no = round_no
        self.snooze_left = snooze_left
        self.rang_at = dt.datetime.now()
        self._settled = False
        self._flash_on = False
        self._muted_until = None
        self._deadline = None
        self._beat = None

        self.setWindowTitle("%s ｜ %s" % (item.display_title(), item.clock_text))
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumSize(520, 560)

        self._hold_awake = hold_awake
        if hold_awake:
            # 鳴っている最中に PC が寝てしまうと意味がないので押さえておく
            power.keep_awake(True)

        self._build()
        self._begin_sound()
        self._arm_timers()
        self._place_on_screen()

    # ------------------------------------------------------------------
    # 組み立て
    # ------------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        self.frame_top = QWidget()
        top = QVBoxLayout(self.frame_top)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(2)

        self.badge = QLabel()
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setStyleSheet("color: %s; font-size: 13px;" % theme.ACCENT)
        top.addWidget(self.badge)

        self.clock = QLabel()
        self.clock.setAlignment(Qt.AlignCenter)
        size = 56 if self.item.shrink_text else 76
        self.clock.setStyleSheet("font-size: %dpx; font-weight: bold;" % size)
        top.addWidget(self.clock)

        self.name = QLabel(self.item.display_title())
        self.name.setAlignment(Qt.AlignCenter)
        self.name.setWordWrap(True)
        self.name.setStyleSheet(
            "font-size: %dpx; color: %s;" %
            (16 if self.item.shrink_text else 20, theme.TEXT))
        top.addWidget(self.name)

        self.notice = QLabel("")
        self.notice.setAlignment(Qt.AlignCenter)
        self.notice.setWordWrap(True)
        self.notice.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        top.addWidget(self.notice)

        root.addStretch(2)
        root.addWidget(self.frame_top)
        root.addStretch(3)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_choices())
        self.challenge_host = QWidget()
        self.challenge_layout = QVBoxLayout(self.challenge_host)
        self.challenge_layout.setContentsMargins(0, 0, 0, 0)
        self.challenge_layout.setSpacing(10)
        self.stack.addWidget(self.challenge_host)
        root.addWidget(self.stack)

        extras = QHBoxLayout()
        self.mute_btn = QPushButton(tr("%d秒だけ消音") % MUTE_SECONDS)
        self.mute_btn.setProperty("tone", "flat")
        self.mute_btn.clicked.connect(self._mute_briefly)
        extras.addWidget(self.mute_btn)
        extras.addStretch(1)

        if self.item.snooze.enabled and self.item.snooze.allow_interval_change:
            extras.addWidget(QLabel(tr("スヌーズ間隔")))
            self.interval_box = QSpinBox()
            self.interval_box.setRange(1, 1439)
            self.interval_box.setSuffix(tr(" 分"))
            self.interval_box.setValue(self.item.snooze.minutes)
            extras.addWidget(self.interval_box)
        else:
            self.interval_box = None
        root.addLayout(extras)

        self._refresh_header()

    def _snooze_available(self) -> bool:
        if not self.item.snooze.enabled:
            return False
        return self.snooze_left != 0

    def _build_choices(self) -> QWidget:
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        if self._snooze_available():
            lay.addWidget(self._entry_for(self.item.snooze_guard, tr("スヌーズ"),
                                          theme.COOL, self._ask_snooze))
        lay.addWidget(self._entry_for(self.item.stop_guard, tr("停止"),
                                      theme.ACCENT, self._ask_stop))
        return holder

    def _entry_for(self, plan, caption: str, tint: str, action) -> QWidget:
        """単純な操作ならその場に、難しい操作なら入口ボタンを置く。"""
        if plan.style in SIMPLE_GUARDS:
            pad = guards.build_pad(plan, caption, tint)
            pad.solved.connect(action)
            return pad
        btn = QPushButton("%s（%s）" % (caption, guards.describe(plan)))
        btn.setMinimumHeight(58)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "background: %s; color: #1b1f27; border: none; border-radius: 12px;"
            "font-size: 16px; font-weight: bold;" % tint)
        btn.clicked.connect(lambda: self._open_challenge(plan, caption, tint, action))
        return btn

    def _open_challenge(self, plan, caption: str, tint: str, action) -> None:
        while self.challenge_layout.count():
            entry = self.challenge_layout.takeAt(0)
            widget = entry.widget()
            if widget:
                widget.deleteLater()
        pad = guards.build_pad(plan, caption, tint)
        pad.solved.connect(action)
        self.challenge_layout.addWidget(pad)
        back = QPushButton(tr("もどる"))
        back.setProperty("tone", "ghost")
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.challenge_layout.addWidget(back)
        self.stack.setCurrentIndex(1)
        pad.setFocus()

    # ------------------------------------------------------------------
    # 表示の更新
    # ------------------------------------------------------------------
    def _refresh_header(self) -> None:
        self.clock.setText(dt.datetime.now().strftime("%H:%M:%S"))
        marks = []
        if self.round_no > 0 and self.item.snooze.show_round_count:
            marks.append(tr("スヌーズ %d回目") % self.round_no)
        if self.snooze_left > 0:
            marks.append(tr("残り %d回") % self.snooze_left)
        elif self.snooze_left == 0 and self.item.snooze.enabled:
            marks.append(tr("スヌーズ上限に達しました"))
        if self.item.auto_stop_minutes:
            left = self._auto_stop_left()
            if left is not None:
                marks.append(tr("自動停止まで %d:%02d") % (left // 60, left % 60))
        self.badge.setText("　·　".join(marks) if marks else tr("アラーム"))

    def _auto_stop_left(self):
        if not self._deadline:
            return None
        return max(0, int((self._deadline - dt.datetime.now()).total_seconds()))

    # ------------------------------------------------------------------
    # 音とタイマー
    # ------------------------------------------------------------------
    def _tone_plan(self) -> SoundPlan:
        override = self.item.snooze.tone_for(self.round_no) if self.round_no else None
        return override or self.item.sound

    def _begin_sound(self) -> None:
        plan = self._tone_plan()
        if plan.delay_start:
            QTimer.singleShot(2000, lambda: self._play(plan))
        else:
            self._play(plan)

    def _play(self, plan: SoundPlan) -> None:
        if self._settled:
            return
        note = self.engine.start(plan)
        if note:
            self.notice.setText(note)

    def _arm_timers(self) -> None:
        self._deadline = None
        limit = self.item.auto_stop_minutes
        if limit:
            seconds = limit * 60
            # スヌーズ間隔をまたぐと次回と重なるので、その 5 秒前で切り上げる
            if self.item.snooze.enabled:
                span = self.item.snooze.minutes * 60 - 5
                if span > 0:
                    seconds = min(seconds, span)
            self._deadline = self.rang_at + dt.timedelta(seconds=seconds)

        self._beat = QTimer(self)
        self._beat.setInterval(500)
        self._beat.timeout.connect(self._on_beat)
        self._beat.start()

    def _on_beat(self) -> None:
        if self._settled:
            return
        self._refresh_header()
        if self._muted_until and dt.datetime.now() >= self._muted_until:
            self._muted_until = None
            self.mute_btn.setText(tr("%d秒だけ消音") % MUTE_SECONDS)
            self._play(self._tone_plan())
        if self.item.flash_screen:
            self._flash_on = not self._flash_on
            tint = theme.ACCENT if self._flash_on else theme.LINE
            self.setStyleSheet(
                "RingWindow { background: %s; border: 3px solid %s; }"
                % (theme.INK, tint))
        if self._deadline and dt.datetime.now() >= self._deadline:
            self._auto_finish()

    def _mute_briefly(self) -> None:
        if self._muted_until:
            return
        self.engine.stop()
        self._muted_until = dt.datetime.now() + dt.timedelta(seconds=MUTE_SECONDS)
        self.mute_btn.setText(tr("消音中…"))

    # ------------------------------------------------------------------
    # 確定操作
    # ------------------------------------------------------------------
    def _confirm(self, plan, question: str) -> bool:
        if not plan.confirm:
            return True
        answer = QMessageBox.question(self, tr("確認"), question,
                                      QMessageBox.Yes | QMessageBox.No,
                                      QMessageBox.Yes)
        return answer == QMessageBox.Yes

    def _ask_stop(self) -> None:
        if not self._confirm(self.item.stop_guard, tr("このアラームを停止します。よろしいですか？")):
            self.stack.setCurrentIndex(0)
            return
        self._settle()
        self.stopped.emit(self.item)
        self.close()

    def _ask_snooze(self) -> None:
        if not self._confirm(self.item.snooze_guard, tr("スヌーズにします。よろしいですか？")):
            self.stack.setCurrentIndex(0)
            return
        minutes = self.item.snooze.minutes
        if self.interval_box is not None:
            minutes = self.interval_box.value()
        self._settle()
        self.snoozed.emit(self.item, minutes)
        self.close()

    def _auto_finish(self) -> None:
        self._settle()
        self.auto_stopped.emit(self.item)
        self.close()

    def _settle(self) -> None:
        if self._settled:
            return
        self._settled = True
        if self._beat is not None:
            self._beat.stop()
        self.engine.stop()
        if self._hold_awake:
            power.keep_awake(False)

    # ------------------------------------------------------------------
    def _place_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        self.resize(min(640, area.width() - 80), min(720, area.height() - 80))
        frame = self.frameGeometry()
        frame.moveCenter(area.center())
        self.move(frame.topLeft())

    def closeEvent(self, event):
        self._settle()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        # 不用意に閉じてしまわないよう Esc は握りつぶす
        if event.key() == Qt.Key_Escape:
            return
        if event.key() == Qt.Key_Space:
            self._mute_briefly()
            return
        super().keyPressEvent(event)
