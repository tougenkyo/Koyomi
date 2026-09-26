"""PC の電源まわりを確かめる。"""
import _home
_home.guard()   # 本物の %APPDATA% を触らせない。koyomi を読み込む前に済ませる

import ctypes
import datetime as dt
import unittest
from unittest import mock

from koyomi import power


@unittest.skipUnless(power.IS_WINDOWS, "Windows だけ")
class WakeTimer(unittest.TestCase):
    """スリープ解除タイマーを、ほかのプロセスと取り合わないこと。

    名前付きのタイマーだと、テストや 2 つ目の起動が同じタイマーを開いてしまい、
    動いているアプリが PC を起こす時刻をずらしたり、消したりしていた。
    """

    def test_the_timer_has_no_name(self):
        kernel32 = ctypes.windll.kernel32
        with mock.patch.object(kernel32, "CreateWaitableTimerW", return_value=0) as made:
            power.WakeClock().arm(dt.datetime.now() + dt.timedelta(hours=1))
        self.assertIsNone(made.call_args[0][2])

    def test_one_clock_does_not_move_another(self):
        soon, later = power.WakeClock(), power.WakeClock()
        try:
            self.assertTrue(soon.arm(dt.datetime.now()))            # 1 秒後
            self.assertTrue(later.arm(dt.datetime.now() + dt.timedelta(days=30)))
            rang = ctypes.windll.kernel32.WaitForSingleObject(soon._handle, 5000)
            self.assertEqual(rang, 0, "あとの予約に、先の予約が書き換えられた")
        finally:
            soon.disarm()
            later.disarm()


if __name__ == "__main__":
    unittest.main()
