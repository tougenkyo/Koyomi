"""新しい版が出ていないかを調べ、その場で取り込む。

調べ方は 2 段構え。
  1. GitHub の Releases（`releases/latest` の tag_name）
  2. 無ければ、既定ブランチの ``koyomi/__init__.py`` から APP_VERSION を読む

取り込み方は ``git pull --ff-only``。
このアプリは git の作業コピーとして配られる前提で、
早送りできるときだけ更新する。手元の変更を巻き込まないための制限。
zip で落としただけの場合は git が使えないので、配布ページを開く案内に留める。

開き直すときは、新しい版が立ち上がったと知らせてくるのを待ってから古い版を
終わらせ、新しい版は古い版が終わるのを待ってから本物になる（ui/solo.py）。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

from . import APP_REPO, APP_VERSION
from .i18n import tr

TIMEOUT = 8
AGENT = "Koyomi/%s" % APP_VERSION
RELEASE_API = "https://api.github.com/repos/%s/releases/latest"
RAW_INIT = "https://raw.githubusercontent.com/%s/%s/koyomi/__init__.py"
BRANCH = "main"
PAGE = "https://github.com/%s"

VERSION_PATTERN = re.compile(r'APP_VERSION\s*=\s*"([^"]+)"')


# --------------------------------------------------------------------------
# 版の比べ方
# --------------------------------------------------------------------------
def parse(version: str) -> tuple:
    """"0.9.003" や "v1.0.0" を並べ替えできる形に。"""
    cleaned = (version or "").strip().lstrip("vV")
    parts = []
    for chunk in cleaned.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(candidate: str, than: str = APP_VERSION) -> bool:
    return parse(candidate) > parse(than)


# --------------------------------------------------------------------------
# 調べる
# --------------------------------------------------------------------------
def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:
        return answer.read().decode("utf-8", "replace")


def look_up(repo: str = APP_REPO) -> dict:
    """向こうの最新版を調べる。

    返す辞書:
      ok       … 調べられたか
      version  … 見つかった版（調べられなかったときは空）
      newer    … いま動いている版より新しいか
      source   … "releases" か "source"
      url      … 人が開くページ
      message  … うまくいかなかった理由
    """
    result = {"ok": False, "version": "", "newer": False,
              "source": "", "url": PAGE % repo, "message": ""}
    try:
        raw = _fetch(RELEASE_API % repo)
        tag = (json.loads(raw) or {}).get("tag_name") or ""
        if tag:
            result.update(ok=True, version=tag.lstrip("vV"),
                          source="releases",
                          url="%s/releases/latest" % (PAGE % repo))
            result["newer"] = is_newer(result["version"])
            return result
    except urllib.error.HTTPError as err:
        if err.code not in (404, 403):
            result["message"] = tr("調べられませんでした: %s") % err
            return result
    except (urllib.error.URLError, ValueError, OSError) as err:
        result["message"] = tr("調べられませんでした: %s") % err
        return result

    # Releases が無いので、ソースの版番号を直接見る
    try:
        text = _fetch(RAW_INIT % (repo, BRANCH))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as err:
        result["message"] = tr("調べられませんでした: %s") % err
        return result

    hit = VERSION_PATTERN.search(text)
    if not hit:
        result["message"] = tr("向こうの版番号を読み取れませんでした。")
        return result
    result.update(ok=True, version=hit.group(1), source="source")
    result["newer"] = is_newer(result["version"])
    return result


# --------------------------------------------------------------------------
# 取り込む
# --------------------------------------------------------------------------
def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*args) -> tuple:
    """git を叩いて (成功したか, 出力) を返す。"""
    try:
        done = subprocess.run(("git",) + args, cwd=project_root(),
                              capture_output=True, timeout=120,
                              creationflags=0x08000000 if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError) as err:
        return False, str(err)
    blob = done.stdout + done.stderr
    for encoding in ("utf-8", "cp932"):
        try:
            text = blob.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = repr(blob)
    return done.returncode == 0, text.strip()


def is_git_copy() -> bool:
    """git で取り込める形で置かれているか。"""
    ok, text = _git("rev-parse", "--is-inside-work-tree")
    return ok and text.strip() == "true"


def has_local_changes() -> bool:
    ok, text = _git("status", "--porcelain")
    return ok and bool(text.strip())


def can_pull() -> str:
    """取り込めない理由。取り込めるなら空文字。"""
    if not is_git_copy():
        return tr("この場所は git の作業コピーではないため、"
                  "自動では取り込めません。")
    ok, _ = _git("rev-parse", "--abbrev-ref", "@{upstream}")
    if not ok:
        return tr("取り込み元が設定されていません。")
    if has_local_changes():
        return tr("手元に未保存の変更があります。"
                  "先にコミットするか元に戻してください。")
    return ""


def pull() -> tuple:
    """早送りできる場合だけ取り込む。(成功したか, 出力) を返す。"""
    blocked = can_pull()
    if blocked:
        return False, blocked
    return _git("pull", "--ff-only")


# --------------------------------------------------------------------------
# 開き直す
# --------------------------------------------------------------------------
# 新しい版へ「このプロセスが終わるのを待ってから始めて」と伝える印
AFTER_FLAG = "--after-update="
_SYNCHRONIZE = 0x00100000


def relaunch(after: int | None = None):
    """新しい版を起動する。起動できたらそのプロセスを、できなければ None を返す。

    ``after`` にいまの pid を渡すと、新しい版はこのプロセスが終わるのを待ってから
    二重起動の見張りを通る。待たずに通ろうとすると、まだ動いているこちらを見て
    「すでに動いている」と引き下がり、どちらも残らないことがあった。
    """
    from .autostart import _launcher, entry_script
    command = [_launcher()]
    if not getattr(sys, "frozen", False):
        command.append(entry_script())
    if after:
        command.append("%s%d" % (AFTER_FLAG, after))
    try:
        return subprocess.Popen(command, cwd=project_root(), shell=False)
    except OSError:
        return None


def predecessor(argv=None):
    """更新で開き直されたときの、前の版の pid。そうでなければ None。"""
    for arg in (sys.argv if argv is None else argv)[1:]:
        if arg.startswith(AFTER_FLAG) and arg[len(AFTER_FLAG):].isdigit():
            return int(arg[len(AFTER_FLAG):])
    return None


def wait_for_exit(pid: int, seconds: float) -> bool:
    """``pid`` のプロセスが終わるのを待つ。終わった（もう居ない）なら True。"""
    if not sys.platform.startswith("win"):     # pragma: no cover - Windows 以外
        deadline = time.monotonic() + seconds
        while True:
            try:
                os.kill(pid, 0)                # Windows 以外では、居るか確かめるだけ
            except OSError:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.2)
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel32.OpenProcess(_SYNCHRONIZE, False, pid)
    if not handle:
        return True                            # もう居ない
    try:
        return kernel32.WaitForSingleObject(handle, int(seconds * 1000)) == 0
    finally:
        kernel32.CloseHandle(handle)
