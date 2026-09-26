"""自動起動の登録と、新しい版の見つけ方・開き直し方を確かめる。"""
import _home
_home.guard()   # 本物の %APPDATA% を触らせない。koyomi を読み込む前に済ませる

import json
import subprocess
import sys
import time
import unittest
from unittest import mock

from koyomi import autostart, updater


class VersionOrder(unittest.TestCase):
    def test_parse_handles_padding_and_a_leading_v(self):
        self.assertEqual(updater.parse("0.9.003"), (0, 9, 3))
        self.assertEqual(updater.parse("v1.0.0"), (1, 0, 0))
        self.assertEqual(updater.parse("2.1"), (2, 1, 0))
        self.assertEqual(updater.parse(""), (0, 0, 0))

    def test_zero_padded_patches_compare_by_number(self):
        self.assertTrue(updater.is_newer("0.9.010", "0.9.002"))
        self.assertTrue(updater.is_newer("0.10.000", "0.9.999"))
        self.assertTrue(updater.is_newer("v1.0.0", "0.9.999"))
        self.assertFalse(updater.is_newer("0.9.002", "0.9.002"))
        self.assertFalse(updater.is_newer("0.9.001", "0.9.002"))


class LookUp(unittest.TestCase):
    """通信はせず、返ってくる中身だけ差し替えて筋道を確かめる。"""

    def test_a_release_tag_is_used_when_there_is_one(self):
        payload = json.dumps({"tag_name": "v0.9.500"})
        with mock.patch.object(updater, "_fetch", return_value=payload):
            answer = updater.look_up("someone/thing")
        self.assertTrue(answer["ok"])
        self.assertEqual(answer["version"], "0.9.500")
        self.assertEqual(answer["source"], "releases")
        self.assertTrue(answer["newer"])

    def test_it_falls_back_to_the_source_version(self):
        import urllib.error

        def answer_for(url):
            if "api.github.com" in url:
                raise urllib.error.HTTPError(url, 404, "none", None, None)
            return 'APP_NAME = "Koyomi"\nAPP_VERSION = "0.9.400"\n'

        with mock.patch.object(updater, "_fetch", side_effect=answer_for):
            answer = updater.look_up("someone/thing")
        self.assertTrue(answer["ok"])
        self.assertEqual(answer["version"], "0.9.400")
        self.assertEqual(answer["source"], "source")

    def test_a_dead_network_is_reported_not_raised(self):
        import urllib.error
        with mock.patch.object(updater, "_fetch",
                               side_effect=urllib.error.URLError("圏外")):
            answer = updater.look_up("someone/thing")
        self.assertFalse(answer["ok"])
        self.assertTrue(answer["message"])

    def test_an_unreadable_source_is_reported(self):
        import urllib.error

        def answer_for(url):
            if "api.github.com" in url:
                raise urllib.error.HTTPError(url, 404, "none", None, None)
            return "ここに版番号はありません"

        with mock.patch.object(updater, "_fetch", side_effect=answer_for):
            answer = updater.look_up("someone/thing")
        self.assertFalse(answer["ok"])
        self.assertTrue(answer["message"])


class Pulling(unittest.TestCase):
    def test_a_plain_folder_cannot_update_itself(self):
        with mock.patch.object(updater, "is_git_copy", return_value=False):
            self.assertIn("git", updater.can_pull())

    def test_local_changes_block_the_update(self):
        with mock.patch.object(updater, "is_git_copy", return_value=True), \
             mock.patch.object(updater, "_git", return_value=(True, "")), \
             mock.patch.object(updater, "has_local_changes", return_value=True):
            self.assertIn("未保存", updater.can_pull())

    def test_pull_is_not_attempted_when_blocked(self):
        with mock.patch.object(updater, "can_pull", return_value="だめ"), \
             mock.patch.object(updater, "_git") as git:
            ok, text = updater.pull()
        self.assertFalse(ok)
        self.assertEqual(text, "だめ")
        git.assert_not_called()


class Autostart(unittest.TestCase):
    def test_the_command_points_at_this_copy(self):
        command = autostart.launch_command(minimized=True)
        self.assertIn("run.pyw", command)
        self.assertIn(autostart.TRAY_FLAG, command)
        # 空白を含むパスなので引用符で囲まれていること
        self.assertTrue(command.startswith('"'))

    def test_the_tray_flag_can_be_left_out(self):
        self.assertNotIn(autostart.TRAY_FLAG,
                         autostart.launch_command(minimized=False))

    def test_the_flag_is_read_from_the_arguments(self):
        self.assertFalse(autostart.wants_tray(["run.pyw"]))
        self.assertTrue(autostart.wants_tray(["run.pyw", "--minimized"]))

    @unittest.skipUnless(autostart.IS_WINDOWS, "Windows 以外")
    def test_register_and_unregister_leave_nothing_behind(self):
        # 本物の登録名とぶつからないよう、別の名前で試す
        with mock.patch.object(autostart, "VALUE_NAME", "KoyomiSelfTest"):
            self.assertIsNone(autostart.current_command())
            self.assertEqual(autostart.enable(minimized=True), "")
            try:
                stored = autostart.current_command()
                self.assertIsNotNone(stored)
                self.assertIn("run.pyw", stored)
                self.assertTrue(autostart.points_here())
                self.assertTrue(autostart.healthy())
            finally:
                self.assertEqual(autostart.disable(), "")
            self.assertIsNone(autostart.current_command())

    @unittest.skipUnless(autostart.IS_WINDOWS, "Windows 以外")
    def test_unregistering_something_absent_is_quiet(self):
        with mock.patch.object(autostart, "VALUE_NAME", "KoyomiNotThere"):
            self.assertEqual(autostart.disable(), "")


class Relaunch(unittest.TestCase):
    """更新して開き直すとき、新しい版に前の版が終わるのを待たせる。"""

    def test_the_new_version_is_told_whom_to_wait_for(self):
        with mock.patch.object(updater.subprocess, "Popen") as popen:
            child = updater.relaunch(after=4321)
        self.assertIn("--after-update=4321", popen.call_args[0][0])
        self.assertIs(child, popen.return_value)

    def test_a_launch_that_cannot_start_returns_nothing(self):
        with mock.patch.object(updater.subprocess, "Popen", side_effect=OSError("x")):
            self.assertIsNone(updater.relaunch(after=1))

    def test_the_old_version_is_read_back_from_the_arguments(self):
        self.assertEqual(updater.predecessor(["run.pyw", "--after-update=77"]), 77)
        self.assertEqual(
            updater.predecessor(["run.pyw", "--minimized", "--after-update=5"]), 5)
        self.assertIsNone(updater.predecessor(["run.pyw"]))
        self.assertIsNone(updater.predecessor(["run.pyw", "--after-update=x"]))
        # トレイへ畳む指示と取り違えない
        self.assertFalse(autostart.wants_tray(["run.pyw", "--after-update=77"]))

    def test_waiting_ends_as_soon_as_the_process_ends(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)"])
        started = time.monotonic()
        self.assertTrue(updater.wait_for_exit(child.pid, 20))
        self.assertLess(time.monotonic() - started, 10)
        child.wait()

    def test_waiting_gives_up_at_the_limit(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            self.assertFalse(updater.wait_for_exit(child.pid, 0.3))
        finally:
            child.kill()
            child.wait()

    def test_a_process_that_is_gone_needs_no_waiting(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        self.assertTrue(updater.wait_for_exit(child.pid, 5))


if __name__ == "__main__":
    unittest.main()
