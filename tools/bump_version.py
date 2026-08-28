"""版番号をひとつ進める。

刻みは 0.0.001。パッチ部は 3 桁でゼロ詰めし、999 の次は繰り上げる。

    0.9.000 -> 0.9.001 -> ... -> 0.9.999 -> 0.10.000

使い方:

    python tools/bump_version.py            進める
    python tools/bump_version.py --show     いまの版を出す
    python tools/bump_version.py --set 1.0.000
    python tools/bump_version.py --dry-run  書き換えずに結果だけ出す

``koyomi/__init__.py`` と ``pyproject.toml`` の両方を書き換える。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INIT = ROOT / "koyomi" / "__init__.py"
PYPROJECT = ROOT / "pyproject.toml"

PATCH_DIGITS = 3
PATCH_WRAP = 10 ** PATCH_DIGITS

INIT_PATTERN = re.compile(r'(APP_VERSION\s*=\s*")([^"]+)(")')
PYPROJECT_PATTERN = re.compile(r'(?m)^(version\s*=\s*")([^"]+)(")')


def read_version() -> str:
    hit = INIT_PATTERN.search(INIT.read_text(encoding="utf-8"))
    if not hit:
        raise SystemExit("APP_VERSION が見つかりません: %s" % INIT)
    return hit.group(2)


def parse(version: str) -> tuple:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise SystemExit("版番号の形が違います: %r（例: 0.9.000）" % version)
    return tuple(int(p) for p in parts)


def render(major: int, minor: int, patch: int) -> str:
    return "%d.%d.%0*d" % (major, minor, PATCH_DIGITS, patch)


def stepped(version: str) -> str:
    major, minor, patch = parse(version)
    patch += 1
    if patch >= PATCH_WRAP:
        patch = 0
        minor += 1
    return render(major, minor, patch)


def write_version(version: str) -> None:
    text = INIT.read_text(encoding="utf-8")
    INIT.write_text(INIT_PATTERN.sub(r"\g<1>%s\g<3>" % version, text, count=1),
                    encoding="utf-8")

    text = PYPROJECT.read_text(encoding="utf-8")
    updated, count = PYPROJECT_PATTERN.subn(r"\g<1>%s\g<3>" % version, text,
                                            count=1)
    if count != 1:
        raise SystemExit("pyproject.toml の version 行が見つかりません")
    PYPROJECT.write_text(updated, encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="版番号をひとつ進める")
    parser.add_argument("--show", action="store_true", help="いまの版を出す")
    parser.add_argument("--set", dest="fixed", metavar="X.Y.ZZZ",
                        help="指定の版に置き換える")
    parser.add_argument("--dry-run", action="store_true",
                        help="書き換えずに結果だけ出す")
    args = parser.parse_args(argv)

    current = read_version()
    if args.show:
        print(current)
        return 0

    target = render(*parse(args.fixed)) if args.fixed else stepped(current)

    if args.dry_run:
        print("%s -> %s（書き換えていません）" % (current, target))
        return 0

    write_version(target)
    print("%s -> %s" % (current, target))
    print("  %s" % INIT.relative_to(ROOT))
    print("  %s" % PYPROJECT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
