"""保存と読み直し、連動動作の隔離を確かめる。"""
import datetime as dt
import os
import pathlib
import tempfile
import unittest

from koyomi.actions import LaunchPlan, check, is_program, run
from koyomi.models import (Cycle, Guard, GuardPlan, ListOrder, RepeatRule,
                           SnoozeOrigin, ToneKind, Toughness, WakeItem,
                           as_enum)
from koyomi.tasks import TodoItem, Weight
from koyomi.vault import Vault


class Serialisation(unittest.TestCase):
    def test_alarm_survives_a_round_trip(self):
        item = WakeItem(hour=6, minute=30, title="起床", group="b")
        item.repeat = RepeatRule(cycle=Cycle.NTH_WEEKDAY, week_index=2,
                                 weekday=3)
        item.stop_guard = GuardPlan(style=Guard.ARITHMETIC,
                                    toughness=Toughness.HEAVY, rounds=5)
        item.snooze.origin = SnoozeOrigin.RING_START
        item.sound.kind = ToneKind.FOLDER_PICK
        item.launch = LaunchPlan(enabled=True, url="https://example.com")
        again = WakeItem.from_dict(item.to_dict())
        self.assertEqual(again.to_dict(), item.to_dict())
        self.assertIsInstance(again.repeat.cycle, Cycle)
        self.assertIsInstance(again.stop_guard.style, Guard)
        self.assertIsInstance(again.sound.kind, ToneKind)

    def test_as_enum_recovers_plain_strings(self):
        # Qt のウィジェットに預けると素の文字列で返ってくることがある
        self.assertIs(as_enum(Cycle, "weekdays"), Cycle.WEEKDAYS)
        self.assertIs(as_enum(Guard, Guard.SLIDE), Guard.SLIDE)
        self.assertIs(as_enum(ListOrder, "知らない値"), ListOrder.TIME)

    def test_enum_survives_even_if_a_plain_string_was_assigned(self):
        item = WakeItem()
        item.repeat.cycle = "annual"            # ウィジェット由来を模す
        item.stop_guard.style = "hold"
        again = WakeItem.from_dict(item.to_dict())
        self.assertIs(again.repeat.cycle, Cycle.ANNUAL)
        self.assertIs(again.stop_guard.style, Guard.HOLD)

    def test_seconds_survive_and_show_only_when_set(self):
        plain = WakeItem(hour=6, minute=30)
        exact = WakeItem(hour=6, minute=30, second=15)
        self.assertEqual(plain.clock_text, "06:30")
        self.assertEqual(exact.clock_text, "06:30:15")
        self.assertEqual(WakeItem.from_dict(exact.to_dict()).second, 15)

    def test_an_old_store_without_seconds_still_loads(self):
        raw = WakeItem(hour=6, minute=30).to_dict()
        del raw["second"]                      # 0.9.001 以前の保存を模す
        self.assertEqual(WakeItem.from_dict(raw).second, 0)

    def test_todo_round_trip(self):
        task = TodoItem(text="電池", weight=Weight.HIGH, due="2026-09-01")
        again = TodoItem.from_dict(task.to_dict())
        self.assertEqual(again.text, "電池")
        self.assertIs(again.weight, Weight.HIGH)
        self.assertEqual(again.due_date(), dt.date(2026, 9, 1))


class Store(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="koyomi-store-")
        self.path = os.path.join(self.folder, "store.json")

    def _filled(self) -> Vault:
        vault = Vault()
        vault.add(WakeItem(hour=6, minute=30, title="起床"))
        vault.groups["a"] = "しごと"
        vault.todos = [TodoItem(text="電池", weight=Weight.HIGH)]
        vault.world_zones = ["Asia/Tokyo", "Europe/Paris"]
        vault.prefs.theme = "hakua-sora"
        vault.prefs.language = "en"
        vault.almanac.add_days("L1", [dt.date(2026, 1, 1)])
        return vault

    def test_everything_comes_back(self):
        self._filled().save(self.path)
        again = Vault()
        again.load(self.path)
        self.assertEqual(len(again.items), 1)
        self.assertEqual(again.groups["a"], "しごと")
        self.assertEqual([t.text for t in again.todos], ["電池"])
        self.assertEqual(again.world_zones, ["Asia/Tokyo", "Europe/Paris"])
        self.assertEqual(again.prefs.theme, "hakua-sora")
        self.assertEqual(again.prefs.language, "en")
        self.assertIn(dt.date(2026, 1, 1), again.almanac.days_of("L1"))

    def test_a_broken_file_does_not_raise(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{ これは JSON ではない")
        vault = Vault()
        vault.load(self.path)               # 例外を投げずに黙って諦める
        self.assertEqual(vault.items, [])

    def test_restoring_a_backup_holds_companion_actions(self):
        vault = self._filled()
        vault.items[0].launch = LaunchPlan(enabled=True, program="notepad.exe")
        vault.save(self.path)

        fresh = Vault()
        fresh.read_backup(self.path)
        self.assertFalse(fresh.items[0].launch.approved)
        self.assertEqual(fresh.pending_actions, [fresh.items[0].uid])
        self.assertIn("未承認", run(fresh.items[0].launch, at_stop=False))

        fresh.approve_actions(False)
        self.assertFalse(fresh.items[0].launch.enabled)
        self.assertEqual(fresh.pending_actions, [])

        other = Vault()
        other.read_backup(self.path)
        other.approve_actions(True)
        self.assertTrue(other.items[0].launch.approved)

    def test_reading_something_that_is_not_a_backup(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write('{"hello": 1}')
        with self.assertRaises(ValueError):
            Vault().read_backup(self.path)


class Companion(unittest.TestCase):
    def test_only_http_urls_pass(self):
        self.assertTrue(check(LaunchPlan(enabled=True, url="ftp://x.example")))
        self.assertTrue(check(LaunchPlan(enabled=True, url="file:///c:/x")))
        self.assertEqual(check(LaunchPlan(enabled=True,
                                          url="https://x.example")), "")

    def test_unbalanced_quotes_are_reported(self):
        plan = LaunchPlan(enabled=True, url="https://x.example",
                          arguments='"open')
        self.assertIn("引用符", check(plan))

    def test_timing_decides_whether_it_runs(self):
        plan = LaunchPlan(enabled=True, url="https://x.example", at_stop=True)
        self.assertEqual(run(plan, at_stop=False), "")

    def test_executables_and_documents_are_told_apart(self):
        # 画像や文書を直接 exec しても動かないので、関連付けに回す
        for path in ('C:/Windows/notepad.exe', 'C:/demo/run.bat',
                     'C:/demo/go.CMD', 'C:/demo/old.com'):
            self.assertTrue(is_program(path), path)
        for path in ('C:/demo/photo.png', 'C:/demo/memo.txt',
                     'C:/demo/book.pdf', 'C:/demo/clip.mp4'):
            self.assertFalse(is_program(path), path)

    def test_a_missing_file_is_reported_not_raised(self):
        plan = LaunchPlan(enabled=True, program='C:/nope/photo.png')
        self.assertIn('見つかりません', check(plan))
        self.assertIn('見つかりません', run(plan, at_stop=False))

    def test_an_image_is_a_valid_target(self):
        # 実行ファイルでなくても設定としては正しい
        root = pathlib.Path(__file__).resolve().parent.parent
        image = root / 'docs' / 'screenshots' / 'main.png'
        if not image.exists():
            self.skipTest('見本画像がない')
        self.assertEqual(check(LaunchPlan(enabled=True,
                                          program=str(image))), '')

    def test_nothing_to_do_is_quiet(self):
        self.assertEqual(check(LaunchPlan()), "")
        self.assertEqual(run(LaunchPlan(), at_stop=False), "")


if __name__ == "__main__":
    unittest.main()
