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
