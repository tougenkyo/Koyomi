"""コンソールを出さない入口（run.pyw）の受け皿を確かめる。

pythonw.exe には標準出力も標準エラーも無いので、
つまずいた跡が控えのファイルに残ることを見ておく。
"""
import _home
_home.guard()   # 本物の %APPDATA% を触らせない。koyomi を読み込む前に済ませる

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


def fake_python(room, name, with_parts=True):
    """python が入っているように見えるフォルダを、その場ででっち上げる。"""
    folder = pathlib.Path(room) / name
    shelf = folder / "Lib" / "site-packages"
    shelf.mkdir(parents=True, exist_ok=True)
    if with_parts:
        for part in launcher.NEEDED:
            (shelf / part).mkdir(exist_ok=True)
    for exe in ("python.exe", "pythonw.exe"):
        (folder / exe).write_bytes(b"")
    return str(folder)


class HandingOver(unittest.TestCase):
    """関連付けが別の Python に取られていたときの逃げ道。"""

    def setUp(self):
        self.room = tempfile.TemporaryDirectory()
        self.addCleanup(self.room.cleanup)

    def _rooms(self, *folders):
        return mock.patch.object(launcher, "python_rooms",
                                 return_value=list(folders))

    def test_it_picks_the_one_that_has_the_parts(self):
        bare = fake_python(self.room.name, "Empty", with_parts=False)
        full = fake_python(self.room.name, "Full")
        with self._rooms(bare, full),              mock.patch.object(launcher, "HAS_CONSOLE", False):
            picked = launcher.a_python_that_works()
        self.assertEqual(picked, os.path.join(full, "pythonw.exe"))

    def test_it_skips_the_python_that_just_failed(self):
        full = fake_python(self.room.name, "Full")
        with self._rooms(full),              mock.patch.object(sys, "executable",
                               os.path.join(full, "pythonw.exe")):
            self.assertIsNone(launcher.a_python_that_works())

    def test_a_console_start_hands_over_to_a_console_python(self):
        full = fake_python(self.room.name, "Full")
        with self._rooms(full), mock.patch.object(launcher, "HAS_CONSOLE", True):
            self.assertEqual(launcher.a_python_that_works(),
                             os.path.join(full, "python.exe"))

    def test_nobody_has_the_parts(self):
        bare = fake_python(self.room.name, "Empty", with_parts=False)
        with self._rooms(bare):
            self.assertIsNone(launcher.a_python_that_works())

    def test_the_places_it_looks_are_real_folders(self):
        for folder in launcher.python_rooms():
            self.assertTrue(os.path.isdir(folder), folder)

    def test_the_handover_carries_the_arguments_and_the_flag(self):
        with mock.patch("subprocess.Popen") as opened,              mock.patch.object(sys, "argv", ["run.pyw", "--minimized"]):
            self.assertTrue(launcher.hand_over(r"C:\somewhere\pythonw.exe"))
        command = opened.call_args[0][0]
        self.assertEqual(command[0], r"C:\somewhere\pythonw.exe")
        self.assertTrue(command[1].endswith("run.pyw"))
        self.assertIn("--minimized", command)
        self.assertEqual(command.count(launcher.HANDOVER_FLAG), 1)

    def test_the_flag_is_not_doubled_on_a_second_pass(self):
        with mock.patch("subprocess.Popen") as opened,              mock.patch.object(sys, "argv",
                               ["run.pyw", launcher.HANDOVER_FLAG]):
            launcher.hand_over("pythonw.exe")
        command = opened.call_args[0][0]
        self.assertEqual(command.count(launcher.HANDOVER_FLAG), 1)

    def test_a_failed_handover_is_reported_not_raised(self):
        with mock.patch("subprocess.Popen", side_effect=OSError("だめ")):
            self.assertFalse(launcher.hand_over("pythonw.exe"))

    def test_the_entry_only_tries_once(self):
        source = ENTRY.read_text(encoding="utf-8")
        self.assertIn("if HANDOVER_FLAG not in sys.argv:", source)


class MissingParts(unittest.TestCase):
    """関連付けが別の Python に取られていたときの言い分け。"""

    def test_it_names_the_python_that_was_used(self):
        text = launcher.missing_parts(ImportError("No module named 'PySide6'"))
        self.assertIn("PySide6", text)
        self.assertIn(sys.executable, text)
        self.assertIn("install.bat", text)


class Shortcut(unittest.TestCase):
    """ショートカットを作る道具。"""

    def setUp(self):
        self.maker = load_module("koyomi_shortcut", ROOT / "tools" / "make_shortcut.py")

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

    @unittest.skipUnless(sys.platform.startswith("win"), "Windows 以外")
    def test_names_the_system_cannot_spell_are_kept(self):
        # 英語版 Windows では、日本語の名前が「?」に化けて保存できなかった。
        # 日本語版でも表せないハングルの置き場で、同じ条件を作る
        with tempfile.TemporaryDirectory() as room:
            with mock.patch.dict(os.environ, {"APPDATA": room}):
                link = self.maker.build(os.path.join(room, "한글"))
            self.assertTrue(os.path.exists(link))
            blob = pathlib.Path(link).read_bytes()
            self.assertIn("コンソールを出さずに開く".encode("utf-16-le"), blob)


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


class OneDoorOnly(unittest.TestCase):
    """入口は run.pyw ひとつ。迷わせないよう run.py は置かない。"""

    def test_the_entry_leads_into_the_package(self):
        text = ENTRY.read_text(encoding="utf-8")
        self.assertIn("from koyomi.ui.app import run", text)

    def test_there_is_no_second_entry(self):
        self.assertFalse((ROOT / "run.py").exists(),
                         "入口が 2 つあると新しく使う人が迷う")

    def test_the_autostart_registration_points_at_it(self):
        from koyomi import autostart
        self.assertTrue(autostart.entry_script().endswith("run.pyw"))
        self.assertEqual(os.path.normcase(autostart.entry_script()),
                         os.path.normcase(str(ENTRY)))


class WithAndWithoutAConsole(unittest.TestCase):
    """python で開いたか pythonw で開いたかで、伝え方を変える。"""

    def test_with_a_console_it_just_prints(self):
        said = io.StringIO()
        with mock.patch.object(launcher, "HAS_CONSOLE", True),              mock.patch.object(sys, "stderr", said),              mock.patch.object(launcher, "log_path") as never:
            launcher.announce("困りました")
        self.assertIn("困りました", said.getvalue())
        never.assert_not_called()

    def test_without_a_console_it_shows_a_window(self):
        shown = []
        with mock.patch.object(launcher, "HAS_CONSOLE", False),              mock.patch("ctypes.windll.user32.MessageBoxW",
                        lambda *a: shown.append(a)):
            launcher.announce("困りました")
        if sys.platform.startswith("win"):
            self.assertEqual(len(shown), 1)
            self.assertIn("困りました", shown[0])

    def test_the_log_is_only_mentioned_when_it_is_used(self):
        trouble = ImportError("No module named 'PySide6'")
        with mock.patch.object(launcher, "HAS_CONSOLE", True):
            self.assertNotIn("error.log", launcher.missing_parts(trouble))
        with mock.patch.object(launcher, "HAS_CONSOLE", False):
            self.assertIn("error.log", launcher.missing_parts(trouble))


if __name__ == "__main__":
    unittest.main()
