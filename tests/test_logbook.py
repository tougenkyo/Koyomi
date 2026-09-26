"""起動と終了の控えを確かめる。

落ち方の見分けは、別のプロセスを本当に落として確かめる。
"""
import _home
_home.guard()   # 本物の %APPDATA% を触らせない。koyomi を読み込む前に済ませる

import datetime as dt
import faulthandler
import json
import os
import subprocess
import sys
import tempfile
import unittest

from koyomi import logbook
from koyomi.logbook import Logbook

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T0 = dt.datetime(2026, 9, 27, 0, 8, 3)

# 控えを開いてから、指定のしかたで終わる子プロセス
CHILD = """
import faulthandler, os, sys
sys.path.insert(0, {root!r})
from koyomi.logbook import Logbook
book = Logbook({folder!r})
book.open("手で起動", "0.9.test")
{ending}
"""


class Base(unittest.TestCase):
    def setUp(self):
        room = tempfile.TemporaryDirectory()
        self.addCleanup(room.cleanup)
        self.folder = room.name

    def book(self) -> Logbook:
        book = Logbook(self.folder)
        self.addCleanup(self._let_go, book)
        return book

    @staticmethod
    def _let_go(book) -> None:
        # 落ちたときの書き込み先を開いたままだと、一時フォルダを消せない
        if book._crash is not None:
            faulthandler.disable()
            book._crash.close()
            book._crash = None

    def exists(self, name: str) -> bool:
        return os.path.exists(os.path.join(self.folder, name))

    def history(self) -> list:
        with open(os.path.join(self.folder, logbook.HISTORY), encoding="utf-8") as fh:
            return fh.read().splitlines()

    def child(self, ending: str) -> int:
        code = CHILD.format(root=ROOT, folder=self.folder, ending=ending)
        done = subprocess.run([sys.executable, "-c", code], capture_output=True,
                              timeout=60)
        return done.returncode


class CleanRuns(Base):
    def test_a_normal_quit_is_written_with_its_reason(self):
        book = self.book()
        book.open(logbook.BY_HAND, "0.9.020", now=T0)
        self.assertTrue(self.exists(logbook.RUNNING), "動いている印が無い")
        book.close(logbook.BY_TRAY, now=T0 + dt.timedelta(hours=9))
        lines = self.history()
        self.assertIn("起動", lines[0])
        self.assertIn("版 0.9.020  手で起動", lines[0])
        self.assertTrue(lines[1].startswith("2026-09-27 09:08:03  終了"))
        self.assertIn("トレイのメニューから終了", lines[1])
        self.assertFalse(self.exists(logbook.RUNNING), "印が残っている")
        self.assertFalse(self.exists(logbook.CRASH), "空の crash.log が残っている")

    def test_after_a_clean_quit_the_next_start_has_nothing_to_report(self):
        first = self.book()
        first.open(logbook.BY_HAND, "0.9.020", now=T0)
        first.close(logbook.BY_MENU, now=T0 + dt.timedelta(hours=1))
        second = self.book()
        second.open(logbook.BY_HAND, "0.9.020", now=T0 + dt.timedelta(hours=2))
        self.assertIsNone(second.previous)
        self.assertFalse(any("前回" in line for line in self.history()))

    def test_closing_twice_writes_once(self):
        book = self.book()
        book.open(logbook.BY_HAND, "0.9.020", now=T0)
        book.close(logbook.BY_MENU, now=T0)
        book.close(logbook.BY_WINDOWS, now=T0)
        self.assertEqual(sum("終了" in line for line in self.history()), 1)

    def test_the_mark_is_rewritten_once_a_minute(self):
        book = self.book()
        book.open(logbook.BY_HAND, "0.9.020", now=T0)

        def alive():
            with open(os.path.join(self.folder, logbook.RUNNING), encoding="utf-8") as fh:
                return json.load(fh)["alive"]

        book.beat(T0 + dt.timedelta(seconds=40))          # 同じ分のうちは書かない
        self.assertEqual(alive(), "2026-09-27T00:08:03")
        book.beat(T0 + dt.timedelta(seconds=70))
        self.assertEqual(alive(), "2026-09-27T00:09:13")

    def test_a_second_instance_only_adds_a_line(self):
        Logbook(self.folder).note("二重起動", "先に動いていた方を前に出して、こちらは終了")
        self.assertEqual(len(self.history()), 1)
        self.assertFalse(self.exists(logbook.RUNNING))
        self.assertFalse(self.exists(logbook.CRASH))

    def test_the_history_keeps_only_the_newest_lines(self):
        path = os.path.join(self.folder, logbook.HISTORY)
        with open(path, "w", encoding="utf-8") as fh:
            for number in range(3000):
                fh.write("2026-01-01 00:00:00  起動  pid %d  %s\n" % (number, "x" * 40))
        Logbook(self.folder).note("起動", now=T0)
        lines = self.history()
        self.assertEqual(len(lines), logbook.HISTORY_KEEP + 1)
        self.assertIn("pid 2999", lines[-2])
        self.assertTrue(lines[-1].startswith("2026-09-27 00:08:03  起動"))

    def test_a_folder_that_cannot_be_written_does_not_stop_the_app(self):
        blocker = os.path.join(self.folder, "file-not-folder")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        book = Logbook(blocker)
        self.addCleanup(self._let_go, book)
        book.open(logbook.BY_HAND, "0.9.020", now=T0)
        book.beat(T0 + dt.timedelta(minutes=5))
        book.close(logbook.BY_MENU, now=T0)


class RunsThatVanished(Base):
    def test_a_mark_left_behind_is_reported_with_the_last_minute_seen(self):
        with open(os.path.join(self.folder, logbook.RUNNING), "w", encoding="utf-8") as fh:
            json.dump({"pid": 4321, "version": "0.9.019",
                       "started": "2026-09-24T07:00:00",
                       "alive": "2026-09-25T21:34:00"}, fh)
        book = self.book()
        book.open(logbook.BY_HAND, "0.9.020", now=T0)
        self.assertEqual(book.previous["pid"], 4321)
        self.assertEqual(book.previous["alive"], dt.datetime(2026, 9, 25, 21, 34))
        self.assertFalse(book.previous["crashed"])
        report = self.history()[0]
        self.assertIn("前回は終了の操作を通らずに消えた", report)
        self.assertIn("前回 pid 4321（2026-09-24 07:00:00 起動、版 0.9.019）", report)
        self.assertIn("最後に動いていたのは 2026-09-25 21:34 ごろ", report)
        self.assertIn("異常終了の記録: なし", report)
        # 印はこの起動のものに置き換わる
        with open(os.path.join(self.folder, logbook.RUNNING), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["pid"], os.getpid())

    def test_a_killed_run_leaves_no_crash_record(self):
        code = self.child("os._exit(1)")          # 後片付けをせずに消える
        self.assertEqual(code, 1)
        book = self.book()
        book.open(logbook.BY_HAND, "0.9.020")
        self.assertIsNotNone(book.previous, "消えたことに気づいていない")
        self.assertFalse(book.previous["crashed"])
        self.assertIsNotNone(book.previous["alive"])
        self.assertFalse(self.exists(logbook.ERROR))

    def test_a_crash_is_kept_in_the_error_log(self):
        code = self.child("faulthandler._sigsegv()")
        self.assertNotEqual(code, 0)
        book = self.book()
        book.open(logbook.BY_HAND, "0.9.020")
        self.assertTrue(book.previous["crashed"], "落ちたときの様子を拾えていない")
        with open(os.path.join(self.folder, logbook.ERROR), encoding="utf-8") as fh:
            kept = fh.read()
        self.assertIn("前回の異常終了", kept)
        self.assertIn("Fatal Python error", kept)
        self.assertIn("異常終了の記録: あり（error.log）", self.history()[1])

    def test_a_clean_quit_in_another_process_is_not_mistaken_for_a_crash(self):
        code = self.child("book.close('メニューボタンから終了')")
        self.assertEqual(code, 0)
        book = self.book()
        book.open(logbook.BY_HAND, "0.9.020")
        self.assertIsNone(book.previous)
        self.assertFalse(self.exists(logbook.ERROR))


if __name__ == "__main__":
    unittest.main()
