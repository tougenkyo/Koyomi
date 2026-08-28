"""画面のことばを切り替える。

日本語を原文として書き、``tr()`` を通した文字列だけが別の言語に差し替わる。
対訳表は lang_en.py のような言語ごとのファイルに置く。
訳が無い語はそのまま日本語で出るので、表が虫食いでも画面は壊れない。
"""
from __future__ import annotations

LANGUAGES = {
    "ja": "日本語",
    "en": "English",
}

_current = "ja"
_table: dict = {}


def _load(code: str) -> dict:
    if code == "en":
        try:
            from .lang_en import WORDS
            return WORDS
        except ImportError:
            return {}
    return {}


def set_language(code: str) -> str:
    """使うことばを決める。知らない符号は日本語に落とす。"""
    global _current, _table
    if code not in LANGUAGES:
        code = "ja"
    _current = code
    _table = _load(code)
    return _current


def current() -> str:
    return _current


def tr(text: str) -> str:
    """原文（日本語）を、いまのことばに置き換える。"""
    if not _table:
        return text
    return _table.get(text, text)
