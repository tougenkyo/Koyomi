"""PC の電源まわり。

Windows の API を ctypes 経由で叩く。ほかの OS では何もせず False を返し、
呼び出し側は「使えない環境」として扱えばよい。

できること
  - 指定時刻に PC を起こす（スリープ解除タイマー）
  - 鳴動中にスリープへ入らせない
  - 指定時刻に PC をスリープさせる
"""
from __future__ import annotations

import ctypes
import datetime as dt
import subprocess
import sys
from .i18n import tr

IS_WINDOWS = sys.platform.startswith("win")

# SetThreadExecutionState のフラグ
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002

# CreateWaitableTimer 用
_TIMER_ALL_ACCESS = 0x1F0003
_WAKE_TIMER_NAME = "KoyomiWakeTimer"


class WakeClock:
    """スリープ解除タイマーを 1 本だけ抱える。

    Windows の待機可能タイマーは、生成時に「復帰させる」指定をしておくと、
    設定時刻にスリープ中のマシンを起こす。タイマーはハンドルを開いている間だけ
    有効なので、この器がハンドルの寿命を持つ。
    """

    def __init__(self):
        self._handle = None
        self._armed_for = None
        self._last_error = ""

    # ---- 情報 -------------------------------------------------------------
    @staticmethod
    def supported() -> bool:
        return IS_WINDOWS

    @property
    def armed_for(self):
        return self._armed_for

    @property
    def last_error(self) -> str:
        return self._last_error

    # ---- 予約 -------------------------------------------------------------
    def arm(self, when) -> bool:
        """``when``（ローカル時刻）に PC を起こすよう予約する。"""
        if not IS_WINDOWS or when is None:
            return False
        if self._armed_for == when and self._handle:
            return True
        self.disarm()
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.CreateWaitableTimerW(None, True, _WAKE_TIMER_NAME)
            if not handle:
                self._last_error = tr("タイマーを作成できませんでした。")
                return False

            # 実際に起きてほしい時刻より少し前に起こし、OS の復帰処理の時間を稼ぐ
            target = when - dt.timedelta(seconds=20)
            delay = (target - dt.datetime.now()).total_seconds()
            if delay < 1:
                delay = 1.0
            # 負の相対値、単位は 100 ナノ秒
            due = ctypes.c_longlong(int(-delay * 10_000_000))

            ok = kernel32.SetWaitableTimer(
                handle, ctypes.byref(due), 0, None, None, True)
            if not ok:
                kernel32.CloseHandle(handle)
                self._last_error = tr("タイマーを設定できませんでした。")
                return False
            self._handle = handle
            self._armed_for = when
            self._last_error = ""
            return True
        except (AttributeError, OSError) as err:
            self._last_error = str(err)
            return False

    def disarm(self) -> None:
        if self._handle:
            try:
                ctypes.windll.kernel32.CancelWaitableTimer(self._handle)
                ctypes.windll.kernel32.CloseHandle(self._handle)
            except (AttributeError, OSError):
                pass
        self._handle = None
        self._armed_for = None


def keep_awake(on: bool) -> bool:
    """鳴動中など、PC を寝かせたくない間だけ True を渡す。"""
    if not IS_WINDOWS:
        return False
    try:
        flags = _ES_CONTINUOUS
        if on:
            flags |= _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(flags))
        return True
    except (AttributeError, OSError):
        return False


def sleep_now(hibernate: bool = False) -> bool:
    """PC をスリープ（または休止）させる。"""
    if not IS_WINDOWS:
        return False
    try:
        keep_awake(False)
        return bool(ctypes.windll.powrprof.SetSuspendState(
            ctypes.c_bool(hibernate), ctypes.c_bool(False), ctypes.c_bool(False)))
    except (AttributeError, OSError):
        return False


_POLICY_LABELS = {0: "無効", 1: "有効", 2: "重要なタイマーのみ"}


def _run_powercfg(args) -> tuple:
    """powercfg を叩いて (成功したか, 文字列) を返す。"""
    try:
        done = subprocess.run(["powercfg"] + list(args), capture_output=True,
                              timeout=10, creationflags=0x08000000)
    except (OSError, subprocess.SubprocessError) as err:
        return False, str(err)
    blob = done.stdout if done.returncode == 0 else (done.stderr or done.stdout)
    for encoding in ("cp932", "utf-8"):
        try:
            text = blob.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = repr(blob)
    return done.returncode == 0, text.strip()


def wake_timer_policy() -> tuple:
    """(コンセント時, バッテリー時) のスリープ解除タイマー設定。

    分からなければ ``None`` を返す。この照会は管理者権限が要らない。
    """
    ok, text = _run_powercfg(["/query", "SCHEME_CURRENT", "SUB_SLEEP", "RTCWAKE"])
    if not ok:
        return None, None
    found = []
    for line in text.splitlines():
        if "0x" in line and ("AC" in line or "DC" in line):
            try:
                found.append(int(line.strip().split()[-1], 16))
            except ValueError:
                found.append(None)
    while len(found) < 2:
        found.append(None)
    return found[0], found[1]


def wake_timer_report() -> str:
    """スリープ解除タイマーが使える状態かを、言葉にして返す。"""
    if not IS_WINDOWS:
        return tr("この OS では確認できません。")

    plugged, battery = wake_timer_policy()
    lines = []
    if plugged is None and battery is None:
        lines.append(tr("電源設定を読み取れませんでした。"))
    else:
        lines.append(tr("スリープ解除タイマーの許可"))
        lines.append(tr("  電源に接続中 : %s")
                     % _POLICY_LABELS.get(plugged, tr("不明")))
        lines.append(tr("  バッテリー駆動: %s")
                     % _POLICY_LABELS.get(battery, tr("不明")))
        if plugged == 0 or battery == 0:
            lines.append("")
            lines.append(tr("「無効」になっている状態では、スリープ中に PC を"
                         "起こせません。"))
            lines.append(tr("コントロールパネル → 電源オプション → プラン設定の変更 →"))
            lines.append(tr("詳細な電源設定の変更 → スリープ → スリープ解除タイマーの許可"))
            lines.append(tr("を「有効」にしてください。"))

    lines.append("")
    ok, text = _run_powercfg(["/waketimers"])
    if ok:
        lines.append(text or tr("予約されているスリープ解除タイマーはありません。"))
    else:
        lines.append(tr("（予約の一覧は管理者権限が無いと表示できません）"))
    return "\n".join(lines)
