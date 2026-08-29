"""画面がひととおり組み立つことと、配色・ことばの切り替えを確かめる。

表示のいらない Qt の環境で動かす。

    set QT_QPA_PLATFORM=offscreen
    python -m unittest discover -s tests
"""
import datetime as dt
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from koyomi import i18n
from koyomi.models import Cycle, Guard, GuardPlan, RepeatRule, WakeItem
from koyomi.player import SoundEngine
from koyomi.tasks import TodoItem, Weight
from koyomi.ui import theme
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
