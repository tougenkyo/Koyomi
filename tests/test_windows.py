"""画面がひととおり組み立つことと、配色・ことばの切り替えを確かめる。

表示のいらない Qt の環境で動かす。

    set QT_QPA_PLATFORM=offscreen
    python -m unittest discover -s tests
"""
import datetime as dt
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from koyomi import i18n
from koyomi.models import Cycle, Guard, GuardPlan, RepeatRule, WakeItem
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
        _app.setStyleSheet(theme.stylesheet())
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
        ed.silent_on.setChecked(True)
        self.assertFalse(ed.erase_box.isHidden())   # 止めたら削除
        self.assertFalse(ed.lock_box.isHidden())    # スイッチの固定

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
