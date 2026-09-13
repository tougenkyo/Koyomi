"""カウントダウンタイマーと、ストップウォッチの呼び出し口。

カウントダウンは秒数ではなく「いつ終わるか」を持たせてある。
そのおかげでアプリを閉じても走り続け、次に開いたときに残りが正しく出る。
月や年の単位で仕掛けるタイマーはこれが無いと成立しない。
"""
from __future__ import annotations

import datetime as dt
import os

from PySide6.QtCore import QDateTime, Qt, QTimer, Signal
from PySide6.QtWidgets import (QDialog, QGroupBox, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QPushButton, QScrollArea,
                               QSpinBox, QStackedWidget, QTabWidget, QVBoxLayout,
                               QWidget, QDateTimeEdit)

from ..models import SoundPlan, ToneKind
from ..planner import duration_text, span_text
from ..tonesmith import TONE_CATALOG
from . import theme
from .editor import SoundEditor
from .stopwatch import StopwatchWindow
from ..i18n import tr

MAX_TIMERS = 10


def timer_sound(raw=None) -> SoundPlan:
    """タイマーの音の指定を読む。

    無いときや読めないときは、音を選べるようになる前から鳴らしていた
    「ひびき」にする。以前に足したタイマーは、これまでどおりの音で鳴る。
    """
    if isinstance(raw, SoundPlan):
        return SoundPlan.from_dict(raw.to_dict())
    if isinstance(raw, dict) and raw:
        try:
            return SoundPlan.from_dict(raw)
        except (TypeError, ValueError):
            pass
    return SoundPlan(kind=ToneKind.BUILTIN, source="hibiki", volume=70, loop=True)


def sound_caption(plan: SoundPlan) -> str:
    """行に添える、音の短い名前。"""
    if plan.kind == ToneKind.SILENT:
        return tr("音を鳴らさない")
    if plan.kind == ToneKind.BUILTIN:
        return tr(TONE_CATALOG.get(plan.source, TONE_CATALOG["kizashi"]))
    name = os.path.basename(os.path.normpath(plan.source)) if plan.source else ""
    if plan.kind == ToneKind.FOLDER_PICK:
        return "%s（%s）" % (name, tr("フォルダからランダム"))
    return name or tr("音声ファイル")


class CountdownRow(QWidget):
    """タイマー 1 本ぶんの行。"""

    finished = Signal(object)
    removed = Signal(object)

    def __init__(self, name: str, seconds: int, deadline: str = "",
                 sound=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.total = max(1, int(seconds))
        self.sound = timer_sound(sound)
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
        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = QLabel(name)
        self.title.setStyleSheet("font-size: 13px; color: %s;" % theme.TEXT_SUB)
        head.addWidget(self.title)
        # 終わったときに鳴る音。タイマーごとに違う音を持てる
        self.tone = QLabel("♪ " + sound_caption(self.sound))
        self.tone.setStyleSheet("font-size: 11px; color: %s;" % theme.TEXT_SUB)
        if self.sound.kind in (ToneKind.FILE, ToneKind.FOLDER_PICK):
            self.tone.setToolTip(self.sound.source)
        head.addWidget(self.tone)
        head.addStretch(1)
        text.addLayout(head)
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
            "sound": self.sound.to_dict(),
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
        self.setMinimumSize(560, 660)

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
                            str(entry.get("deadline", "")),
                            entry.get("sound"))
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

        # 「すぐ足す」にも「追加」にも効くので、どちらの枠にも入れない。
        # 開いたままだと一覧の場所を食うので、ふだんは音の名前 1 行に畳む
        tone_box = QGroupBox(tr("これから足すタイマーの音"))
        tone_lay = QVBoxLayout(tone_box)
        tone_head = QHBoxLayout()
        self.tone_summary = QLabel()
        tone_head.addWidget(self.tone_summary, 1)
        self.tone_toggle = QPushButton(tr("音を選ぶ"))
        self.tone_toggle.setProperty("tone", "ghost")
        self.tone_toggle.setCheckable(True)
        self.tone_toggle.toggled.connect(self._show_sound_editor)
        tone_head.addWidget(self.tone_toggle)
        tone_lay.addLayout(tone_head)
        self.sound_editor = SoundEditor(timer_sound(self.vault.timer_sound),
                                        compact=True)
        self.sound_editor.preview_requested.connect(self._preview_sound)
        self.sound_editor.preview_stopped.connect(self.engine.stop)
        self.sound_editor.setVisible(False)
        for changed in (self.sound_editor.kind_box.currentIndexChanged,
                        self.sound_editor.builtin_box.currentIndexChanged,
                        self.sound_editor.path_field.textChanged):
            changed.connect(self._refresh_tone_summary)
        tone_lay.addWidget(self.sound_editor)
        lay.addWidget(tone_box)
        self._refresh_tone_summary()

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

    def _spawn(self, name: str, seconds: int, deadline: str = "",
               sound=None, start: bool = False):
        """行を 1 本足す。``start`` なら、足したその場で計り始める。"""
        if len(self.rows) >= MAX_TIMERS:
            return None
        row = CountdownRow(name, seconds, deadline, sound)
        row.finished.connect(self._on_finished)
        row.removed.connect(self._drop)
        self.stack_layout.insertWidget(self.stack_layout.count() - 1, row)
        self.rows.append(row)
        if start and not row.running:
            row.toggle()
        self._refresh_count()
        self._persist()
        return row

    def _drop(self, row: CountdownRow) -> None:
        if row in self.rows:
            self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._refresh_count()
        self._persist()

    def _persist(self) -> None:
        self.vault.timers = [r.snapshot() for r in self.rows]
        # 最後に選んでいた音は、次に窓を開いたときの初期値にする
        self.vault.timer_sound = self.sound_editor.value().to_dict()

    def _preview_sound(self, plan: SoundPlan) -> None:
        trial = SoundPlan.from_dict(plan.to_dict())
        trial.delay_start = False
        trial.loop = False
        self.engine.start(trial)

    def _show_sound_editor(self, shown: bool) -> None:
        self.sound_editor.setVisible(shown)
        self.tone_toggle.setText(tr("閉じる") if shown else tr("音を選ぶ"))
        if not shown:
            return
        # 開いた分だけ窓を伸ばす。伸ばさないと、欄が押し潰されて読めなくなる。
        # 画面より高くはしない
        needed = self.minimumSizeHint().height()
        screen = self.screen()
        if screen is not None:
            needed = min(needed, screen.availableGeometry().height() - 40)
        if self.height() < needed:
            self.resize(self.width(), needed)

    def _refresh_tone_summary(self, *_args) -> None:
        self.tone_summary.setText("♪ " + sound_caption(self.sound_editor.value()))

    def _add_preset(self, slot: int) -> None:
        seconds = self.vault.timer_presets[slot]
        self._spawn(duration_text(seconds), seconds,
                    sound=self.sound_editor.value(), start=True)

    def _add_custom(self) -> None:
        seconds = self._requested_seconds()
        if seconds <= 0:
            return
        name = self.name_field.text().strip() or span_text(seconds)
        sound = self.sound_editor.value()
        if self.mode_stack.currentIndex() == 1:
            # 日時で指定したものは、足すまでに経った分も含めて、その時刻ちょうどに終える
            target = self.target_field.dateTime().toPython()
            self._spawn(name, seconds, target.isoformat(timespec="seconds"), sound)
        else:
            self._spawn(name, seconds, sound=sound, start=True)
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
        plan = SoundPlan.from_dict(row.sound.to_dict())
        plan.delay_start = False
        plan.loop = True                 # 止めるまで鳴らし続ける
        notice = self.engine.start(plan)
        box = QDialog(self)
        box.setWindowTitle(tr("タイマー"))
        box.setMinimumWidth(340)
        box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        lay = QVBoxLayout(box)
        label = QLabel(tr("「%s」の時間になりました。") % row.name)
        label.setStyleSheet("font-size: 16px;")
        label.setWordWrap(True)
        lay.addWidget(label)
        if notice:                       # ファイルが見つからず内蔵の音にした、など
            hint = QLabel(notice)
            hint.setWordWrap(True)
            hint.setStyleSheet("color: %s;" % theme.WARN)
            lay.addWidget(hint)
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
