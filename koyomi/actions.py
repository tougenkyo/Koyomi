"""アラームに紐づけて実行する外部アクション。

鳴り始めたとき、あるいは止めたときに、指定のアプリを起動したり
Web ページを開いたりする。

実行ファイル（.exe など）はそのまま起動し、画像や文書は OS の関連付け、
つまりエクスプローラーでダブルクリックしたときと同じ経路で開く。

安全のための取り決め:
  - シェルを介さずに起動する（`cmd /c` 相当の解釈をさせない）
  - URL は http / https だけを通す
  - バックアップから復元したアラームのアクションは、
    利用者が画面で承認するまで動かさない（vault 側で扱う）
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import webbrowser
from dataclasses import asdict, dataclass
from .i18n import tr

SAFE_SCHEMES = ("http://", "https://")

# それ自体が動くファイル。これ以外は OS の関連付けに任せる。
EXECUTABLE_SUFFIXES = (".exe", ".com", ".bat", ".cmd")


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


def split_arguments(text: str) -> list:
    """引数の並びを 1 つずつに分ける。

    ``shlex.split`` は逆斜線を「次の 1 文字を逃がす記号」として扱う。
    そのため Windows のパスをそのまま書くと

        D:\XAMPP\htdocs\a.php  ->  D:XAMPPhtdocsa.php

    のように区切りが消えてしまう。引用符の扱いはそのままに、
    Windows では逃がし記号だけを取り止める。
    """
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""              # # から後ろを捨てさせない
    if os.name == "nt":
        lexer.escape = ""              # 逆斜線はただの文字
    return list(lexer)


def looks_like_a_path(text: str) -> bool:
    """引数が、書き間違えると効かなくなる類の絶対パスに見えるか。"""
    if os.name == "nt":
        heads = (os.sep, os.altsep or os.sep)
        drive = len(text) > 2 and text[1] == ":" and text[2] in heads
        return drive or text.startswith(os.sep * 2)     # 共有フォルダ
    return text.startswith("/") and len(text) > 1


def is_program(path: str) -> bool:
    """それ自体が動くファイルか。画像や文書はここに入らない。"""
    return path.strip().lower().endswith(EXECUTABLE_SUFFIXES)


NO_WINDOW = 0x08000000 if os.name == "nt" else 0
WORK_LOG = "actions.log"
WORK_LOG_LIMIT = 200 * 1024


def work_log_path() -> str:
    """黙って動かしたものの、出しものを残す場所。"""
    from .vault import data_dir          # 取り込みが輪になるので、ここで呼ぶ
    return os.path.join(data_dir(), WORK_LOG)


def _open_work_log(command: list):
    """追記用に開いて、見出しを 1 行入れて返す。開けなければ None。"""
    import datetime as dt
    try:
        path = work_log_path()
        if os.path.exists(path) and os.path.getsize(path) > WORK_LOG_LIMIT:
            try:
                os.remove(path)             # まだ動いている最中なら消せない
            except OSError:
                pass
        book = open(path, "a", encoding="utf-8", errors="replace")
        book.write("%s----- %s  %s -----%s"
                   % (os.linesep,
                      dt.datetime.now().isoformat(timespec="seconds"),
                      subprocess.list2cmdline(command), os.linesep))
        book.flush()
        return book
    except OSError:
        return None                         # 残せなくても、動かすほうを優先


def _launch(program: str, args: list, quietly: bool = False) -> bool:
    """開く。実行ファイルとして起動したら True、関連付けに任せたら False。

    画像や文書を直接 exec しても動かないので、その場合は OS の
    関連付け（ダブルクリックしたときと同じ経路）に渡す。
    """
    folder = os.path.dirname(program) or None

    if is_program(program):
        if not quietly:
            subprocess.Popen([program] + args, shell=False, cwd=folder)
            return True
        # 画面を出さないアラームから動かすときは、黒い窓も出さない。
        # そのままでは出しものの行き先が無くなるので、控えへ回す。
        book = _open_work_log([program] + args)
        subprocess.Popen([program] + args, shell=False, cwd=folder,
                         stdout=book, stderr=subprocess.STDOUT,
                         creationflags=NO_WINDOW)
        if book is not None:
            book.close()      # 子が自分の分を持っているので、こちらは閉じてよい
        return True

    if hasattr(os, "startfile"):                      # Windows
        os.startfile(program, arguments=" ".join(args), cwd=folder)
        return False

    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, program] + args, shell=False, cwd=folder)
    return False


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
        args = split_arguments(plan.arguments)
    except ValueError:
        return tr("引数の引用符が閉じていません。")
    for arg in args:
        if looks_like_a_path(arg) and not os.path.exists(arg):
            return tr("引数に書かれたこのファイルが見つかりません: %s") % arg
    return ""


def run(plan: LaunchPlan, at_stop: bool, quietly: bool = False) -> str:
    """条件が合えば実行する。利用者に見せたい報告文を返す。

    ``quietly`` は画面を出さないアラームから呼ばれたとき。
    黒い窓を出さず、出しものを控えへ回す。
    """
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
                args = (split_arguments(plan.arguments)
                        if plan.arguments.strip() else [])
            except ValueError:
                args = []
            try:
                if _launch(program, args, quietly):
                    notes.append(tr("%s を起動しました。")
                                 % os.path.basename(program))
                else:
                    notes.append(tr("%s を開きました。")
                                 % os.path.basename(program))
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


def run_now(plan: LaunchPlan, quietly: bool = True) -> str:
    """時機を問わず実行する。画面を出さないアラーム用。

    画面が出ないと「鳴り始め」も「止めたとき」も無いので、
    どちらの指定でも、時刻が来た時点で同じように動かす。

    ``quietly`` を下ろすと黒い窓を隠さない。編集画面から試すときに使う。
    """
    return run(plan, at_stop=bool(plan.at_stop), quietly=quietly)
