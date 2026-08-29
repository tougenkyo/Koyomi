"""Windows を起動したときに、このアプリも一緒に始める仕掛け。

登録先は現在のユーザーの Run キー。管理者権限は要らない。

  HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run

設定ファイルではなく **レジストリを唯一の正** として扱う。
タスクマネージャーの「スタートアップ アプリ」から無効にされることがあり、
そのときアプリ側の設定だけを見ていると食い違うため。
"""
from __future__ import annotations

import os
import subprocess
import sys

from . import APP_NAME
from .i18n import tr

IS_WINDOWS = sys.platform.startswith("win")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY = (r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                r"\StartupApproved\Run")
VALUE_NAME = APP_NAME
TRAY_FLAG = "--minimized"

if IS_WINDOWS:
    import winreg
else:                                   # pragma: no cover - Windows 以外
    winreg = None


# --------------------------------------------------------------------------
# いま登録するとしたら、というコマンド
# --------------------------------------------------------------------------
def _launcher() -> str:
    """窓を出さずに Python を動かす実行ファイル。"""
    if getattr(sys, "frozen", False):
        return sys.executable
    folder = os.path.dirname(sys.executable)
    quiet = os.path.join(folder, "pythonw.exe")
    return quiet if os.path.exists(quiet) else sys.executable


def entry_script() -> str:
    """run.py の場所。パッケージの 1 つ上にある。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "run.py")


def launch_command(minimized: bool = True) -> str:
    """レジストリへ書き込む一行。空白を含むので必ず引用符で囲む。"""
    parts = ['"%s"' % _launcher()]
    if not getattr(sys, "frozen", False):
        parts.append('"%s"' % entry_script())
    if minimized:
        parts.append(TRAY_FLAG)
    return " ".join(parts)


def wants_tray(argv=None) -> bool:
    """起動時にトレイへ畳んでおくよう指示されているか。"""
    argv = sys.argv if argv is None else argv
    return TRAY_FLAG in argv or "-m" in argv[1:2]


# --------------------------------------------------------------------------
# レジストリの読み書き
# --------------------------------------------------------------------------
def current_command():
    """登録されている一行。未登録なら None。"""
    if not IS_WINDOWS:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return value
    except OSError:
        return None


def _blocked_by_task_manager() -> bool:
    """タスクマネージャー側で無効にされているか。"""
    if not IS_WINDOWS:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY) as key:
            blob, _ = winreg.QueryValueEx(key, VALUE_NAME)
            # 先頭バイトが 2 か 6 なら有効、3 なら無効
            return bool(blob) and blob[0] not in (2, 6)
    except OSError:
        return False


def is_registered() -> bool:
    return current_command() is not None


def points_here() -> bool:
    """登録が、いま動いているこの場所を指しているか。"""
    stored = current_command()
    if not stored:
        return False
    return entry_script().lower() in stored.lower()


def state() -> str:
    """人に見せる一行。"""
    if not IS_WINDOWS:
        return tr("この OS では自動起動に対応していません。")
    stored = current_command()
    if stored is None:
        return tr("登録されていません。")
    if _blocked_by_task_manager():
        return tr("登録はありますが、タスクマネージャーで無効にされています。")
    if not points_here():
        return tr("別の場所が登録されています。登録し直してください。")
    return tr("登録済み。次回の Windows 起動から始まります。")


def healthy() -> bool:
    """登録が今の場所を指していて、じゃまもされていない状態か。"""
    return (IS_WINDOWS and is_registered() and points_here()
            and not _blocked_by_task_manager())


def enable(minimized: bool = True) -> str:
    """登録する。うまくいけば空文字、だめなら理由を返す。"""
    if not IS_WINDOWS:
        return tr("この OS では自動起動に対応していません。")
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ,
                              launch_command(minimized))
    except OSError as err:
        return tr("登録できませんでした: %s") % err
    _unblock()
    return ""


def _unblock() -> None:
    """タスクマネージャー側の無効指定を解く。無ければ何もしない。"""
    if not IS_WINDOWS:
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY, 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
            blob, kind = winreg.QueryValueEx(key, VALUE_NAME)
            if blob and blob[0] not in (2, 6):
                winreg.SetValueEx(key, VALUE_NAME, 0, kind,
                                  bytes([2]) + bytes(blob[1:]))
    except OSError:
        pass


def disable() -> str:
    """登録を消す。もともと無ければ黙って終わる。"""
    if not IS_WINDOWS:
        return tr("この OS では自動起動に対応していません。")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        return ""
    except OSError as err:
        return tr("解除できませんでした: %s") % err
    return ""


def open_startup_settings() -> bool:
    """Windows の「スタートアップ アプリ」設定を開く。"""
    if not IS_WINDOWS:
        return False
    try:
        subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:startupapps"],
                         shell=False, creationflags=0x08000000)
        return True
    except OSError:
        return False
