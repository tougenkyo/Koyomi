"""起動と終了の控え。

いつ始まり、どの操作で終わったかを ``history.log`` へ 1 行ずつ残す。
あとから「自分で終了したのか、落ちたのか」を見分けるためのもの。

  - 動いている間は ``running.json`` に「いつまで動いていたか」を 1 分ごとに
    書き直し、ふつうに終わるときに消す。次の起動でこれが残っていれば、前回は
    終了の操作を通らずに消えた（強制終了・異常終了・電源断）ということになる。
  - Python ごと落ちたときの様子は、faulthandler が ``crash.log`` へ書く。
    次の起動で ``error.log`` へ移し、「error.log がある＝つまずいた」の目印に揃える。

どれも書けなくても、アプリの動作は止めない。
"""
from __future__ import annotations

import datetime as dt
import faulthandler
import json
import os

HISTORY = "history.log"      # 起動と終了を 1 行ずつ
RUNNING = "running.json"     # 動いている間だけ置く印
CRASH = "crash.log"          # faulthandler の書き込み先。動いている間は開いたまま
ERROR = "error.log"          # run.pyw の控えと同じ名前
HISTORY_LIMIT = 100 * 1024   # これを超えたら古い行を捨てる
HISTORY_KEEP = 1000          # そのとき残す行数

# 始まり方と終わり方の言い方。控えに残すだけなので訳さない
BY_HAND = "手で起動"
BY_AUTOSTART = "トレイに畳んで起動（Windows の自動起動など）"
AFTER_UPDATE = "更新のあと開き直し（前の版 pid %d）"
BY_TRAY = "トレイのメニューから終了"
BY_MENU = "メニューボタンから終了"
BY_UPDATE = "更新して開き直すため終了"
BY_WINDOWS = "Windows の終了（シャットダウン・再起動・サインアウト）"
BY_CLOSE = "窓を閉じたため終了（トレイが使えない）"
BY_TROUBLE = "起動の途中でつまずいたため終了（error.log を参照）"


def _moment(text):
    try:
        return dt.datetime.fromisoformat(text) if text else None
    except (TypeError, ValueError):
        return None


class Logbook:
    """1 回の起動ぶんの控え。"""

    def __init__(self, folder: str | None = None):
        if folder is None:
            from .vault import data_dir          # 読み込むと保存先が決まるので、使うときに呼ぶ
            folder = data_dir()
        self.folder = folder
        self.pid = os.getpid()
        self.version = ""
        self.started = None
        self.previous = None     # 前回が終了の操作を通らずに消えていたら、その様子
        self._crash = None       # faulthandler が書き込むファイル
        self._beat_at = None     # running.json を最後に書いた分
        self._closed = False

    def path(self, name: str) -> str:
        return os.path.join(self.folder, name)

    # ---- 1 行の控え -------------------------------------------------------
    def note(self, what: str, detail: str = "", now=None) -> None:
        """history.log へ 1 行足す。"""
        now = now or dt.datetime.now()
        parts = [now.strftime("%Y-%m-%d %H:%M:%S"), what, "pid %d" % self.pid]
        if detail:
            parts.append(detail)
        try:
            os.makedirs(self.folder, exist_ok=True)
            self._trim()
            with open(self.path(HISTORY), "a", encoding="utf-8") as book:
                book.write("  ".join(parts) + "\n")
        except OSError:
            pass

    def _trim(self) -> None:
        """大きくなりすぎたら、新しいほうの行だけ残す。"""
        path = self.path(HISTORY)
        if not os.path.exists(path) or os.path.getsize(path) <= HISTORY_LIMIT:
            return
        with open(path, "r", encoding="utf-8", errors="replace") as book:
            keep = book.readlines()[-HISTORY_KEEP:]
        with open(path, "w", encoding="utf-8") as book:
            book.writelines(keep)

    # ---- 始まりと終わり ---------------------------------------------------
    def open(self, how: str, version: str, now=None) -> None:
        """起動を記録する。前回の終わり方も、ここで確かめる。

        二重起動の見張りを通ってから呼ぶ。先に動いているものがいるうちに呼ぶと、
        その印を「前回の消え残り」と取り違える。
        """
        now = now or dt.datetime.now()
        self.version = version
        self.started = now
        self.previous = self._look_back(now)
        if self.previous is not None:
            self.note("前回は終了の操作を通らずに消えた", self._describe(self.previous), now)
        self.note("起動", "版 %s  %s" % (version, how), now)
        self.beat(now, force=True)
        self._watch_crashes()

    def close(self, how: str, now=None) -> None:
        """ふつうに終わるときの記録。印を片付ける。"""
        if self._closed:
            return
        self._closed = True
        now = now or dt.datetime.now()
        self.note("終了", how or "（理由の記録なし）", now)
        if self._crash is not None:
            faulthandler.disable()
            try:
                self._crash.close()
            except OSError:
                pass
            self._crash = None
            # 落ちずに済んでも、深刻な例外が書かれていたら error.log へ残す
            self._adopt_crash_log(now, "動いている間に記録された深刻な例外（アプリは動き続けた）")
        try:
            os.remove(self.path(RUNNING))
        except OSError:
            pass

    def beat(self, now=None, force: bool = False) -> None:
        """動いている印を書き直す。消えた時刻の目安なので、1 分に 1 回で足りる。"""
        now = now or dt.datetime.now()
        minute = now.replace(second=0, microsecond=0)
        if minute == self._beat_at and not force:
            return
        self._beat_at = minute
        mark = {"pid": self.pid, "version": self.version,
                "started": (self.started or now).isoformat(timespec="seconds"),
                "alive": now.isoformat(timespec="seconds")}
        path = self.path(RUNNING)
        try:
            with open(path + ".part", "w", encoding="utf-8") as fh:
                json.dump(mark, fh)
            os.replace(path + ".part", path)
        except OSError:
            pass

    def _watch_crashes(self) -> None:
        """Python ごと落ちたとき、その場の様子を crash.log へ書かせる。"""
        try:
            self._crash = open(self.path(CRASH), "w", encoding="utf-8")
            faulthandler.enable(file=self._crash, all_threads=True)
        except (OSError, RuntimeError, ValueError):
            if self._crash is not None:
                self._crash.close()
            self._crash = None

    # ---- 前回の様子 -------------------------------------------------------
    def _look_back(self, now):
        """前回が終了の操作を通らずに消えていたら、その様子を返す。"""
        crashed = self._adopt_crash_log(now, "前回の異常終了")
        mark = None
        try:
            with open(self.path(RUNNING), "r", encoding="utf-8") as fh:
                mark = json.load(fh)
        except (OSError, ValueError):
            pass
        if mark is None and not crashed:
            return None
        try:
            os.remove(self.path(RUNNING))
        except OSError:
            pass
        mark = mark if isinstance(mark, dict) else {}
        return {"pid": mark.get("pid"), "version": str(mark.get("version") or ""),
                "started": _moment(mark.get("started")),
                "alive": _moment(mark.get("alive")), "crashed": crashed}

    def _adopt_crash_log(self, now, title: str) -> bool:
        """crash.log に中身があれば error.log へ移す。移したら True。"""
        path = self.path(CRASH)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            os.remove(path)
        except OSError:
            return False
        if not text.strip():
            return False
        try:
            with open(self.path(ERROR), "a", encoding="utf-8") as book:
                book.write("\n----- %s  %s -----\n"
                           % (now.isoformat(timespec="seconds"), title))
                book.write(text if text.endswith("\n") else text + "\n")
        except OSError:
            pass
        return True

    @staticmethod
    def _describe(previous: dict) -> str:
        head = "前回 pid %s" % previous["pid"] if previous.get("pid") else "前回"
        about = []
        if previous.get("started"):
            about.append("%s 起動" % previous["started"].strftime("%Y-%m-%d %H:%M:%S"))
        if previous.get("version"):
            about.append("版 %s" % previous["version"])
        if about:
            head += "（%s）" % "、".join(about)
        parts = [head]
        if previous.get("alive"):
            parts.append("最後に動いていたのは %s ごろ"
                         % previous["alive"].strftime("%Y-%m-%d %H:%M"))
        parts.append("異常終了の記録: %s"
                     % ("あり（error.log）" if previous.get("crashed") else "なし"))
        return "  ".join(parts)
