"""コンソールを出さない入口（run.pyw）の受け皿を確かめる。

pythonw.exe には標準出力も標準エラーも無いので、
つまずいた跡が控えのファイルに残ることを見ておく。
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENTRY = ROOT / "run.pyw"


def load_module(name, path):
    """拡張子が .py ではないものも取り込めるよう、読み手を指定する。"""
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_file_location(name, path, loader=loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


launcher = load_module("koyomi_launcher", ENTRY)


class LogPlace(unittest.TestCase):
    def test_it_sits_next_to_the_saved_data(self):
        with tempfile.TemporaryDirectory() as room:
            with mock.patch.dict(os.environ, {"APPDATA": room}):
                path = launcher.log_path()
            self.assertTrue(path.endswith("error.log"))
            self.assertTrue(os.path.isdir(os.path.dirname(path)))


class TheJournal(unittest.TestCase):
    def setUp(self):
        self.room = tempfile.TemporaryDirectory()
        self.addCleanup(self.room.cleanup)
        patch = mock.patch.dict(os.environ, {"APPDATA": self.room.name})
        patch.start()
        self.addCleanup(patch.stop)
        self.path = pathlib.Path(self.room.name) / "Koyomi" / "error.log"

    def test_nothing_is_written_until_there_is_something_to_say(self):
        launcher.Journal()
        self.assertFalse(self.path.exists(), "黙っているのにファイルができた")

    def test_a_note_gets_a_timestamp_and_the_text(self):
        book = launcher.Journal()
        book.write("困りました\n")
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("困りました", text)
        self.assertIn("-----", text)          # 日時の見出し

    def test_an_overgrown_file_is_started_again(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("む" * launcher.LOG_LIMIT, encoding="utf-8")
        launcher.Journal().write("新しい分\n")
        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("む", text)
        self.assertIn("新しい分", text)

    def test_a_place_it_cannot_write_to_is_not_fatal(self):
        book = launcher.Journal()
        with mock.patch.object(launcher, "log_path",
                               side_effect=OSError("書けません")):
            self.assertEqual(book.write("あ"), 1)    # 例外は出さない
            self.assertEqual(book.write("い"), 1)    # 二度目も静か

    def test_it_looks_enough_like_a_stream(self):
        book = launcher.Journal()
        self.assertFalse(book.isatty())
        self.assertEqual(book.encoding, "utf-8")
        book.flush()


class Trouble(unittest.TestCase):
    def test_the_trace_is_kept_and_the_person_is_told(self):
        told = []
        kept = io.StringIO()
        try:
            raise ValueError("音が出せません")
        except ValueError:
            kind, value, chain = sys.exc_info()
            with mock.patch.object(launcher, "announce", told.append), \
                 mock.patch.object(sys, "stderr", kept):
                launcher.on_trouble(kind, value, chain)
        self.assertIn("ValueError", kept.getvalue())
        self.assertIn("音が出せません", kept.getvalue())
        self.assertEqual(len(told), 1)
        self.assertIn("音が出せません", told[0])

    def test_warnings_are_kept_out_of_the_journal(self):
        import warnings
        keep = warnings.showwarning
        try:
            launcher.hush_warnings()
            kept = io.StringIO()
            with mock.patch.object(sys, "stderr", kept):
                warnings.warn("そのうち無くなります", UserWarning)
            self.assertEqual(kept.getvalue(), "")
        finally:
            warnings.showwarning = keep


class MissingParts(unittest.TestCase):
    """関連付けが別の Python に取られていたときの言い分け。"""

    def test_it_names_the_python_that_was_used(self):
        text = launcher.missing_parts(ImportError("No module named 'PySide6'"))
        self.assertIn("PySide6", text)
        self.assertIn(sys.executable, text)
        self.assertIn("make_shortcut", text)


class Shortcut(unittest.TestCase):
    """ショートカットを作る道具。"""

    def setUp(self):
        self.maker = load_module("koyomi_shortcut", ROOT / "tools" / "make_shortcut.py")

    def test_single_quotes_are_doubled(self):
        self.assertEqual(self.maker._quoted("it's"), "'it''s'")

    def test_where_only_prints(self):
        said = io.StringIO()
        with mock.patch.object(self.maker, "build") as never,              contextlib.redirect_stdout(said):
            self.assertEqual(self.maker.main(["--where"]), 0)
        never.assert_not_called()
        self.assertIn(".lnk", said.getvalue())

    @unittest.skipUnless(sys.platform.startswith("win"), "Windows 以外")
    def test_it_writes_a_link_that_points_at_the_entry(self):
        with tempfile.TemporaryDirectory() as room:
            with mock.patch.dict(os.environ, {"APPDATA": room}):
                link = self.maker.build(os.path.join(room, "置き場"))
            self.assertTrue(os.path.exists(link))
            blob = pathlib.Path(link).read_bytes()
            # .lnk の中では文字が UTF-16 で並んでいる
            self.assertIn("run.pyw".encode("utf-16-le"), blob)
            self.assertIn("pythonw".encode("utf-16-le"), blob)


PNG_MARK = bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10])


class IconForTheShortcut(unittest.TestCase):
    def test_the_ico_holds_several_sizes_of_png(self):
        import struct
        from koyomi.tonesmith import app_icon_ico
        blob = app_icon_ico()
        _, kind, count = struct.unpack("<HHH", blob[:6])
        self.assertEqual(kind, 1)               # 1 = アイコン
        self.assertEqual(count, 4)
        for i in range(count):
            entry = blob[6 + 16 * i:22 + 16 * i]
            _, _, _, _, _, _, size, offset = struct.unpack("<BBBBHHII", entry)
            self.assertEqual(blob[offset:offset + 8], PNG_MARK)
            self.assertEqual(len(blob[offset:offset + size]), size)


class BothEntries(unittest.TestCase):
    def test_the_two_doors_lead_to_the_same_room(self):
        for door in ("run.py", "run.pyw"):
            text = (ROOT / door).read_text(encoding="utf-8")
            self.assertIn("from koyomi.ui.app import run", text, door)


if __name__ == "__main__":
    unittest.main()
