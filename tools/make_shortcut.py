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
import base64
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from koyomi import APP_TITLE                      # noqa: E402
from koyomi.autostart import TRAY_FLAG, _launcher  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "run.pyw")
LINK_NAME = APP_TITLE + ".lnk"


def desktop() -> str:
    return os.path.join(os.path.expanduser("~"), "Desktop")


def start_menu() -> str:
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs")


def icon_file() -> str:
    """ショートカットに付ける絵。無ければその場で作る。"""
    from koyomi.tonesmith import ensure_ico
    return ensure_ico()


def _quoted(text: str) -> str:
    """PowerShell の単引用符の中に置ける形にする。"""
    return "'" + text.replace("'", "''") + "'"


def build(folder: str, minimized: bool = False) -> str:
    """.lnk を 1 つ作って、その場所を返す。"""
    os.makedirs(folder, exist_ok=True)
    link = os.path.normpath(os.path.join(folder, LINK_NAME))
    args = '"%s"' % ENTRY
    if minimized:
        args += " " + TRAY_FLAG

    # 追加の部品を入れずに済むよう、Windows 自身の仕組みに作らせる。
    # 日本語が化けないよう、命令ごと UTF-16 に直して渡す。
    lines = [
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut(%s)" % _quoted(link),
        "$s.TargetPath = %s" % _quoted(_launcher()),
        "$s.Arguments = %s" % _quoted(args),
        "$s.WorkingDirectory = %s" % _quoted(ROOT),
        "$s.IconLocation = %s" % _quoted(icon_file()),
        "$s.Description = %s" % _quoted("%s（コンソールを出さずに開く）" % APP_TITLE),
        "$s.Save()",
    ]
    packed = base64.b64encode("\n".join(lines).encode("utf-16-le")).decode("ascii")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                    "-EncodedCommand", packed],
                   check=True, capture_output=True,
                   creationflags=0x08000000 if os.name == "nt" else 0)
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
