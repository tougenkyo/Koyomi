"""テストをまとめて走らせ、落ちたものと時間のかかったものを知らせる。

    python tools/run_tests.py        python -m unittest discover -s tests と同じ
    python tools/run_tests.py -v     1 件ずつ名前を出す

終わりに、時間のかかったテストの上位を出す。

GitHub Actions の上では、落ちたテストと時間のかかったテストを
注記（annotation）としても書き出す。CI のログはサインインしないと
読めないが、注記は実行結果の画面に出るうえ、API からも読める。
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
SLOWEST = 10
FRAME = re.compile(r'File "([^"]+)", line (\d+)')


class TimedResult(unittest.TextTestResult):
    """1 件ごとにかかった時間を控える。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spent = []
        self._began = 0.0

    def startTest(self, test):
        self._began = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        self.spent.append((time.perf_counter() - self._began, test.id()))


def slowest_text(result: TimedResult) -> str:
    top = sorted(result.spent, reverse=True)[:SLOWEST]
    return "\n".join("%6.1f 秒  %s" % (secs, name) for secs, name in top)


def _escape(text: str, field: bool = False) -> str:
    """注記の書式で特別な意味を持つ文字を逃がす。"""
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if field:
        text = text.replace(":", "%3A").replace(",", "%2C")
    return text


def _spot(trace: str) -> tuple:
    """トレースのうち tests/ の下でいちばん奥の行を、(パス, 行番号) で返す。"""
    base = os.path.normcase(str(TESTS)) + os.sep
    found = ("", 0)
    for hit in FRAME.finditer(trace):
        path = os.path.normcase(os.path.abspath(hit.group(1)))
        if path.startswith(base):
            found = ("tests/" + path[len(base):].replace(os.sep, "/"), int(hit.group(2)))
    return found


def annotate(result: TimedResult, out) -> None:
    """落ちたテストと時間のかかったテストを、GitHub Actions の注記にする。"""
    for kind, pairs in (("FAIL", result.failures), ("ERROR", result.errors)):
        for test, trace in pairs:
            path, line = _spot(trace)
            where = "file=%s,line=%d," % (path, line) if path else ""
            title = _escape("%s: %s" % (kind, test.id()), field=True)
            out.write("::error %stitle=%s::%s\n" % (where, title, _escape(trace.strip())))
    out.write("::notice title=%s::%s\n" % (_escape("時間のかかったテスト", field=True),
                                           _escape(slowest_text(result))))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="テストをまとめて走らせる。")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="1 件ずつ名前を出す")
    opts = parser.parse_args(argv)

    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(TESTS), top_level_dir=str(TESTS))
    runner = unittest.TextTestRunner(verbosity=2 if opts.verbose else 1,
                                     resultclass=TimedResult)
    result = runner.run(suite)
    sys.stderr.write("\n時間のかかったテスト:\n%s\n" % slowest_text(result))
    if os.environ.get("GITHUB_ACTIONS") == "true":
        sys.stderr.flush()
        # 書き出せない文字があっても、注記そのものは必ず出す
        sys.stdout.reconfigure(errors="backslashreplace")
        annotate(result, sys.stdout)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
