"""画面がひととおり組み立つことと、配色・ことばの切り替えを確かめる。

表示のいらない Qt の環境で動かす。

    set QT_QPA_PLATFORM=offscreen
    python -m unittest discover -s tests
"""
import _home
_home.guard()   # 本物の %APPDATA% を触らせない。koyomi を読み込む前に済ませる

import datetime as dt
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from koyomi import i18n
from koyomi.models import ONE_SHOT, Cycle, Guard, GuardPlan, RepeatRule, WakeItem
from koyomi.player import SoundEngine
from koyomi.tasks import TodoItem, Weight
from koyomi.ui import theme
from koyomi.ui.main_window import MainWindow
from koyomi.vault import Vault

_app = QApplication.instance() or QApplication([])


def sample_vault() -> Vault:
    vault = Vault()
    vault.add(WakeItem(hour=6, minute=30, title="起床",
                       repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                         weekdays=[0, 1, 2, 3, 4]),
                       dodge_holidays=True,
                       stop_guard=GuardPlan(style=Guard.ARITHMETIC, rounds=2)))
    vault.add(WakeItem(hour=22, minute=0, title="就寝", active=False))
    vault.todos = [TodoItem(text="電池", weight=Weight.HIGH)]
    vault.timers = [{"name": "卵", "seconds": 300, "deadline": ""}]
    return vault


def quiet_engine() -> SoundEngine:
    engine = SoundEngine()
    engine.ready = False        # テスト中は音を出さない
    return engine


class Windows(unittest.TestCase):
    def setUp(self):
        i18n.set_language("ja")
        theme.apply("yoichi-kohaku")
        sheet = theme.stylesheet()
        # 同じものを当て直すと、それまでのテストで作った窓がすべて塗り直され、
        # 1 件ごとに遅くなっていく
        if _app.styleSheet() != sheet:
            _app.setStyleSheet(sheet)
        self.vault = sample_vault()
        self.engine = quiet_engine()

    def test_main_window_lists_every_alarm(self):
        from koyomi.ui.main_window import MainWindow
        win = MainWindow(self.vault, self.engine)
        try:
            self.assertEqual(len(win.rows), 2)
            soonest, owner = win.next_ring()
            self.assertIsNotNone(soonest)
            self.assertEqual(owner.title, "起床")
        finally:
            win._quitting = True
            win.close()

    def test_main_window_opens_on_english_windows(self):
        # 英語版の Windows では、今日の日付を書くところで落ちて開けなかった
        _home.english_windows(self)
        win = MainWindow(self.vault, self.engine)
        try:
            self.assertRegex(win.today_label.text(), r"^\d{4}年\d{2}月\d{2}日（.）")
        finally:
            win._quitting = True
            win.close()

    def test_alarm_editor_writes_every_tab_back(self):
        from koyomi.ui.editor import AlarmEditor
        dialog = AlarmEditor(self.vault.items[0], self.vault, self.engine)
        dialog._commit()
        saved = dialog.result_item()
        self.assertIsInstance(saved.repeat.cycle, Cycle)
        self.assertIsInstance(saved.stop_guard.style, Guard)
        self.assertEqual(saved.title, "起床")

    def test_guard_editor_hides_rows_that_do_not_apply(self):
        from koyomi.ui.editor import GuardEditor
        wanted = {
            Guard.TAP: (False, False),
            Guard.SLIDE: (False, False),
            Guard.HOLD: (False, True),
            Guard.ARITHMETIC: (True, False),
            Guard.ORDER_TAP: (True, False),
            Guard.SHAPE_MATCH: (True, False),
        }
        editor = GuardEditor(GuardPlan())
        for style, (graded, held) in wanted.items():
            editor.style_box.setCurrentIndex(list(Guard).index(style))
            self.assertIs(editor.form.isRowVisible(editor.tough_box), graded,
                          "難しさ: %s" % style.value)
            self.assertIs(editor.form.isRowVisible(editor.rounds_box), graded,
                          "出題数: %s" % style.value)
            self.assertIs(editor.form.isRowVisible(editor.hold_box), held,
                          "長押しの時間: %s" % style.value)

    def test_guard_editor_keeps_hidden_values(self):
        # 隠れている間も値は残り、選び直すと元に戻る
        from koyomi.ui.editor import GuardEditor
        editor = GuardEditor(GuardPlan(style=Guard.ARITHMETIC, rounds=5))
        editor.style_box.setCurrentIndex(list(Guard).index(Guard.TAP))
        self.assertEqual(editor.value().rounds, 5)
        editor.style_box.setCurrentIndex(list(Guard).index(Guard.ARITHMETIC))
        self.assertTrue(editor.form.isRowVisible(editor.rounds_box))
        self.assertEqual(editor.value().rounds, 5)

    def test_ring_window_caps_auto_stop_at_the_snooze_interval(self):
        from koyomi.ui.ring_window import RingWindow
        item = self.vault.items[0]
        item.auto_stop_minutes = 10
        item.snooze.enabled = True
        item.snooze.minutes = 3
        window = RingWindow(item, self.engine, hold_awake=False)
        try:
            gap = (window._deadline - window.rang_at).total_seconds()
            self.assertEqual(round(gap), 3 * 60 - 5)
        finally:
            window.close()

    def test_other_windows_open(self):
        from koyomi.ui.datelists import DateListDialog
        from koyomi.ui.timers import TimerWindow
        from koyomi.ui.todo import TodoWindow
        from koyomi.ui.worldclock import WorldClockWindow
        for build in (lambda: TimerWindow(self.vault, self.engine),
                      lambda: WorldClockWindow(self.vault),
                      lambda: TodoWindow(self.vault),
                      lambda: DateListDialog(self.vault.almanac)):
            window = build()
            window.close()

    def test_countdown_keeps_running_across_a_restart(self):
        from koyomi.ui.timers import CountdownRow
        deadline = dt.datetime.now() + dt.timedelta(days=30)
        row = CountdownRow("住民票", 30 * 86400,
                           deadline.isoformat(timespec="seconds"))
        self.assertTrue(row.running)
        self.assertGreater(row.left, 29 * 86400)
        self.assertTrue(row.snapshot()["deadline"])

    def test_countdown_that_expired_while_closed_is_finished(self):
        from koyomi.ui.timers import CountdownRow
        gone = (dt.datetime.now() - dt.timedelta(hours=1))
        row = CountdownRow("過ぎたもの", 60, gone.isoformat(timespec="seconds"))
        self.assertFalse(row.running)
        self.assertEqual(row.left, 0.0)


BELL = "C:/sounds/bell.mp3"


class Countdowns(unittest.TestCase):
    """足したらすぐ計り始めること。終わったときの音を選べること。"""

    def setUp(self):
        from koyomi.ui.timers import TimerWindow
        i18n.set_language("ja")
        self.vault = Vault()
        self.engine = quiet_engine()
        self.window = TimerWindow(self.vault, self.engine)
        self.addCleanup(self.window.close)

    def pick_file(self, path=BELL):
        from koyomi.models import ToneKind
        editor = self.window.sound_editor
        editor.kind_box.setCurrentIndex(editor.kind_box.findData(ToneKind.FILE))
        editor.path_field.setText(path)

    def test_a_quick_add_starts_at_once(self):
        self.window._add_preset(0)
        row = self.window.rows[-1]
        self.assertTrue(row.running, "足しただけで止まっている")
        self.assertTrue(self.vault.timers[-1]["deadline"])

    def test_a_new_timer_starts_at_once(self):
        self.window.min_box.setValue(2)
        before = dt.datetime.now()
        self.window._add_custom()
        row = self.window.rows[-1]
        self.assertTrue(row.running, "足しただけで止まっている")
        self.assertAlmostEqual((row.deadline - before).total_seconds(), 120, delta=2)

    def test_a_timer_to_a_date_ends_right_at_that_time(self):
        from PySide6.QtCore import QDateTime
        target = QDateTime.currentDateTime().addSecs(3600)
        self.window._flip_mode()
        self.window.target_field.setDateTime(target)
        self.window._add_custom()
        row = self.window.rows[-1]
        self.assertTrue(row.running)
        self.assertLess(abs((row.deadline - target.toPython()).total_seconds()), 1.0)

    def test_the_chosen_file_goes_with_the_timer(self):
        from koyomi.models import ToneKind
        from koyomi.ui.timers import CountdownRow
        self.pick_file()
        self.window._add_preset(0)
        saved = self.vault.timers[-1]
        self.assertEqual(saved["sound"]["kind"], "file")
        self.assertEqual(saved["sound"]["source"], BELL)
        again = CountdownRow(saved["name"], saved["seconds"], saved["deadline"],
                             saved["sound"])
        self.assertEqual(again.sound.kind, ToneKind.FILE)
        self.assertEqual(again.sound.source, BELL)
        self.assertIn("bell.mp3", again.tone.text())

    def test_each_timer_keeps_its_own_sound(self):
        from koyomi.models import ToneKind
        self.window._add_preset(0)                   # 既定の音のまま
        self.pick_file()
        self.window._add_preset(1)                   # ファイルに替えてから
        first, second = self.window.rows[-2:]
        self.assertEqual(first.sound.kind, ToneKind.BUILTIN)
        self.assertEqual(second.sound.kind, ToneKind.FILE)

    def test_the_choice_is_there_next_time(self):
        from koyomi.models import ToneKind
        from koyomi.ui.timers import TimerWindow
        self.pick_file()
        self.window.close()
        again = Vault()
        again.apply(self.vault.snapshot())            # 保存して読み戻したつもり
        reopened = TimerWindow(again, self.engine)
        self.addCleanup(reopened.close)
        chosen = reopened.sound_editor.value()
        self.assertEqual(chosen.kind, ToneKind.FILE)
        self.assertEqual(chosen.source, BELL)

    def test_timers_added_before_this_ring_the_old_tone(self):
        from koyomi.models import ToneKind
        from koyomi.ui.timers import CountdownRow
        row = CountdownRow("卵", 300)
        self.assertEqual(row.sound.kind, ToneKind.BUILTIN)
        self.assertEqual(row.sound.source, "hibiki")

    def test_the_sound_picker_stays_folded_until_asked(self):
        self.assertTrue(self.window.sound_editor.isHidden(), "一覧の場所を食っている")
        self.window.tone_toggle.setChecked(True)
        self.assertFalse(self.window.sound_editor.isHidden())
        self.window.tone_toggle.setChecked(False)
        self.assertTrue(self.window.sound_editor.isHidden())

    def test_opening_the_picker_makes_room_instead_of_squashing_it(self):
        self.window.resize(560, 660)
        with mock.patch.object(self.window, "screen", return_value=None):
            self.window.tone_toggle.setChecked(True)
        self.assertGreaterEqual(self.window.height(),
                                self.window.minimumSizeHint().height())

    def test_the_folded_line_names_the_sound(self):
        self.assertIn("ひびき", self.window.tone_summary.text())
        self.pick_file()
        self.assertIn("bell.mp3", self.window.tone_summary.text())

    def test_it_rings_its_own_sound_until_stopped(self):
        from PySide6.QtWidgets import QDialog
        from koyomi.models import ToneKind
        self.pick_file()
        self.window._add_preset(0)
        with mock.patch.object(self.engine, "start", return_value="") as played:
            with mock.patch.object(self.engine, "stop"):
                with mock.patch.object(QDialog, "exec", return_value=0):
                    self.window._on_finished(self.window.rows[-1])
        plan = played.call_args[0][0]
        self.assertEqual(plan.kind, ToneKind.FILE)
        self.assertEqual(plan.source, BELL)
        self.assertTrue(plan.loop)

    def test_a_missing_file_is_mentioned_when_it_rings(self):
        from PySide6.QtWidgets import QDialog, QLabel
        self.pick_file()
        self.window._add_preset(0)
        seen = []

        def look(dialog):
            seen.extend(label.text() for label in dialog.findChildren(QLabel))
            return 0

        notice = "指定した音声ファイルが見つからないため、内蔵音で鳴らしています。"
        with mock.patch.object(self.engine, "start", return_value=notice):
            with mock.patch.object(self.engine, "stop"):
                with mock.patch.object(QDialog, "exec", look):
                    self.window._on_finished(self.window.rows[-1])
        self.assertIn(notice, seen)


class TimeField(unittest.TestCase):
    """カーソルの下の桁がホイールで動くこと。"""

    def _roll(self, widget, x, up=True):
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QWheelEvent
        event = QWheelEvent(QPointF(x, 16), QPointF(x, 16), QPoint(0, 0),
                            QPoint(0, 120 if up else -120), Qt.NoButton,
                            Qt.NoModifier, Qt.NoScrollPhase, False)
        _app.sendEvent(widget, event)
        return widget.time()

    def test_each_part_moves_where_the_cursor_is(self):
        from PySide6.QtCore import QTime
        from koyomi.ui.widgets import TimeSpinner
        field = TimeSpinner(QTime(6, 30, 0), "HH:mm:ss")
        field.resize(170, 32)
        field.show()
        _app.processEvents()
        for x, wanted in ((14, QTime(7, 30, 0)),      # 時のあたり
                          (55, QTime(6, 31, 0)),      # 分のあたり
                          (95, QTime(6, 30, 1))):     # 秒のあたり
            field.setTime(QTime(6, 30, 0))
            self.assertEqual(self._roll(field, x), wanted, "x=%d" % x)
        field.close()

    def test_values_wrap_around(self):
        from PySide6.QtCore import QTime
        from koyomi.ui.widgets import TimeSpinner
        field = TimeSpinner(QTime(0, 0, 0), "HH:mm:ss")
        field.resize(170, 32)
        field.show()
        _app.processEvents()
        self.assertEqual(self._roll(field, 14, up=False), QTime(23, 0, 0))
        field.close()


class SundayFirst(unittest.TestCase):
    """曜日はどこでも日曜はじめに並ぶこと。保存する番号は変えないこと。"""

    def setUp(self):
        i18n.set_language("ja")
        self.vault = Vault()

    def test_the_weekday_boxes_start_on_sunday(self):
        from koyomi.ui.editor import RepeatEditor
        editor = RepeatEditor(WakeItem(), self.vault.almanac)
        row = editor.weekday_boxes[0].parentWidget().layout().itemAt(0).layout()
        texts = [row.itemAt(i).widget().text() for i in range(row.count())
                 if row.itemAt(i).widget()]
        self.assertEqual(texts, ["日", "月", "火", "水", "木", "金", "土"])

    def test_the_saved_weekday_numbers_do_not_move(self):
        from koyomi.ui.editor import RepeatEditor
        item = WakeItem(repeat=RepeatRule(cycle=Cycle.WEEKDAYS, weekdays=[3, 6]))
        editor = RepeatEditor(item, self.vault.almanac)
        self.assertEqual(editor.weekday_boxes[6].text(), "日")
        self.assertTrue(editor.weekday_boxes[6].isChecked())
        self.assertTrue(editor.weekday_boxes[3].isChecked())
        self.assertEqual(editor.value().weekdays, [3, 6])

    def test_the_nth_weekday_list_starts_on_sunday_and_keeps_the_choice(self):
        from koyomi.ui.editor import RepeatEditor
        item = WakeItem(repeat=RepeatRule(cycle=Cycle.NTH_WEEKDAY,
                                          week_index=2, weekday=2))
        editor = RepeatEditor(item, self.vault.almanac)
        self.assertEqual(editor.nth_weekday.itemText(0), "日曜日")
        self.assertEqual(editor.nth_weekday.currentText(), "水曜日")
        self.assertEqual(editor.value().weekday, 2)

    def test_the_date_list_weekdays_start_on_sunday(self):
        from koyomi.ui.datelists import DateListDialog
        dialog = DateListDialog(self.vault.almanac)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.weekday_box.itemText(0), "日曜日")
        self.assertEqual(dialog.weekday_box.itemData(0), 6)

    def test_calendars_start_on_sunday_whatever_the_os_says(self):
        from PySide6.QtCore import QLocale, Qt
        from koyomi.ui.datelists import DateListDialog
        from koyomi.ui.editor import RepeatEditor
        from koyomi.ui.timers import TimerWindow
        from koyomi.ui.todo import TodoEditor
        QLocale.setDefault(QLocale(QLocale.German, QLocale.Germany))
        self.addCleanup(QLocale.setDefault, QLocale.system())
        self.assertEqual(QLocale().firstDayOfWeek(), Qt.Monday, "月曜はじめの地域になっていない")
        editor = RepeatEditor(WakeItem(), self.vault.almanac)
        dates = DateListDialog(self.vault.almanac)
        timers = TimerWindow(self.vault, quiet_engine())
        todo = TodoEditor(TodoItem())
        for window in (dates, timers, todo):
            self.addCleanup(window.close)
        fields = [editor.on_date, editor.step_anchor, editor.annual_date,
                  editor.cycle_anchor, timers.target_field, todo.due_field]
        calendars = [self.opened(field) for field in fields] + [dates.calendar]
        self.assertEqual({c.firstDayOfWeek() for c in calendars}, {Qt.Sunday})

    @staticmethod
    def opened(field):
        """利用者が日付欄を押したときと同じ順で、カレンダーを取り出す。"""
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        press = QMouseEvent(QEvent.MouseButtonPress, QPointF(4, 4), QPointF(4, 4),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        _app.sendEvent(field, press)
        return field.calendarWidget()

    def test_date_fields_do_not_build_their_calendars_up_front(self):
        # 先に作ると日付欄ごとにカレンダーを抱え、編集画面もテストも重くなる
        from PySide6.QtWidgets import QCalendarWidget
        from koyomi.ui.editor import RepeatEditor
        editor = RepeatEditor(WakeItem(), self.vault.almanac)
        for field in (editor.on_date, editor.step_anchor,
                      editor.annual_date, editor.cycle_anchor):
            self.assertIsNone(field.findChild(QCalendarWidget))


class NthWeeks(unittest.TestCase):
    """毎月・第n曜日で、週を複数選べること。"""

    def setUp(self):
        i18n.set_language("ja")
        self.vault = Vault()

    def editor(self, **kw):
        from koyomi.ui.editor import RepeatEditor
        item = WakeItem(repeat=RepeatRule(cycle=Cycle.NTH_WEEKDAY, **kw))
        return RepeatEditor(item, self.vault.almanac)

    @staticmethod
    def ticked(editor):
        return [n for n, box in editor.week_boxes.items() if box.isChecked()]

    def test_second_and_fourth_thursday_fit_in_one_alarm(self):
        editor = self.editor(week_index=1, weekday=3)
        editor.week_boxes[2].setChecked(True)
        editor.week_boxes[4].setChecked(True)
        editor.week_boxes[1].setChecked(False)
        rule = editor.value()
        self.assertEqual(rule.week_indexes, [2, 4])
        self.assertEqual(rule.week_index, 2)      # 週を 1 つしか読めない版への控え
        self.assertEqual(rule.weekday, 3)

    def test_the_weeks_run_from_the_first_to_the_last(self):
        editor = self.editor()
        self.assertEqual([box.text() for box in editor.week_boxes.values()],
                         ["第1", "第2", "第3", "第4", "第5", "最終"])

    def test_it_opens_with_the_saved_weeks_ticked(self):
        editor = self.editor(week_indexes=[2, 0], weekday=3)
        self.assertEqual(self.ticked(editor), [2, 0])
        self.assertEqual(editor.nth_weekday.currentText(), "木曜日")

    def test_an_alarm_saved_with_one_week_opens_with_that_week(self):
        editor = self.editor(week_index=0, weekday=4)
        self.assertEqual(self.ticked(editor), [0])
        self.assertEqual(editor.value().week_indexes, [0])

    def test_the_last_ticked_week_cannot_be_cleared(self):
        editor = self.editor(week_index=3, weekday=3)
        editor.week_boxes[3].setChecked(False)
        self.assertTrue(editor.week_boxes[3].isChecked())
        self.assertEqual(editor.value().week_indexes, [3])

    def test_a_week_that_cannot_exist_opens_as_the_first(self):
        editor = self.editor(week_index=7, weekday=3)
        self.assertEqual(self.ticked(editor), [1])
        self.assertEqual(editor.value().week_indexes, [1])


class RepeatPicker(unittest.TestCase):
    """繰り返しの選択肢と、その入力欄の対応。"""

    def setUp(self):
        from koyomi.ui.editor import RepeatEditor
        i18n.set_language("ja")
        self.vault = Vault()
        self.editor = RepeatEditor(WakeItem(), self.vault.almanac)

    def test_every_choice_has_its_own_page(self):
        # 並び順で頁を選んでいるので、数がずれると別の欄が出てしまう
        self.assertEqual(self.editor.cycle_box.count(), len(list(Cycle)))
        self.assertEqual(self.editor.stack.count(), len(list(Cycle)))
        for index in range(self.editor.cycle_box.count()):
            self.editor.cycle_box.setCurrentIndex(index)
            self.assertEqual(self.editor.stack.currentIndex(), index)

    def test_every_day_is_offered_on_its_own(self):
        labels = [self.editor.cycle_box.itemText(i)
                  for i in range(self.editor.cycle_box.count())]
        self.assertIn("毎日", labels)
        self.assertIn("曜日を指定", labels)

    def test_choosing_every_day_needs_nothing_else(self):
        self.editor.cycle_box.setCurrentIndex(list(Cycle).index(Cycle.EVERY_DAY))
        rule = self.editor.value()
        self.assertIs(rule.cycle, Cycle.EVERY_DAY)
        self.assertEqual(rule.weekdays, [])
        self.assertEqual(rule.anchor, "")

    def test_it_opens_on_the_saved_choice(self):
        from koyomi.models import RepeatRule
        from koyomi.ui.editor import RepeatEditor
        item = WakeItem(repeat=RepeatRule(cycle=Cycle.EVERY_DAY))
        again = RepeatEditor(item, self.vault.almanac)
        self.assertEqual(again.cycle_box.currentText(), "毎日")
        self.assertIs(again.value().cycle, Cycle.EVERY_DAY)

    def test_it_takes_only_the_room_the_chosen_page_needs(self):
        # いちばん背の高い「曜日を指定」に揃えると、「繰り返さない」の下が大きく空く
        self.editor.cycle_box.setCurrentIndex(list(Cycle).index(Cycle.WEEKDAYS))
        tall = self.editor.sizeHint().height()
        self.editor.cycle_box.setCurrentIndex(list(Cycle).index(Cycle.SINGLE))
        short = self.editor.sizeHint().height()
        self.assertLess(short, tall - 100)


class SilentRun(unittest.TestCase):
    """画面を出さずに、ついでにやることだけ済ませるアラーム。"""

    def setUp(self):
        from koyomi.actions import LaunchPlan
        i18n.set_language("ja")
        self.vault = Vault()
        self.item = WakeItem(hour=9, minute=0, title="バックアップ",
                             silent_run=True)
        self.item.launch = LaunchPlan(enabled=True, program="どこかの.exe")
        self.vault.add(self.item)
        self.win = MainWindow(self.vault, quiet_engine())
        self.addCleanup(self._shut)
        self.notices = []
        self.win.tray.showMessage = lambda *a, **k: self.notices.append(a)
        self.win.tray.isVisible = lambda: True

    def _shut(self):
        self.win._quitting = True
        self.win.close()

    def _fire(self, item=None):
        from koyomi.ui import main_window as mw
        with mock.patch.object(mw.actions, "run_now",
                               return_value="どこかの.exe を起動しました。") as ran:
            self.win._on_due(item or self.item, 0)
        return ran

    def test_no_ringing_screen_appears(self):
        ran = self._fire()
        self.assertTrue(ran.called, "連動動作が動かなかった")
        self.assertEqual(self.win.ring_windows, {}, "画面が出てしまった")
        self.assertFalse(self.win.director.is_held(self.item.uid),
                         "鳴りっぱなしの扱いのまま残っている")

    def test_the_notice_can_be_turned_on_and_off(self):
        self._fire()
        self.assertEqual(len(self.notices), 1)
        self.assertIn("バックアップ", self.notices[0][1])

        self.notices.clear()
        self.item.notify_silent_run = False
        ran = self._fire()
        self.assertTrue(ran.called, "通知を切ったら連動まで止まった")
        self.assertEqual(self.notices, [])

    def test_an_ordinary_alarm_still_shows_its_screen(self):
        from koyomi.ui import main_window as mw
        plain = WakeItem(hour=9, minute=1, title="ふつう")
        self.vault.add(plain)
        with mock.patch.object(mw.actions, "run", return_value=""):
            self.win._on_due(plain, 0)
        self.assertIn(plain.uid, self.win.ring_windows)

    def test_the_timing_choice_is_ignored(self):
        # 「止めたとき」に設定してあっても、止める操作が無いので実行する
        from koyomi import actions
        self.item.launch.at_stop = True
        with mock.patch.object(actions, "_launch", return_value=True) as opened:
            with mock.patch.object(actions.os.path, "exists", return_value=True):
                note = actions.run_now(self.item.launch)
        self.assertTrue(opened.called)
        self.assertTrue(note)

    def test_a_trial_does_not_launch_anything(self):
        from koyomi.ui import main_window as mw
        with mock.patch.object(mw.actions, "run_now") as never:
            self.win.preview_ring(self.item)
        never.assert_not_called()
        self.assertEqual(self.win.ring_windows, {})
        self.assertEqual(len(self.notices), 1)

    def test_the_list_shows_a_marker(self):
        from koyomi.ui.widgets import Pill
        row = self.win.rows[0]
        labels = [p.text() for p in row.findChildren(Pill)]
        self.assertIn("画面なし", labels)

    def test_the_setting_survives_a_save_and_load(self):
        again = Vault()
        again.apply(self.vault.snapshot())
        self.assertTrue(again.items[0].silent_run)
        self.assertTrue(again.items[0].notify_silent_run)


class TryTheCompanionNow(unittest.TestCase):
    """連動動作を、時刻を待たずにその場で試せること。"""

    def setUp(self):
        from koyomi.ui.editor import AlarmEditor
        i18n.set_language("ja")
        self.vault = sample_vault()
        self.editor = AlarmEditor(self.vault.items[0], self.vault,
                                  quiet_engine())
        self.editor.launch_on.setChecked(True)
        self.editor.launch_program.setText("C:/Windows/notepad.exe")
        self.editor.launch_args.setText("--x")

    def _press(self):
        from koyomi.ui import editor as ed
        with mock.patch.object(ed, "run_now",
                               return_value="notepad.exe を起動しました。") as ran, \
             mock.patch.object(ed.QMessageBox, "information") as shown:
            self.editor._try_launch()
        return ran, shown

    def test_the_button_waits_for_the_companion_to_be_switched_on(self):
        self.editor.launch_on.setChecked(False)
        self.assertFalse(self.editor.launch_try.isEnabled())
        self.editor.launch_on.setChecked(True)
        self.assertTrue(self.editor.launch_try.isEnabled())

    def test_it_runs_what_is_written_on_the_screen(self):
        ran, shown = self._press()
        ran.assert_called_once()
        self.assertEqual(ran.call_args[0][0].program, "C:/Windows/notepad.exe")
        self.assertTrue(shown.called, "結果が出なかった")

    def test_a_silent_alarm_is_tried_the_same_quiet_way(self):
        self.editor.silent_on.setChecked(True)
        ran, _ = self._press()
        self.assertTrue(ran.call_args[1]["quietly"])
        self.editor.silent_on.setChecked(False)
        ran, _ = self._press()
        self.assertFalse(ran.call_args[1]["quietly"])

    def test_nothing_to_try_is_said_plainly(self):
        self.editor.launch_program.setText("")
        self.editor.launch_args.setText("")
        ran, _ = self._press()
        self.assertFalse(ran.called)
        self.assertIn("指定されていません", self.editor.launch_note.text())

    def test_a_setting_that_cannot_work_stops_the_trial(self):
        self.editor.launch_program.setText("Z:/どこにもない.exe")
        ran, _ = self._press()
        self.assertFalse(ran.called, "見つからないものを動かそうとした")
        self.assertIn("見つかりません", self.editor.launch_note.text())

    def test_the_report_shows_each_argument_whole(self):
        from koyomi.actions import LaunchPlan
        script = chr(92).join(("D:", "XAMPP", "htdocs", "test.php"))
        plan = LaunchPlan(enabled=True, program="C:/Windows/notepad.exe",
                          arguments=script + " --station")
        lines = self.editor._trial_report(plan, "動かしました。", quiet=False)
        self.assertTrue(any(line.endswith(script) for line in lines),
                        "引数のパスが丸ごと出ていない: %r" % lines)
        self.assertTrue(any(line.endswith("--station") for line in lines))

    def test_the_quiet_report_points_at_the_log(self):
        from koyomi.actions import LaunchPlan
        plan = LaunchPlan(enabled=True, program="C:/Windows/notepad.exe")
        lines = self.editor._trial_report(plan, "動かしました。", quiet=True)
        self.assertTrue(any("actions.log" in line for line in lines))

    def test_the_log_button_says_so_when_there_is_nothing_yet(self):
        from koyomi.ui import editor as ed
        with mock.patch.object(ed.os.path, "exists", return_value=False), \
             mock.patch.object(ed.QMessageBox, "information") as shown, \
             mock.patch.object(ed.os, "startfile", create=True) as opened:
            self.editor._show_work_log()
        self.assertFalse(opened.called, "無い記録を開こうとした")
        self.assertIn("まだ記録はありません", shown.call_args[0][2])


class SkipOnTheCard(unittest.TestCase):
    """一覧の札が、飛ばす回を過ぎたら外れて、そのことが保存されること。"""

    def setUp(self):
        from koyomi import planner
        from koyomi.ui.main_window import MainWindow
        i18n.set_language("ja")
        self.planner = planner
        self.vault = Vault()
        self.item = WakeItem(hour=3, minute=0, title="発送依頼日",
                             repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                               weekdays=[3, 6]))
        planner.arm_skip(self.item, self.vault.almanac,
                         dt.datetime(2026, 9, 12, 10, 0))
        self.vault.add(self.item)
        self.saves = mock.patch.object(Vault, "save").start()
        self.addCleanup(mock.patch.stopall)
        self.win = MainWindow(self.vault, quiet_engine())
        self.addCleanup(self._shut)

    def _shut(self):
        self.win._quitting = True
        self.win.close()

    def pills(self) -> list:
        row = self.win.rows[0]
        return [row.pills.itemAt(i).widget().text()
                for i in range(row.pills.count())
                if row.pills.itemAt(i).widget()]

    def test_the_card_names_the_day(self):
        self.assertIn("9/13(日) は飛ばす", self.pills())

    def test_the_label_goes_and_is_saved_once_the_time_passes(self):
        self.saves.reset_mock()
        self.win.director._last_check = dt.datetime(2026, 9, 13, 2, 59, 59, 900000)
        self.win.director._on_tick(dt.datetime(2026, 9, 13, 3, 0, 0, 150000))
        self.assertFalse(self.item.skip_once)
        self.assertNotIn("9/13(日) は飛ばす", self.pills(), "札が残っている")
        self.assertTrue(self.saves.called, "下ろしたことが保存されていない")
        self.assertIn("「発送依頼日」は飛ばす回が過ぎました", self.win.status.text())

    def test_the_menu_toggle_sets_and_clears_the_day(self):
        self.win.toggle_skip(self.item)
        self.assertFalse(self.item.skip_once)
        self.assertEqual(self.item.skip_on, "")
        self.win.toggle_skip(self.item)
        self.assertTrue(self.item.skip_once)
        self.assertNotEqual(self.item.skip_on, "")

    def test_the_editor_keeps_the_day_through_a_save(self):
        from koyomi.ui.editor import AlarmEditor
        self.planner.arm_skip(self.item, self.vault.almanac)   # いまから数えた次の回
        dialog = AlarmEditor(self.item, self.vault, quiet_engine())
        dialog._commit()
        self.assertEqual(dialog.result_item().skip_on, self.item.skip_on)

    def test_unticking_in_the_editor_clears_the_day(self):
        from koyomi.ui.editor import AlarmEditor
        self.planner.arm_skip(self.item, self.vault.almanac)
        dialog = AlarmEditor(self.item, self.vault, quiet_engine())
        dialog.skip_box.setChecked(False)
        dialog._commit()
        saved = dialog.result_item()
        self.assertFalse(saved.skip_once)
        self.assertEqual(saved.skip_on, "")

    def test_what_passed_while_closed_is_counted_before_watching_starts(self):
        # 見張りが先に回ると、過ぎた「次は飛ばす」を下ろしてから取りこぼしを
        # 数えるので、飛ばした回が「鳴らせなかったアラーム」に出てしまう
        from koyomi.director import RingDirector
        from koyomi.ui.main_window import MainWindow
        order = []
        real_sweep, real_start = RingDirector.sweep_missed, RingDirector.start

        def sweep(director, *args, **kwargs):
            order.append("sweep")
            return real_sweep(director, *args, **kwargs)

        def start(director):
            order.append("start")
            return real_start(director)

        with mock.patch.object(RingDirector, "sweep_missed", sweep):
            with mock.patch.object(RingDirector, "start", start):
                win = MainWindow(self.vault, quiet_engine())
        win._quitting = True
        win.close()
        self.assertEqual(order[:2], ["sweep", "start"])


class SilenceHidesWhatDoesNotApply(unittest.TestCase):
    """画面を出さない設定にすると、関わりのない欄が引っ込む。"""

    def setUp(self):
        from koyomi.ui.editor import AlarmEditor
        i18n.set_language("ja")
        self.vault = sample_vault()
        self.editor = AlarmEditor(self.vault.items[0], self.vault,
                                  quiet_engine())

    def test_the_ringing_settings_step_aside(self):
        ed = self.editor
        self.assertTrue(ed.tabs.isTabVisible(1))
        ed.silent_on.setChecked(True)
        self.assertFalse(ed.tabs.isTabVisible(1), "音のタブが残っている")
        self.assertTrue(ed.snooze_group.isHidden())
        self.assertTrue(ed.ring_look_group.isHidden())
        self.assertTrue(ed.stop_guard_editor.isHidden())
        self.assertFalse(ed.stop_form.isRowVisible(ed.autostop_box))
        self.assertFalse(ed.launch_form.isRowVisible(ed.launch_when))

    def test_what_has_nothing_to_do_with_the_screen_stays(self):
        ed = self.editor
        ed.repeat_editor.cycle_box.setCurrentIndex(list(Cycle).index(Cycle.SINGLE))
        ed.silent_on.setChecked(True)
        self.assertFalse(ed.erase_box.isHidden())   # 済んだら削除
        self.assertFalse(ed.lock_box.isHidden())    # スイッチの固定

    def test_the_delete_box_speaks_of_running_instead_of_ringing(self):
        ed = self.editor
        ed.silent_on.setChecked(True)
        self.assertEqual(ed.erase_box.text(), "実行したらこのアラームを削除する")
        ed.silent_on.setChecked(False)
        self.assertEqual(ed.erase_box.text(), "鳴り終わったらこのアラームを削除する")

    def test_the_notice_box_follows_the_main_one(self):
        ed = self.editor
        self.assertFalse(ed.silent_notify.isEnabled())
        ed.silent_on.setChecked(True)
        self.assertTrue(ed.silent_notify.isEnabled())

    def test_unchecking_puts_everything_back(self):
        ed = self.editor
        ed.silent_on.setChecked(True)
        ed.silent_on.setChecked(False)
        self.assertTrue(ed.tabs.isTabVisible(1))
        self.assertFalse(ed.snooze_group.isHidden())
        self.assertTrue(ed.launch_form.isRowVisible(ed.launch_when))

    def test_both_choices_are_written_back(self):
        ed = self.editor
        ed.silent_on.setChecked(True)
        ed.silent_notify.setChecked(False)
        ed._commit()
        saved = ed.result_item()
        self.assertTrue(saved.silent_run)
        self.assertFalse(saved.notify_silent_run)


class DeleteAfterRinging(unittest.TestCase):
    """鳴り終わったら削除する指定。止め方によらず、鳴り終えたら一覧から消える。"""

    def setUp(self):
        i18n.set_language("ja")
        self.vault = Vault()
        self.item = WakeItem(hour=9, minute=0, title="歯医者", erase_after_stop=True)
        self.vault.add(self.item)
        mock.patch.object(Vault, "save").start()
        self.addCleanup(mock.patch.stopall)
        self.win = MainWindow(self.vault, quiet_engine())
        self.addCleanup(self._shut)

    def _shut(self):
        self.win._quitting = True
        self.win.close()

    def listed(self) -> list:
        return [item.uid for item in self.vault.items]

    def pills(self) -> list:
        row = self.win.rows[0]
        return [row.pills.itemAt(i).widget().text()
                for i in range(row.pills.count())
                if row.pills.itemAt(i).widget()]

    def test_stopping_it_deletes_it(self):
        self.win._on_ring_stopped(self.item)
        self.assertEqual(self.listed(), [])
        self.assertEqual(self.win.rows, [], "一覧に札が残っている")

    def test_it_is_deleted_when_it_stops_by_itself(self):
        # 席を外していて自動で止まったときも、鳴り終えたことに変わりはない
        self.item.snooze.enabled = False
        self.win._on_ring_auto_stopped(self.item)
        self.assertEqual(self.listed(), [])

    def test_a_snooze_still_to_come_keeps_it(self):
        self.win._on_ring_auto_stopped(self.item)      # スヌーズは既定で使う
        self.assertEqual(self.listed(), [self.item.uid])
        self.assertTrue(self.win.director.is_snoozing(self.item.uid))

    def test_it_is_deleted_when_the_snoozes_run_out(self):
        self.item.snooze.max_rounds = 1
        self.win.director.begin_snooze(self.item, dt.datetime.now())
        self.win._on_ring_snoozed(self.item, 5)
        self.assertEqual(self.listed(), [])

    def test_a_ring_let_go_for_another_stays_as_off(self):
        # 重なって見送った回は鳴っていないので、消さずに OFF で残す
        self.vault.prefs.overlap_policy = "stop"
        self.win._handle_overlap(self.item, 0)
        self.assertEqual(self.listed(), [self.item.uid])
        self.assertFalse(self.item.active)

    def test_a_repeating_alarm_stays(self):
        self.item.repeat = RepeatRule(cycle=Cycle.EVERY_DAY)
        self.win._on_ring_stopped(self.item)
        self.assertEqual(self.listed(), [self.item.uid])
        self.assertTrue(self.item.active)

    def test_one_run_without_a_screen_goes_too(self):
        from koyomi.ui import main_window as mw
        self.item.silent_run = True
        with mock.patch.object(mw.actions, "run_now", return_value=""):
            self.win._on_due(self.item, 0)
        self.assertEqual(self.listed(), [])

    def test_the_card_says_it_will_go(self):
        self.assertIn("済んだら削除", self.pills())
        self.item.repeat = RepeatRule(cycle=Cycle.EVERY_DAY)
        self.win.reload()
        self.assertNotIn("済んだら削除", self.pills(), "繰り返すものは消えないのに札が出る")


class DeleteBoxInTheEditor(unittest.TestCase):
    """「鳴り終わったら削除」は、繰り返しを選ぶところに、1 回きりのときだけ出る。"""

    def setUp(self):
        from koyomi.ui.editor import AlarmEditor
        i18n.set_language("ja")
        self.vault = Vault()
        self.editor = AlarmEditor(WakeItem(erase_after_stop=True), self.vault,
                                  quiet_engine())

    def pick(self, cycle) -> None:
        self.editor.repeat_editor.cycle_box.setCurrentIndex(list(Cycle).index(cycle))

    def test_it_sits_on_the_tab_where_the_repeat_is_chosen(self):
        self.assertTrue(self.editor.tabs.widget(0).isAncestorOf(self.editor.erase_box))

    def test_it_shows_only_for_alarms_that_ring_once(self):
        for cycle in Cycle:
            self.pick(cycle)
            self.assertIs(self.editor.erase_box.isHidden(), cycle not in ONE_SHOT,
                          cycle.value)

    def test_the_choice_is_written_back(self):
        self.assertTrue(self.editor.erase_box.isChecked())
        self.editor.erase_box.setChecked(False)
        self.editor._commit()
        self.assertFalse(self.editor.result_item().erase_after_stop)


class WindowSizes(unittest.TestCase):
    """窓の大きさを覚えて、次に開いたときに戻すこと。"""

    def setUp(self):
        i18n.set_language("ja")
        self.vault = sample_vault()
        self.engine = quiet_engine()
        mock.patch.object(Vault, "save").start()
        self.addCleanup(mock.patch.stopall)

    def open_main(self):
        from koyomi.ui.main_window import MainWindow
        win = MainWindow(self.vault, self.engine)
        self.addCleanup(self._shut, win)
        return win

    @staticmethod
    def _shut(win):
        win._quitting = True
        win.close()

    @staticmethod
    def as_restored(window_class, minimum, blob):
        """同じ控えを素の窓に当てたときの大きさ。画面で削られる分も同じになる。"""
        control = window_class()
        control.setMinimumSize(minimum)
        control.restoreGeometry(blob)
        return control.size()

    def test_the_main_window_comes_back_at_the_size_it_was_left(self):
        from PySide6.QtWidgets import QMainWindow
        first = self.open_main()
        first.show()
        first.resize(790, 700)
        _app.processEvents()
        blob = first.saveGeometry()
        first.hide()                                   # トレイへ畳む
        self.assertIn("main", self.vault.prefs.window_sizes)
        second = self.open_main()                      # 起動し直す
        self.assertEqual(second.size(),
                         self.as_restored(QMainWindow, first.minimumSize(), blob))
        self.assertEqual(second.size().toTuple(), (790, 700))

    def test_a_maximized_window_stays_maximized_when_opened_from_the_tray(self):
        win = self.open_main()
        win.showMaximized()
        _app.processEvents()
        win.hide()
        win._restore_window()
        self.assertTrue(win.isMaximized(), "トレイから開くと最大化が解ける")

    def test_maximized_is_remembered_across_a_restart(self):
        first = self.open_main()
        first.showMaximized()
        _app.processEvents()
        first.hide()
        second = self.open_main()
        second._restore_window()
        self.assertTrue(second.isMaximized())

    def test_a_window_left_in_the_tray_keeps_the_old_size(self):
        first = self.open_main()
        first.show()
        first.resize(790, 700)
        _app.processEvents()
        first.hide()
        stored = self.vault.prefs.window_sizes["main"]
        second = self.open_main()                      # 自動起動でトレイに畳んだまま
        self._shut(second)                             # 一度も開かずに終える
        self.assertEqual(self.vault.prefs.window_sizes["main"], stored)

    def test_a_broken_note_is_ignored(self):
        self.vault.prefs.window_sizes["main"] = "壊れた控え"
        win = self.open_main()
        win.show()
        _app.processEvents()
        self.assertGreaterEqual(win.width(), win.minimumWidth())

    def test_the_timer_window_reopens_at_its_last_size(self):
        from PySide6.QtWidgets import QDialog
        win = self.open_main()
        win.open_timers()
        win.timer_window.resize(700, 720)
        _app.processEvents()
        blob = win.timer_window.saveGeometry()
        minimum = win.timer_window.minimumSize()
        win.timer_window.close()
        self.assertIsNone(win.timer_window)
        win.open_timers()
        self.assertEqual(win.timer_window.size(),
                         self.as_restored(QDialog, minimum, blob))
        self.assertEqual(win.timer_window.size().toTuple(), (700, 720))

    def test_dialogs_keep_their_size_but_still_open_over_the_main_window(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QDialog
        win = self.open_main()
        item = self.vault.items[0]
        sizes, moved = [], []

        def use(dialog):
            sizes.append(dialog.size().toTuple())
            moved.append(dialog.testAttribute(Qt.WA_Moved))
            dialog.show()
            dialog.resize(700, 680)
            _app.processEvents()
            dialog.hide()
            return QDialog.Rejected

        with mock.patch.object(QDialog, "exec", use):
            win.edit_item(item)
            self.assertEqual(self.vault.prefs.window_sizes["alarm_editor"], "700x680")
            win.edit_item(item)
        self.assertEqual(sizes[1], (700, 680))
        self.assertEqual(moved, [False, False],
                         "位置まで戻すと、本体の真ん中に出なくなる")

    def test_every_resizable_dialog_is_looked_after(self):
        from PySide6.QtWidgets import QDialog
        from koyomi.ui.placement import Placement
        win = self.open_main()
        seen = {}

        def use(dialog):
            seen[type(dialog).__name__] = dialog.findChild(Placement) is not None
            return QDialog.Rejected

        with mock.patch.object(QDialog, "exec", use):
            win.add_item()
            win.open_settings()
            win.open_bulk()
            win.open_date_lists()
        self.assertEqual(seen, {"AlarmEditor": True, "SettingsDialog": True,
                                "BulkDialog": True, "DateListDialog": True})

    def test_the_notes_survive_saving(self):
        from koyomi.models import Prefs
        self.vault.prefs.window_sizes = {"main": "AAAA", "settings": "600x700"}
        again = Prefs.from_dict(self.vault.prefs.to_dict())
        self.assertEqual(again.window_sizes, {"main": "AAAA", "settings": "600x700"})
        self.assertEqual(Prefs.from_dict({"window_sizes": "壊れた"}).window_sizes, {})

    def test_a_restored_backup_does_not_strand_the_notes(self):
        # 復元で設定の器が差し替わっても、新しい器のほうへ控える
        win = self.open_main()
        win.show()
        _app.processEvents()
        self.vault.apply(self.vault.snapshot())
        self.vault.prefs.window_sizes.clear()
        win.resize(790, 700)
        _app.processEvents()
        self.assertIn("main", self.vault.prefs.window_sizes)


class TrayHint(unittest.TestCase):
    def test_the_notice_is_shown_only_once_ever(self):
        from koyomi.ui.main_window import MainWindow
        vault = sample_vault()
        self.assertFalse(vault.prefs.tray_hint_shown)
        win = MainWindow(vault, quiet_engine())
        shown = []
        win.tray.showMessage = lambda *a, **k: shown.append(a)
        try:
            win.close()                      # 1 回目 → 案内が出る
            self.assertEqual(len(shown), 1)
            self.assertTrue(vault.prefs.tray_hint_shown)
            win.show()
            win.close()                      # 2 回目 → 黙って畳む
            win.show()
            win.close()
            self.assertEqual(len(shown), 1)
        finally:
            win._quitting = True
            win.close()

    def test_the_flag_is_kept_across_restarts(self):
        vault = sample_vault()
        vault.prefs.tray_hint_shown = True
        again = Vault()
        again.apply(vault.snapshot())
        self.assertTrue(again.prefs.tray_hint_shown)


class SingleInstance(unittest.TestCase):
    """二つ目の起動を弾いて、一つ目に知らせること。"""

    NAME = "KoyomiSoloTest"

    def test_the_second_one_is_turned_away(self):
        import time
        from koyomi.ui.solo import SoloGuard
        first = SoloGuard(self.NAME)
        self.assertTrue(first.claim())
        called = []
        first.summoned.connect(lambda: called.append(1))
        try:
            second = SoloGuard(self.NAME)
            self.assertFalse(second.claim(), "二つ目が窓口を取れてしまった")
            for _ in range(30):
                _app.processEvents()
                time.sleep(0.02)
                if called:
                    break
            self.assertTrue(called, "一つ目に呼び出しが届かなかった")
        finally:
            first.release()

    def test_the_name_is_free_again_after_release(self):
        from koyomi.ui.solo import SoloGuard
        first = SoloGuard(self.NAME)
        self.assertTrue(first.claim())
        first.release()
        second = SoloGuard(self.NAME)
        self.assertTrue(second.claim())
        second.release()


class Appearance(unittest.TestCase):
    def test_every_palette_builds(self):
        catalogue = theme.catalog()
        self.assertEqual(len(catalogue), 27)
        for key in catalogue:
            theme.apply(key)
            sheet = theme.stylesheet()
            self.assertNotIn("url()", sheet)
            self.assertGreater(len(sheet), 2000)
        theme.apply("yoichi-kohaku")

    def test_group_tints_exist_for_every_group(self):
        from koyomi.models import DEFAULT_GROUPS
        for key in DEFAULT_GROUPS:
            self.assertTrue(theme.group_tint(key).startswith("#"))


class Language(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("ja")

    def test_english_replaces_the_wording(self):
        i18n.set_language("en")
        self.assertEqual(i18n.tr("鳴らす時刻"), "Ring at")
        self.assertEqual(i18n.tr("世界時計"), "World clock")

    def test_japanese_is_the_original(self):
        i18n.set_language("ja")
        self.assertEqual(i18n.tr("鳴らす時刻"), "鳴らす時刻")

    def test_unknown_wording_falls_back(self):
        i18n.set_language("en")
        self.assertEqual(i18n.tr("対訳表に無い言葉"), "対訳表に無い言葉")

    def test_unknown_language_falls_back_to_japanese(self):
        self.assertEqual(i18n.set_language("xx"), "ja")


if __name__ == "__main__":
    unittest.main()
