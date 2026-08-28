"""対訳表の抜けと、書式指定子の食い違いを調べる。

``tr()`` に渡している文字列と、モジュール直下のラベル表を集めて、
lang_en.py と突き合わせる。CI から呼ぶことを想定している。

    python tools/check_translations.py
"""
from __future__ import annotations

import ast
import os
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# 設定ファイルを本物の場所に作らせない
os.environ.setdefault("APPDATA", tempfile.mkdtemp(prefix="koyomi-check-"))

PACKAGE = ROOT / "koyomi"
SPEC = re.compile(r"%[-#0-9. ]*[a-zA-Z%]")

# strftime の書式なので、指定子がそのまま対応しなくてよいもの
FREE_FORM = {"%Y年%m月%d日"}


def wrapped_strings() -> set:
    """``tr("...")`` に直接渡している文字列。"""
    found = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "tr" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                found.add(node.args[0].value)
    return found


def table_strings() -> set:
    """モジュール直下のラベル表。読み出す側で tr() を通している。"""
    from koyomi.models import (DEFAULT_DATE_LISTS, DEFAULT_GROUPS,
                               QUICK_ACTIONS, WEEKDAY_LABELS, _CYCLE_LABELS,
                               _GUARD_LABELS)
    from koyomi.tonesmith import TONE_CATALOG
    from koyomi.ui.guards import COLOR_NAMES, SHAPE_NAMES
    from koyomi.ui.palettes import ACCENTS, SURFACES
    from koyomi.ui.worldclock import FAVOURITES

    found = set(WEEKDAY_LABELS)
    for source in (QUICK_ACTIONS.values(), _CYCLE_LABELS.values(),
                   _GUARD_LABELS.values(), TONE_CATALOG.values(),
                   SHAPE_NAMES.values(), COLOR_NAMES.values(),
                   DEFAULT_GROUPS.values(), DEFAULT_DATE_LISTS.values(),
                   (name for name, _ in FAVOURITES),
                   (s["label"] for s in SURFACES.values()),
                   (a[0] for a in ACCENTS.values())):
        found.update(source)
    return found


def main() -> int:
    from koyomi.lang_en import WORDS

    vocabulary = wrapped_strings() | table_strings()
    missing = sorted(w for w in vocabulary if w not in WORDS)
    unused = sorted(k for k in WORDS if k not in vocabulary)
    mismatched = [
        (key, value) for key, value in WORDS.items()
        if key not in FREE_FORM
        and sorted(SPEC.findall(key)) != sorted(SPEC.findall(value))
    ]

    print("原文 %d 語 / 対訳 %d 語" % (len(vocabulary), len(WORDS)))
    for word in missing:
        print("  訳が無い : %r" % word)
    for word in unused:
        print("  使われない: %r" % word)
    for key, value in mismatched:
        print("  書式が違う: %r -> %r" % (key, value))

    if missing or unused or mismatched:
        print("NG")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
