"""こよみアラーム のショートカットを作る。

拡張子 .pyw の関連付けは、Microsoft Store の Python など
別の Python に取られていることがある。そのままダブルクリックすると
必要な部品の入っていない Python で開こうとして失敗する。

ショートカットなら Python を名指しできるので、その心配が無い。
いま動かしている Python の pythonw.exe をそのまま埋め込む。

使い方:

    python tools/make_shortcut.py                デスクトップに作る
    python tools/make_shortcut.py --start-menu   スタートメニューにも作る
    python tools/make_shortcut.py --minimized    トレイに畳んだ状態で始める
    python tools/make_shortcut.py --where        作られる場所だけ出す
"""
from __future__ import annotations

import argparse
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from koyomi import APP_TITLE                      # noqa: E402
from koyomi.autostart import TRAY_FLAG, _launcher  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "run.pyw")
LINK_NAME = APP_TITLE + ".lnk"

# ショートカットを扱う Windows の部品（COM）の名前
_SHELL_LINK = "{00021401-0000-0000-C000-000000000046}"
_I_SHELL_LINK_W = "{000214F9-0000-0000-C000-000000000046}"
_I_PERSIST_FILE = "{0000010B-0000-0000-C000-000000000046}"
_IN_PROCESS = 1                     # CLSCTX_INPROC_SERVER
_CHANGED_MODE = -2147417850         # RPC_E_CHANGED_MODE: COM が別の方式で始まっていた


class _Guid(ctypes.Structure):
    _fields_ = [("data1", ctypes.c_uint32), ("data2", ctypes.c_uint16),
                ("data3", ctypes.c_uint16), ("data4", ctypes.c_ubyte * 8)]


def desktop() -> str:
    return os.path.join(os.path.expanduser("~"), "Desktop")


def start_menu() -> str:
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs")


def icon_file() -> str:
    """ショートカットに付ける絵。無ければその場で作る。"""
    from koyomi.tonesmith import ensure_ico
    return ensure_ico()


def _guid(text: str) -> _Guid:
    found = _Guid()
    ctypes.oledll.ole32.CLSIDFromString(text, ctypes.byref(found))
    return found


def _call(obj, index: int, argtypes=(), restype=None):
    """COM の口 ``obj`` が持つ手続きのうち、``index`` 番目を呼べる形で返す。"""
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(restype or ctypes.HRESULT, ctypes.c_void_p, *argtypes)
    return lambda *args: proto(table[index])(obj, *args)


def write_link(path: str, target: str, arguments: str, folder: str,
               icon: str, note: str) -> None:
    """.lnk を書く。

    WScript.Shell を通すと、文字がいったん OS の文字コードに直される。
    英語版 Windows では日本語の名前が「?」に化けて保存できないので、
    ショートカットの部品（IShellLinkW）に UTF-16 のまま渡す。
    """
    ole32 = ctypes.oledll.ole32
    try:
        ole32.CoInitialize(None)
        started = True
    except OSError as err:
        if err.winerror != _CHANGED_MODE:
            raise
        started = False                  # 始まっていた方式のまま使える
    link, disk = ctypes.c_void_p(), ctypes.c_void_p()
    text = ctypes.c_wchar_p
    try:
        ole32.CoCreateInstance(ctypes.byref(_guid(_SHELL_LINK)), None, _IN_PROCESS,
                               ctypes.byref(_guid(_I_SHELL_LINK_W)), ctypes.byref(link))
        # 数字は、それぞれの口で手続きが並んでいる順番
        _call(link, 20, (text,))(target)                   # SetPath
        _call(link, 11, (text,))(arguments)                # SetArguments
        _call(link, 9, (text,))(folder)                    # SetWorkingDirectory
        _call(link, 17, (text, ctypes.c_int))(icon, 0)     # SetIconLocation
        _call(link, 7, (text,))(note)                      # SetDescription
        _call(link, 0, (ctypes.POINTER(_Guid), ctypes.POINTER(ctypes.c_void_p)))(
            ctypes.byref(_guid(_I_PERSIST_FILE)), ctypes.byref(disk))  # QueryInterface
        _call(disk, 6, (text, ctypes.c_int))(path, 1)      # IPersistFile の Save
    finally:
        for obj in (disk, link):
            if obj.value:
                _call(obj, 2, restype=ctypes.c_ulong)()    # Release
        if started:
            ole32.CoUninitialize()


def build(folder: str, minimized: bool = False) -> str:
    """.lnk を 1 つ作って、その場所を返す。"""
    os.makedirs(folder, exist_ok=True)
    link = os.path.normpath(os.path.join(folder, LINK_NAME))
    args = '"%s"' % ENTRY
    if minimized:
        args += " " + TRAY_FLAG
    # 追加の部品を入れずに済むよう、Windows 自身の仕組みに作らせる
    write_link(link, _launcher(), args, ROOT, icon_file(),
               "%s（コンソールを出さずに開く）" % APP_TITLE)
    return link


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-menu", action="store_true",
                        help="スタートメニューにも置く")
    parser.add_argument("--minimized", action="store_true",
                        help="トレイに畳んだ状態で始める")
    parser.add_argument("--where", action="store_true",
                        help="作らずに、置き場所だけ出す")
    opts = parser.parse_args(argv)

    if not sys.platform.startswith("win"):
        print("この道具は Windows 専用です。")
        return 1
    if not os.path.exists(ENTRY):
        print("起動口が見つかりません: %s" % ENTRY)
        return 1

    places = [desktop()]
    if opts.start_menu:
        places.append(start_menu())

    for place in places:
        target = os.path.join(place, LINK_NAME)
        if opts.where:
            print(target)
            continue
        print("作りました: %s" % build(place, opts.minimized))
    return 0


if __name__ == "__main__":
    sys.exit(main())
