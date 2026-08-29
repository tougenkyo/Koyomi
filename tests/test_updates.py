"""自動起動の登録と、新しい版の見つけ方を確かめる。"""
import json
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
        self.assertIn("run.py", command)
        self.assertIn(autostart.TRAY_FLAG, command)
        # 空白を含むパスなので引用符で囲まれていること
        self.assertTrue(command.startswith('"'))

    def test_the_tray_flag_can_be_left_out(self):
        self.assertNotIn(autostart.TRAY_FLAG,
                         autostart.launch_command(minimized=False))

    def test_the_flag_is_read_from_the_arguments(self):
        self.assertFalse(autostart.wants_tray(["run.py"]))
        self.assertTrue(autostart.wants_tray(["run.py", "--minimized"]))

    @unittest.skipUnless(autostart.IS_WINDOWS, "Windows 以外")
    def test_register_and_unregister_leave_nothing_behind(self):
        # 本物の登録名とぶつからないよう、別の名前で試す
        with mock.patch.object(autostart, "VALUE_NAME", "KoyomiSelfTest"):
            self.assertIsNone(autostart.current_command())
            self.assertEqual(autostart.enable(minimized=True), "")
            try:
                stored = autostart.current_command()
                self.assertIsNotNone(stored)
                self.assertIn("run.py", stored)
                self.assertTrue(autostart.points_here())
                self.assertTrue(autostart.healthy())
            finally:
                self.assertEqual(autostart.disable(), "")
            self.assertIsNone(autostart.current_command())

    @unittest.skipUnless(autostart.IS_WINDOWS, "Windows 以外")
    def test_unregistering_something_absent_is_quiet(self):
        with mock.patch.object(autostart, "VALUE_NAME", "KoyomiNotThere"):
            self.assertEqual(autostart.disable(), "")


if __name__ == "__main__":
    unittest.main()
