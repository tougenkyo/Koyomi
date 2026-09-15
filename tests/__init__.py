"""テスト一式。

    python -m unittest discover -s tests

画面を組み立てるテストは、表示のいらない Qt の環境で動かす。

    set QT_QPA_PLATFORM=offscreen

本物の %APPDATA% を汚さないよう、各テストは先頭で ``_home.guard()`` を呼ぶ。
この __init__.py は ``discover -s tests`` では読まれないので、ここだけに頼らない。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)       # パッケージとして走らせたときも _home を見つけられるように

import _home  # noqa: E402

_home.guard()
