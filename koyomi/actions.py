"""アラームに紐づけて実行する外部アクション。

鳴り始めたとき、あるいは止めたときに、指定のアプリを起動したり
Web ページを開いたりする。

安全のための取り決め:
  - シェルを介さずに直接起動する（`cmd /c` 相当の解釈をさせない）
  - URL は http / https だけを通す
  - バックアップから復元したアラームのアクションは、
    利用者が画面で承認するまで動かさない（vault 側で扱う）
"""
from __future__ import annotations

import os
import shlex
import subprocess
import webbrowser
from dataclasses import asdict, dataclass
from .i18n import tr

SAFE_SCHEMES = ("http://", "https://")


@dataclass
class LaunchPlan:
    """アラームに付ける「ついでにやること」。"""

    enabled: bool = False
    program: str = ""        # 実行ファイルや文書のパス
    arguments: str = ""      # 引数（空白区切り。引用符も使える）
    url: str = ""            # 開く Web ページ
    at_stop: bool = False    # False=鳴り始めたとき / True=止めたとき
    approved: bool = True    # 復元直後など、未承認のうちは実行しない

    def has_work(self) -> bool:
        return bool(self.enabled and (self.program.strip() or self.url.strip()))

    def summary(self) -> str:
        bits = []
        if self.program.strip():
            bits.append(os.path.basename(self.program.strip()))
        if self.url.strip():
            bits.append(self.url.strip())
        if not bits:
            return ""
        timing = tr("停止時") if self.at_stop else tr("鳴動時")
        return "%s: %s" % (timing, " / ".join(bits))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "LaunchPlan":
        d = dict(d or {})
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def check(plan: LaunchPlan) -> str:
    """設定の粗を人に伝わる言葉で返す。問題なければ空文字。"""
    if not plan.has_work():
        return ""
    program = plan.program.strip()
    if program and not os.path.exists(program):
        return tr("指定されたファイルが見つかりません: %s") % program
    url = plan.url.strip()
    if url and not url.lower().startswith(SAFE_SCHEMES):
        return tr("URL は http:// または https:// で始めてください。")
    try:
        shlex.split(plan.arguments)
    except ValueError:
        return tr("引数の引用符が閉じていません。")
    return ""


def run(plan: LaunchPlan, at_stop: bool) -> str:
    """条件が合えば実行する。利用者に見せたい報告文を返す。"""
    if not plan.has_work() or bool(plan.at_stop) != bool(at_stop):
        return ""
    if not plan.approved:
        return tr("このアラームの連動動作は未承認のため実行しませんでした。")

    notes = []
    program = plan.program.strip()
    if program:
        if not os.path.exists(program):
            notes.append(tr("起動できませんでした（ファイルが見つかりません）。"))
        else:
            try:
                args = shlex.split(plan.arguments) if plan.arguments.strip() else []
            except ValueError:
                args = []
            try:
                subprocess.Popen([program] + args, shell=False,
                                 cwd=os.path.dirname(program) or None)
                notes.append(tr("%s を起動しました。") % os.path.basename(program))
            except OSError as err:
                notes.append(tr("起動できませんでした: %s") % err)

    url = plan.url.strip()
    if url:
        if not url.lower().startswith(SAFE_SCHEMES):
            notes.append(tr("この URL は開けません（http/https のみ）。"))
        else:
            try:
                webbrowser.open(url)
                notes.append(tr("ページを開きました。"))
            except OSError as err:
                notes.append(tr("ページを開けませんでした: %s") % err)

    return " ".join(notes)
