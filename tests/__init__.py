"""テスト一式。

    python -m unittest discover -s tests

画面を組み立てるテストは、表示のいらない Qt の環境で動かす。

    set QT_QPA_PLATFORM=offscreen
"""
import os
import sys
import tempfile

# 本物の %APPDATA% を汚さないよう、読み込む前に差し替える
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="koyomi-tests-")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
