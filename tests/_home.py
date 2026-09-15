"""テストのあいだ、本物の %APPDATA% を触らせない。

``python -m unittest discover -s tests`` で走らせると、tests/__init__.py は
読まれない。どの走らせ方でも効くよう、各テストの先頭で ``guard()`` を呼ぶ。
koyomi.vault は読み込んだ時点で保存先を決めるので、それより前に差し替える。
"""
import os
import sys
import tempfile

KEY = "KOYOMI_TEST_APPDATA"


def _inside(path: str, folder: str) -> bool:
    here = os.path.normcase(os.path.abspath(path))
    return here.startswith(os.path.normcase(os.path.abspath(folder)))


def guard() -> str:
    """テスト用の置き場を %APPDATA% に据える。何度呼んでも同じ場所になる。"""
    if not os.environ.get(KEY):
        os.environ[KEY] = tempfile.mkdtemp(prefix="koyomi-tests-")
    os.environ["APPDATA"] = os.environ[KEY]
    loaded = sys.modules.get("koyomi.vault")
    if loaded is not None and not _inside(loaded.STORE_PATH, os.environ[KEY]):
        # 先に読み込まれていたら、差し替えても手遅れ。書き込む前に止める
        raise RuntimeError("koyomi.vault が先に読み込まれ、本物の保存先を向いています: "
                           + loaded.STORE_PATH)
    return os.environ[KEY]


guard()
