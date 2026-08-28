"""アラーム 1 件を編集するダイアログと、その部品。"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate, Qt, QTime, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSlider, QSpinBox, QStackedWidget,
                               QTabWidget, QTimeEdit, QVBoxLayout, QWidget)

from ..actions import LaunchPlan, check as check_launch
from ..models import (WEEKDAY_LABELS, Cycle, Guard, GuardPlan, SnoozeOrigin,
                      SoundPlan, ToneKind, Toughness, WakeItem, as_enum)
from ..player import AUDIO_SUFFIXES
from ..tonesmith import TONE_CATALOG
from . import guards, theme
from ..i18n import tr


# --------------------------------------------------------------------------
# 解除方法の編集
# --------------------------------------------------------------------------
class GuardEditor(QWidget):
    """停止／スヌーズの操作方法を選ばせる小さなパネル。"""

    def __init__(self, plan: GuardPlan, tint: str = "", parent=None):
        super().__init__(parent)
        self.tint = tint or theme.ACCENT
        form = QFormLayout(self)
        self.form = form
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(7)

        self.style_box = QComboBox()
        for style in Guard:
            self.style_box.addItem(style.label, style)
        self.style_box.setCurrentIndex(list(Guard).index(plan.style))
        self.style_box.currentIndexChanged.connect(self._sync)
        form.addRow(tr("操作方法"), self.style_box)

        self.tough_box = QComboBox()
        for level in Toughness:
            self.tough_box.addItem(level.label, level)
        self.tough_box.setCurrentIndex(list(Toughness).index(plan.toughness))
        form.addRow(tr("難しさ"), self.tough_box)

        self.rounds_box = QSpinBox()
        self.rounds_box.setRange(1, 10)
        self.rounds_box.setSuffix(tr(" 問"))
        self.rounds_box.setValue(max(1, plan.rounds))
        form.addRow(tr("出題数"), self.rounds_box)

        self.hold_box = QDoubleSpinBox()
        self.hold_box.setRange(0.5, 10.0)
        self.hold_box.setSingleStep(0.5)
        self.hold_box.setSuffix(tr(" 秒"))
        self.hold_box.setValue(plan.hold_seconds)
        form.addRow(tr("長押しの時間"), self.hold_box)

        self.confirm_box = QCheckBox(tr("確定前に確認する"))
        self.confirm_box.setChecked(plan.confirm)
        form.addRow(self.confirm_box)

        preview = QPushButton(tr("この操作を試す"))
        preview.setProperty("tone", "ghost")
        preview.clicked.connect(self._preview)
        form.addRow(preview)

        self._sync()

    def _sync(self) -> None:
        """選んだ操作方法に関係のない欄は、見出しごと引っ込める。"""
        style = as_enum(Guard, self.style_box.currentData())
        graded = style in (Guard.ARITHMETIC, Guard.ORDER_TAP, Guard.SHAPE_MATCH)
        self.form.setRowVisible(self.tough_box, graded)
        self.form.setRowVisible(self.rounds_box, graded)
        self.form.setRowVisible(self.hold_box, style == Guard.HOLD)

    def value(self) -> GuardPlan:
        return GuardPlan(
            style=as_enum(Guard, self.style_box.currentData()),
            toughness=as_enum(Toughness, self.tough_box.currentData()),
            rounds=self.rounds_box.value(),
            hold_seconds=self.hold_box.value(),
            confirm=self.confirm_box.isChecked(),
        )

    def _preview(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("操作の確認"))
        dialog.setMinimumWidth(400)
        lay = QVBoxLayout(dialog)
        note = QLabel(tr("実際の鳴動画面と同じ操作です。試しても設定は変わりません。"))
        note.setWordWrap(True)
        note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        lay.addWidget(note)
        pad = guards.build_pad(self.value(), tr("確認"), self.tint)
        pad.solved.connect(dialog.accept)
        lay.addWidget(pad)
        close = QPushButton(tr("閉じる"))
        close.setProperty("tone", "ghost")
        close.clicked.connect(dialog.reject)
        lay.addWidget(close)
        dialog.exec()


# --------------------------------------------------------------------------
# 音の編集
# --------------------------------------------------------------------------
FADE_CHOICES = [(0, "しない"), (5, "5秒かけて"), (15, "15秒かけて"),
                (30, "30秒かけて"), (60, "1分かけて"), (180, "3分かけて")]


class SoundEditor(QWidget):
    """鳴動音の選択欄。試聴つき。"""

    preview_requested = Signal(object)   # SoundPlan
    preview_stopped = Signal()

    def __init__(self, plan: SoundPlan, compact: bool = False, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        row = QHBoxLayout()
        self.kind_box = QComboBox()
        self.kind_box.addItem(tr("内蔵の音"), ToneKind.BUILTIN)
        self.kind_box.addItem(tr("音声ファイル"), ToneKind.FILE)
        self.kind_box.addItem(tr("フォルダからランダム"), ToneKind.FOLDER_PICK)
        self.kind_box.addItem(tr("音を鳴らさない"), ToneKind.SILENT)
        index = [ToneKind.BUILTIN, ToneKind.FILE,
                 ToneKind.FOLDER_PICK, ToneKind.SILENT].index(plan.kind)
        self.kind_box.setCurrentIndex(index)
        self.kind_box.currentIndexChanged.connect(self._sync)
        row.addWidget(self.kind_box, 1)
        lay.addLayout(row)

        self.source_stack = QStackedWidget()

        self.builtin_box = QComboBox()
        for key, label in TONE_CATALOG.items():
            self.builtin_box.addItem(tr(label), key)
        if plan.kind == ToneKind.BUILTIN:
            hit = self.builtin_box.findData(plan.source)
            if hit >= 0:
                self.builtin_box.setCurrentIndex(hit)
        self.source_stack.addWidget(self.builtin_box)

        picker = QWidget()
        picker_lay = QHBoxLayout(picker)
        picker_lay.setContentsMargins(0, 0, 0, 0)
        self.path_field = QLineEdit(plan.source if plan.kind in
                                    (ToneKind.FILE, ToneKind.FOLDER_PICK) else "")
        self.path_field.setPlaceholderText(tr("パスを選んでください"))
        picker_lay.addWidget(self.path_field, 1)
        browse = QPushButton(tr("参照"))
        browse.clicked.connect(self._browse)
        picker_lay.addWidget(browse)
        self.source_stack.addWidget(picker)

        blank = QLabel(tr("鳴動画面だけを表示します。"))
        blank.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        self.source_stack.addWidget(blank)

        lay.addWidget(self.source_stack)

        grid = QFormLayout()
        grid.setSpacing(7)

        vol_row = QHBoxLayout()
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(plan.volume)
        self.vol_label = QLabel("%d%%" % plan.volume)
        self.vol_label.setMinimumWidth(42)
        self.volume.valueChanged.connect(
            lambda v: self.vol_label.setText("%d%%" % v))
        vol_row.addWidget(self.volume, 1)
        vol_row.addWidget(self.vol_label)
        grid.addRow(tr("音量"), vol_row)

        self.fade_box = QComboBox()
        for secs, label in FADE_CHOICES:
            self.fade_box.addItem(label, secs)
        hit = self.fade_box.findData(plan.fade_seconds)
        self.fade_box.setCurrentIndex(hit if hit >= 0 else 0)
        grid.addRow(tr("だんだん大きく"), self.fade_box)

        if not compact:
            self.delay_box = QCheckBox(tr("鳴り始めを 2 秒遅らせる"))
            self.delay_box.setChecked(plan.delay_start)
            grid.addRow(self.delay_box)
            self.loop_box = QCheckBox(tr("止めるまで繰り返す"))
            self.loop_box.setChecked(plan.loop)
            grid.addRow(self.loop_box)
        else:
            self.delay_box = None
            self.loop_box = None
        lay.addLayout(grid)

        trial = QHBoxLayout()
        play = QPushButton(tr("試聴"))
        play.setProperty("tone", "ghost")
        play.clicked.connect(lambda: self.preview_requested.emit(self.value()))
        trial.addWidget(play)
        hush = QPushButton(tr("止める"))
        hush.setProperty("tone", "ghost")
        hush.clicked.connect(self.preview_stopped.emit)
        trial.addWidget(hush)
        trial.addStretch(1)
        lay.addLayout(trial)

        self._sync()

    def _sync(self) -> None:
        kind = as_enum(ToneKind, self.kind_box.currentData())
        if kind == ToneKind.BUILTIN:
            self.source_stack.setCurrentIndex(0)
        elif kind in (ToneKind.FILE, ToneKind.FOLDER_PICK):
            self.source_stack.setCurrentIndex(1)
        else:
            self.source_stack.setCurrentIndex(2)

    def _browse(self) -> None:
        kind = as_enum(ToneKind, self.kind_box.currentData())
        if kind == ToneKind.FOLDER_PICK:
            path = QFileDialog.getExistingDirectory(self, tr("フォルダを選ぶ"))
        else:
            filt = tr("音声ファイル (%s)") % " ".join("*" + s for s in AUDIO_SUFFIXES)
            path, _ = QFileDialog.getOpenFileName(self, tr("音声ファイルを選ぶ"), "", filt)
        if path:
            self.path_field.setText(path)

    def value(self) -> SoundPlan:
        kind = as_enum(ToneKind, self.kind_box.currentData())
        if kind == ToneKind.BUILTIN:
            source = self.builtin_box.currentData()
        elif kind == ToneKind.SILENT:
            source = ""
        else:
            source = self.path_field.text().strip()
        return SoundPlan(
            kind=kind,
            source=source,
            volume=self.volume.value(),
            fade_seconds=self.fade_box.currentData(),
            delay_start=self.delay_box.isChecked() if self.delay_box else False,
            loop=self.loop_box.isChecked() if self.loop_box else True,
        )


# --------------------------------------------------------------------------
# 繰り返し条件の編集
# --------------------------------------------------------------------------
class RepeatEditor(QWidget):
    """繰り返し種別と、そのパラメータ。"""

    def __init__(self, item: WakeItem, almanac, parent=None):
        super().__init__(parent)
        rule = item.repeat
        self.almanac = almanac

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.cycle_box = QComboBox()
        for cycle in Cycle:
            self.cycle_box.addItem(cycle.label, cycle)
        self.cycle_box.setCurrentIndex(list(Cycle).index(rule.cycle))
        self.cycle_box.currentIndexChanged.connect(self._sync)
        lay.addWidget(self.cycle_box)

        self.stack = QStackedWidget()
        lay.addWidget(self.stack)

        # 0: 繰り返さない
        self.stack.addWidget(self._note(tr("次に来るこの時刻に 1 回だけ鳴らします。")))

        # 1: 日付指定
        page = QWidget()
        pl = QFormLayout(page)
        self.on_date = QDateEdit(QDate.currentDate().addDays(1))
        self.on_date.setCalendarPopup(True)
        self.on_date.setDisplayFormat("yyyy/MM/dd")
        if rule.cycle == Cycle.ON_DATE and rule.anchor:
            self.on_date.setDate(QDate.fromString(rule.anchor, "yyyy-MM-dd"))
        pl.addRow(tr("鳴らす日"), self.on_date)
        self.stack.addWidget(page)

        # 2: 曜日
        page = QWidget()
        pl = QVBoxLayout(page)
        row = QHBoxLayout()
        self.weekday_boxes = []
        for idx, label in enumerate(WEEKDAY_LABELS):
            box = QCheckBox(tr(label))
            box.setChecked(idx in rule.weekdays)
            row.addWidget(box)
            self.weekday_boxes.append(box)
        row.addStretch(1)
        pl.addLayout(row)
        quick = QHBoxLayout()
        for caption, days in ((tr("毎日"), range(7)), (tr("平日"), range(5)),
                              (tr("週末"), (5, 6)), (tr("解除"), ())):
            btn = QPushButton(caption)
            btn.setProperty("tone", "ghost")
            btn.clicked.connect(lambda _=False, d=tuple(days): self._set_weekdays(d))
            quick.addWidget(btn)
        quick.addStretch(1)
        pl.addLayout(quick)
        self.add_marked = QCheckBox(tr("下のリストに入っている日も鳴らす"))
        self.add_marked.setChecked(rule.add_marked_days)
        pl.addWidget(self.add_marked)
        self.mark_boxes = {}
        marks = QGridLayout()
        for i, key in enumerate(sorted(almanac.lists)):
            box = QCheckBox(almanac.list_label(key))
            box.setChecked(key in rule.mark_lists)
            marks.addWidget(box, i // 2, i % 2)
            self.mark_boxes[key] = box
        pl.addLayout(marks)
        self.stack.addWidget(page)

        # 3: N 日おき
        page = QWidget()
        pl = QFormLayout(page)
        self.step_box = QSpinBox()
        self.step_box.setRange(1, 365)
        self.step_box.setSuffix(tr(" 日ごと"))
        self.step_box.setValue(max(1, rule.step_days))
        pl.addRow(tr("間隔"), self.step_box)
        self.step_anchor = QDateEdit(QDate.currentDate())
        self.step_anchor.setCalendarPopup(True)
        self.step_anchor.setDisplayFormat("yyyy/MM/dd")
        if rule.cycle == Cycle.EVERY_N_DAYS and rule.anchor:
            self.step_anchor.setDate(QDate.fromString(rule.anchor, "yyyy-MM-dd"))
        pl.addRow(tr("起点の日"), self.step_anchor)
        self.stack.addWidget(page)

        # 4: 毎月・日付
        page = QWidget()
        pl = QFormLayout(page)
        self.dom_box = QComboBox()
        for d in range(1, 32):
            self.dom_box.addItem(tr("%d日") % d, d)
        self.dom_box.addItem(tr("末日"), 0)
        hit = self.dom_box.findData(rule.day_of_month)
        self.dom_box.setCurrentIndex(hit if hit >= 0 else 0)
        pl.addRow(tr("毎月"), self.dom_box)
        self.stack.addWidget(page)

        # 5: 毎月・第n曜日
        page = QWidget()
        pl = QFormLayout(page)
        self.week_box = QComboBox()
        for n in range(1, 6):
            self.week_box.addItem(tr("第%d") % n, n)
        self.week_box.addItem(tr("最終"), 0)
        hit = self.week_box.findData(rule.week_index)
        self.week_box.setCurrentIndex(hit if hit >= 0 else 0)
        pl.addRow(tr("週"), self.week_box)
        self.nth_weekday = QComboBox()
        for idx, label in enumerate(WEEKDAY_LABELS):
            self.nth_weekday.addItem(tr("%s曜日") % tr(label), idx)
        self.nth_weekday.setCurrentIndex(rule.weekday)
        pl.addRow(tr("曜日"), self.nth_weekday)
        self.stack.addWidget(page)

        # 6: 毎年
        page = QWidget()
        pl = QFormLayout(page)
        self.annual_date = QDateEdit(QDate(QDate.currentDate().year(),
                                           rule.month or 1, rule.day or 1))
        self.annual_date.setCalendarPopup(True)
        self.annual_date.setDisplayFormat("MM/dd")
        pl.addRow(tr("毎年"), self.annual_date)
        self.stack.addWidget(page)

        # 7: 鳴動／休止
        page = QWidget()
        pl = QFormLayout(page)
        self.run_box = QSpinBox()
        self.run_box.setRange(1, 60)
        self.run_box.setSuffix(tr(" 日 鳴らす"))
        self.run_box.setValue(max(1, rule.run_days))
        pl.addRow(tr("周期"), self.run_box)
        self.rest_box = QSpinBox()
        self.rest_box.setRange(0, 60)
        self.rest_box.setSuffix(tr(" 日 休む"))
        self.rest_box.setValue(max(0, rule.rest_days))
        pl.addRow(self.rest_box)
        self.cycle_anchor = QDateEdit(QDate.currentDate())
        self.cycle_anchor.setCalendarPopup(True)
        self.cycle_anchor.setDisplayFormat("yyyy/MM/dd")
        if rule.cycle == Cycle.RUN_REST and rule.anchor:
            self.cycle_anchor.setDate(QDate.fromString(rule.anchor, "yyyy-MM-dd"))
        pl.addRow(tr("起点の日"), self.cycle_anchor)
        self.stack.addWidget(page)

        self._sync()

    @staticmethod
    def _note(text: str) -> QWidget:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        return label

    def _set_weekdays(self, days) -> None:
        for idx, box in enumerate(self.weekday_boxes):
            box.setChecked(idx in days)

    def _sync(self) -> None:
        self.stack.setCurrentIndex(self.cycle_box.currentIndex())

    def value(self):
        from ..models import RepeatRule
        cycle = as_enum(Cycle, self.cycle_box.currentData())
        rule = RepeatRule(cycle=cycle)
        if cycle == Cycle.ON_DATE:
            rule.anchor = self.on_date.date().toString("yyyy-MM-dd")
        elif cycle == Cycle.WEEKDAYS:
            rule.weekdays = [i for i, b in enumerate(self.weekday_boxes) if b.isChecked()]
            rule.add_marked_days = self.add_marked.isChecked()
            rule.mark_lists = [k for k, b in self.mark_boxes.items() if b.isChecked()]
            if not rule.weekdays and not (rule.add_marked_days and rule.mark_lists):
                rule.weekdays = [dt.date.today().weekday()]
        elif cycle == Cycle.EVERY_N_DAYS:
            rule.step_days = self.step_box.value()
            rule.anchor = self.step_anchor.date().toString("yyyy-MM-dd")
        elif cycle == Cycle.DAY_OF_MONTH:
            rule.day_of_month = self.dom_box.currentData()
        elif cycle == Cycle.NTH_WEEKDAY:
            rule.week_index = self.week_box.currentData()
            rule.weekday = self.nth_weekday.currentData()
        elif cycle == Cycle.ANNUAL:
            rule.month = self.annual_date.date().month()
            rule.day = self.annual_date.date().day()
        elif cycle == Cycle.RUN_REST:
            rule.run_days = self.run_box.value()
            rule.rest_days = self.rest_box.value()
            rule.anchor = self.cycle_anchor.date().toString("yyyy-MM-dd")
        return rule


# --------------------------------------------------------------------------
# 本体
# --------------------------------------------------------------------------
class AlarmEditor(QDialog):
    """アラーム 1 件の全設定。"""

    def __init__(self, item: WakeItem, vault, engine, parent=None,
                 title: str = tr("アラームの設定")):
        super().__init__(parent)
        self.item = WakeItem.from_dict(item.to_dict())
        self.vault = vault
        self.engine = engine
        self.setWindowTitle(title)
        self.setMinimumSize(560, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._wrap(self._tab_basics()), tr("基本"))
        tabs.addTab(self._wrap(self._tab_sound()), tr("音"))
        tabs.addTab(self._wrap(self._tab_stop()), tr("停止・スヌーズ"))
        tabs.addTab(self._wrap(self._tab_screen()), tr("画面"))
        tabs.addTab(self._wrap(self._tab_launch()), tr("連動"))
        root.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText(tr("保存"))
        buttons.button(QDialogButtonBox.Save).setProperty("tone", "accent")
        buttons.button(QDialogButtonBox.Cancel).setText(tr("やめる"))
        buttons.accepted.connect(self._commit)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _wrap(inner: QWidget) -> QWidget:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setWidget(inner)
        return area

    # ---- 各タブ -----------------------------------------------------------
    def _tab_basics(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        head = QGroupBox(tr("時刻と名前"))
        form = QFormLayout(head)
        self.time_field = QTimeEdit(QTime(self.item.hour, self.item.minute))
        self.time_field.setDisplayFormat("HH:mm")
        # 23 の次は 0、59 の次は 0 へ回り込ませる
        self.time_field.setWrapping(True)
        self.time_field.setStyleSheet("font-size: 26px; padding: 6px 10px;")
        form.addRow(tr("鳴らす時刻"), self.time_field)

        self.title_field = QLineEdit(self.item.title)
        self.title_field.setPlaceholderText(tr("空欄なら「アラーム」になります"))
        form.addRow(tr("名前"), self.title_field)

        self.group_box = QComboBox()
        for key, name in sorted(self.vault.groups.items()):
            self.group_box.addItem(name, key)
        hit = self.group_box.findData(self.item.group)
        self.group_box.setCurrentIndex(max(0, hit))
        form.addRow(tr("グループ"), self.group_box)
        lay.addWidget(head)

        repeat_box = QGroupBox(tr("繰り返し"))
        rl = QVBoxLayout(repeat_box)
        self.repeat_editor = RepeatEditor(self.item, self.vault.almanac)
        rl.addWidget(self.repeat_editor)
        lay.addWidget(repeat_box)

        dodge_box = QGroupBox(tr("鳴らさない日"))
        dl = QVBoxLayout(dodge_box)
        self.holiday_box = QCheckBox(tr("日本の祝日は鳴らさない"))
        self.holiday_box.setChecked(self.item.dodge_holidays)
        if not self.vault.almanac.holidays_available():
            self.holiday_box.setEnabled(False)
            self.holiday_box.setText(tr("日本の祝日は鳴らさない（jpholiday 未導入）"))
        dl.addWidget(self.holiday_box)
        self.dodge_boxes = {}
        grid = QGridLayout()
        for i, key in enumerate(sorted(self.vault.almanac.lists)):
            entry = self.vault.almanac.lists[key]
            box = QCheckBox(tr("%s（%d日）")
                            % (self.vault.almanac.list_label(key),
                               len(entry.days)))
            box.setChecked(key in self.item.dodge_lists)
            grid.addWidget(box, i // 2, i % 2)
            self.dodge_boxes[key] = box
        dl.addLayout(grid)
        self.skip_box = QCheckBox(tr("次の 1 回だけ飛ばす"))
        self.skip_box.setChecked(self.item.skip_once)
        dl.addWidget(self.skip_box)
        lay.addWidget(dodge_box)

        lay.addStretch(1)
        return page

    def _tab_sound(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        box = QGroupBox(tr("鳴らす音"))
        bl = QVBoxLayout(box)
        self.sound_editor = SoundEditor(self.item.sound)
        self.sound_editor.preview_requested.connect(self._preview_sound)
        self.sound_editor.preview_stopped.connect(self.engine.stop)
        bl.addWidget(self.sound_editor)
        lay.addWidget(box)

        rounds = QGroupBox(tr("スヌーズの回ごとに音を変える"))
        rl = QVBoxLayout(rounds)
        self.round_editors = {}
        for attr, caption in (("tone_round1", tr("1回目のスヌーズ")),
                              ("tone_round2", tr("2回目のスヌーズ")),
                              ("tone_round3plus", tr("3回目以降"))):
            existing = getattr(self.item.snooze, attr)
            toggle = QCheckBox(caption + tr("に別の音を使う"))
            toggle.setChecked(existing is not None)
            rl.addWidget(toggle)
            editor = SoundEditor(existing or SoundPlan(), compact=True)
            editor.preview_requested.connect(self._preview_sound)
            editor.preview_stopped.connect(self.engine.stop)
            editor.setEnabled(existing is not None)
            toggle.toggled.connect(editor.setEnabled)
            rl.addWidget(editor)
            self.round_editors[attr] = (toggle, editor)
        lay.addWidget(rounds)

        lay.addStretch(1)
        return page

    def _tab_stop(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        stop_box = QGroupBox(tr("止め方"))
        sl = QVBoxLayout(stop_box)
        self.stop_guard_editor = GuardEditor(self.item.stop_guard, theme.ACCENT)
        sl.addWidget(self.stop_guard_editor)
        form = QFormLayout()
        self.autostop_box = QSpinBox()
        self.autostop_box.setRange(0, 120)
        self.autostop_box.setSuffix(tr(" 分（0 で自動停止しない）"))
        self.autostop_box.setValue(self.item.auto_stop_minutes)
        form.addRow(tr("鳴り続ける時間"), self.autostop_box)
        self.erase_box = QCheckBox(tr("止めたらこのアラームを削除する"))
        self.erase_box.setChecked(self.item.erase_after_stop)
        form.addRow(self.erase_box)
        sl.addLayout(form)
        lay.addWidget(stop_box)

        snooze_box = QGroupBox(tr("スヌーズ"))
        nl = QVBoxLayout(snooze_box)
        self.snooze_on = QCheckBox(tr("スヌーズを使う"))
        self.snooze_on.setChecked(self.item.snooze.enabled)
        nl.addWidget(self.snooze_on)

        form = QFormLayout()
        self.snooze_minutes = QSpinBox()
        self.snooze_minutes.setRange(1, 1439)
        self.snooze_minutes.setSuffix(tr(" 分"))
        self.snooze_minutes.setValue(self.item.snooze.minutes)
        form.addRow(tr("間隔"), self.snooze_minutes)

        self.snooze_max = QSpinBox()
        self.snooze_max.setRange(0, 99)
        self.snooze_max.setSuffix(tr(" 回（0 で無制限）"))
        self.snooze_max.setValue(self.item.snooze.max_rounds)
        form.addRow(tr("最大回数"), self.snooze_max)

        self.snooze_origin = QComboBox()
        self.snooze_origin.addItem(tr("スヌーズ操作をした時刻から数える"),
                                   SnoozeOrigin.USER_ACTION)
        self.snooze_origin.addItem(tr("鳴り始めた時刻から数える"), SnoozeOrigin.RING_START)
        self.snooze_origin.setCurrentIndex(
            0 if self.item.snooze.origin == SnoozeOrigin.USER_ACTION else 1)
        form.addRow(tr("間隔の起点"), self.snooze_origin)

        self.snooze_change = QCheckBox(tr("鳴動画面で間隔を変えられるようにする"))
        self.snooze_change.setChecked(self.item.snooze.allow_interval_change)
        form.addRow(self.snooze_change)

        self.snooze_count = QCheckBox(tr("鳴動画面にスヌーズ回数を出す"))
        self.snooze_count.setChecked(self.item.snooze.show_round_count)
        form.addRow(self.snooze_count)
        nl.addLayout(form)

        nl.addWidget(QLabel(tr("スヌーズのしかた")))
        self.snooze_guard_editor = GuardEditor(self.item.snooze_guard, theme.COOL)
        nl.addWidget(self.snooze_guard_editor)

        self.snooze_on.toggled.connect(
            lambda on: [w.setEnabled(on) for w in
                        (self.snooze_minutes, self.snooze_max, self.snooze_origin,
                         self.snooze_change, self.snooze_count,
                         self.snooze_guard_editor)])
        self.snooze_on.toggled.emit(self.snooze_on.isChecked())
        lay.addWidget(snooze_box)

        lay.addStretch(1)
        return page

    def _tab_screen(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        box = QGroupBox(tr("鳴動画面"))
        bl = QVBoxLayout(box)
        self.flash_box = QCheckBox(tr("画面のふちを点滅させる"))
        self.flash_box.setChecked(self.item.flash_screen)
        bl.addWidget(self.flash_box)
        self.shrink_box = QCheckBox(tr("文字を小さめにする"))
        self.shrink_box.setChecked(self.item.shrink_text)
        bl.addWidget(self.shrink_box)
        lay.addWidget(box)

        guard = QGroupBox(tr("誤操作の防止"))
        gl = QVBoxLayout(guard)
        self.lock_box = QCheckBox(tr("一覧の ON/OFF スイッチを固定する"))
        self.lock_box.setChecked(self.item.toggle_locked)
        gl.addWidget(self.lock_box)
        note = QLabel(tr("固定中は一覧から切り替えられません。解除はこの画面か、"
                      "一覧の右クリックメニューから行えます。"))
        note.setWordWrap(True)
        note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        gl.addWidget(note)
        lay.addWidget(guard)

        lay.addStretch(1)
        return page

    def _tab_launch(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)
        plan = self.item.launch

        note = QLabel(tr("アラームに合わせて、アプリを起動したり Web ページを開いたりします。"))
        note.setWordWrap(True)
        note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        lay.addWidget(note)

        self.launch_on = QCheckBox(tr("このアラームで連動動作を使う"))
        self.launch_on.setChecked(plan.enabled)
        lay.addWidget(self.launch_on)

        box = QGroupBox(tr("何をするか"))
        form = QFormLayout(box)

        program_row = QHBoxLayout()
        self.launch_program = QLineEdit(plan.program)
        self.launch_program.setPlaceholderText(tr("起動するファイル（省略可）"))
        program_row.addWidget(self.launch_program, 1)
        browse = QPushButton(tr("参照"))
        browse.clicked.connect(self._pick_program)
        program_row.addWidget(browse)
        form.addRow(tr("アプリ"), program_row)

        self.launch_args = QLineEdit(plan.arguments)
        self.launch_args.setPlaceholderText(tr("引数（省略可）"))
        form.addRow(tr("引数"), self.launch_args)

        self.launch_url = QLineEdit(plan.url)
        self.launch_url.setPlaceholderText(tr("https://…（省略可）"))
        form.addRow(tr("ページ"), self.launch_url)

        self.launch_when = QComboBox()
        self.launch_when.addItem(tr("鳴り始めたとき"), False)
        self.launch_when.addItem(tr("止めたとき"), True)
        self.launch_when.setCurrentIndex(1 if plan.at_stop else 0)
        form.addRow(tr("いつ"), self.launch_when)
        lay.addWidget(box)

        self.launch_note = QLabel("")
        self.launch_note.setWordWrap(True)
        self.launch_note.setStyleSheet("color: %s;" % theme.WARN)
        lay.addWidget(self.launch_note)

        caution = QLabel(tr("この設定はアプリを起動します。バックアップから読み込んだ"
                         "アラームの連動動作は、内容を確認して承認するまで動きません。"))
        caution.setWordWrap(True)
        caution.setStyleSheet("color: %s; font-size: 11px;" % theme.TEXT_SUB)
        lay.addWidget(caution)

        for widget in (self.launch_program, self.launch_args, self.launch_url):
            widget.textChanged.connect(self._check_launch)
        self.launch_on.toggled.connect(
            lambda on: [w.setEnabled(on) for w in
                        (box, self.launch_program, self.launch_args,
                         self.launch_url, self.launch_when)])
        self.launch_on.toggled.emit(self.launch_on.isChecked())
        self._check_launch()

        lay.addStretch(1)
        return page

    def _pick_program(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("起動するファイルを選ぶ"))
        if path:
            self.launch_program.setText(path)

    def _launch_value(self) -> LaunchPlan:
        return LaunchPlan(
            enabled=self.launch_on.isChecked(),
            program=self.launch_program.text().strip(),
            arguments=self.launch_args.text().strip(),
            url=self.launch_url.text().strip(),
            at_stop=bool(self.launch_when.currentData()),
            approved=True,
        )

    def _check_launch(self) -> None:
        self.launch_note.setText(check_launch(self._launch_value()))

    # ---- 保存 -------------------------------------------------------------
    def _preview_sound(self, plan: SoundPlan) -> None:
        trial = SoundPlan.from_dict(plan.to_dict())
        trial.delay_start = False
        trial.loop = False
        self.engine.start(trial)

    def _commit(self) -> None:
        self.engine.stop()
        item = self.item
        picked = self.time_field.time()
        item.hour, item.minute = picked.hour(), picked.minute()
        item.title = self.title_field.text().strip()
        item.group = self.group_box.currentData()
        item.repeat = self.repeat_editor.value()
        item.dodge_holidays = self.holiday_box.isChecked()
        item.dodge_lists = [k for k, b in self.dodge_boxes.items() if b.isChecked()]
        item.skip_once = self.skip_box.isChecked()

        item.sound = self.sound_editor.value()
        for attr, (toggle, editor) in self.round_editors.items():
            setattr(item.snooze, attr, editor.value() if toggle.isChecked() else None)

        item.stop_guard = self.stop_guard_editor.value()
        item.auto_stop_minutes = self.autostop_box.value()
        item.erase_after_stop = self.erase_box.isChecked()

        item.snooze.enabled = self.snooze_on.isChecked()
        item.snooze.minutes = self.snooze_minutes.value()
        item.snooze.max_rounds = self.snooze_max.value()
        item.snooze.origin = as_enum(SnoozeOrigin, self.snooze_origin.currentData())
        item.snooze.allow_interval_change = self.snooze_change.isChecked()
        item.snooze.show_round_count = self.snooze_count.isChecked()
        item.snooze_guard = self.snooze_guard_editor.value()

        item.flash_screen = self.flash_box.isChecked()
        item.shrink_text = self.shrink_box.isChecked()
        item.toggle_locked = self.lock_box.isChecked()
        item.launch = self._launch_value()
        self.accept()

    def result_item(self) -> WakeItem:
        return self.item

    def reject(self):
        self.engine.stop()
        super().reject()
