"""設定とアラームの保存先。

保存先は Windows なら ``%APPDATA%\\Koyomi``、それ以外は ``~/.koyomi``。
中身は 1 本の JSON にまとめてあり、そのままバックアップファイルとして
書き出し／読み戻しができる。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile

from . import APP_NAME, APP_VERSION
from .almanac import Almanac
from .models import DEFAULT_GROUPS, Prefs, WakeItem
from .tasks import TodoItem
from .i18n import tr

STORE_FORMAT = 1

# アプリ名を変える前に使っていた保存先。初回だけ中身を引き継ぐ。
LEGACY_APP_NAMES = ("SmileAlarm",)

_legacy_checked = False


def _adopt_legacy(root: str, current: str) -> None:
    """旧名フォルダに残っているデータを、新しい保存先へ写す。

    移動ではなく複製にしておき、うまくいかなかったときのために
    元のフォルダはそのまま残す。
    """
    if os.path.exists(os.path.join(current, "store.json")):
        return
    candidates = []
    for name in LEGACY_APP_NAMES:
        candidates.append(os.path.join(root, name))            # Windows 側の綴り
        candidates.append(os.path.join(root, "." + name.lower()))  # それ以外の綴り
    for old in candidates:
        if os.path.normcase(old) == os.path.normcase(current):
            continue
        source = os.path.join(old, "store.json")
        if not os.path.isfile(source):
            continue
        try:
            shutil.copy2(source, os.path.join(current, "store.json"))
            old_backups = os.path.join(old, "backup")
            if os.path.isdir(old_backups):
                shutil.copytree(old_backups, os.path.join(current, "backup"),
                                dirs_exist_ok=True)
        except OSError:
            continue
        return


def data_dir() -> str:
    global _legacy_checked
    base = os.environ.get("APPDATA")
    if base:
        root = base
        path = os.path.join(base, APP_NAME)
    else:
        root = os.path.expanduser("~")
        path = os.path.join(root, "." + APP_NAME.lower())
    os.makedirs(path, exist_ok=True)
    if not _legacy_checked:
        _legacy_checked = True
        _adopt_legacy(root, path)
    return path


def tones_dir() -> str:
    path = os.path.join(data_dir(), "tones")
    os.makedirs(path, exist_ok=True)
    return path


def glyphs_dir() -> str:
    path = os.path.join(data_dir(), "glyphs")
    os.makedirs(path, exist_ok=True)
    return path


def backups_dir() -> str:
    path = os.path.join(data_dir(), "backup")
    os.makedirs(path, exist_ok=True)
    return path


STORE_PATH = os.path.join(data_dir(), "store.json")


class Vault:
    """アプリの状態をまとめて抱える器。"""

    def __init__(self):
        self.items: list = []
        self.prefs = Prefs()
        self.groups = dict(DEFAULT_GROUPS)
        self.almanac = Almanac()
        self.timer_presets: list = [180, 300, 600]
        self.timers: list = []
        self.todos: list = []
        self.world_zones: list = ["Asia/Tokyo", "America/New_York", "Europe/London"]
        self.last_seen: str = ""   # 前回アプリが動いていた時刻（取りこぼし検出用）
        # 復元直後など、連動動作の承認待ちが残っているか
        self.pending_actions: list = []

    # ---- 読み書き ---------------------------------------------------------
    def load(self, path: str | None = None) -> None:
        path = path or STORE_PATH
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            return
        self.apply(raw)

    def apply(self, raw: dict) -> None:
        self.items = [WakeItem.from_dict(d) for d in raw.get("items", [])]
        self.prefs = Prefs.from_dict(raw.get("prefs"))
        groups = dict(DEFAULT_GROUPS)
        groups.update({k: str(v) for k, v in (raw.get("groups") or {}).items()
                       if k in DEFAULT_GROUPS})
        self.groups = groups
        self.almanac = Almanac(raw.get("date_lists"))
        presets = raw.get("timer_presets")
        if isinstance(presets, list) and presets:
            self.timer_presets = [int(x) for x in presets[:3]]
        self.timers = list(raw.get("timers") or [])
        self.todos = [TodoItem.from_dict(d) for d in raw.get("todos") or []]
        zones = raw.get("world_zones")
        if isinstance(zones, list):
            self.world_zones = [str(z) for z in zones]
        self.last_seen = str(raw.get("last_seen") or "")
        if not self.prefs.keep_group_filter:
            self.prefs.group_filter = []

    def snapshot(self) -> dict:
        return {
            "format": STORE_FORMAT,
            "app_version": APP_VERSION,
            "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
            "items": [i.to_dict() for i in self.items],
            "prefs": self.prefs.to_dict(),
            "groups": self.groups,
            "date_lists": self.almanac.to_dict(),
            "timer_presets": self.timer_presets,
            "timers": self.timers,
            "todos": [t.to_dict() for t in self.todos],
            "world_zones": self.world_zones,
            "last_seen": self.last_seen,
        }

    def save(self, path: str | None = None) -> None:
        path = path or STORE_PATH
        payload = json.dumps(self.snapshot(), ensure_ascii=False, indent=1)
        folder = os.path.dirname(path) or "."
        os.makedirs(folder, exist_ok=True)
        # 途中で落ちても既存ファイルを壊さないよう、一時ファイル経由で置き換える
        fd, tmp = tempfile.mkstemp(dir=folder, suffix=".part")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            shutil.move(tmp, path)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    # ---- バックアップ -----------------------------------------------------
    def write_backup(self, path: str | None = None) -> str:
        if path is None:
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            path = os.path.join(backups_dir(), "koyomi-%s.json" % stamp)
        self.save(path)
        return path

    def read_backup(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict) or "items" not in raw:
            raise ValueError(tr("このファイルはバックアップとして読み込めません。"))
        self.apply(raw)
        self.quarantine_actions()

    def quarantine_actions(self) -> list:
        """外から来たアラームの「連動して起動するもの」を保留にする。

        バックアップは中身がそのままプログラムの起動指定になりうる。
        自分で作ったものでなければ、画面で中身を見せて承認をもらうまで
        動かさない。承認待ちの一覧を返す。
        """
        waiting = []
        for item in self.items:
            if item.launch.has_work():
                item.launch.approved = False
                waiting.append(item)
        self.pending_actions = [i.uid for i in waiting]
        return waiting

    def approve_actions(self, approve: bool) -> None:
        for uid in self.pending_actions:
            item = self.find(uid)
            if item is None:
                continue
            if approve:
                item.launch.approved = True
            else:
                item.launch.enabled = False
                item.launch.approved = True
        self.pending_actions = []

    # ---- アラーム操作 -----------------------------------------------------
    def find(self, uid: str):
        for item in self.items:
            if item.uid == uid:
                return item
        return None

    def add(self, item: WakeItem) -> None:
        self.items.append(item)

    def replace(self, item: WakeItem) -> None:
        for idx, existing in enumerate(self.items):
            if existing.uid == item.uid:
                self.items[idx] = item
                return
        self.items.append(item)

    def remove(self, uid: str) -> None:
        self.items = [i for i in self.items if i.uid != uid]

    def group_name(self, key: str) -> str:
        """まだ名前を変えていないグループは、表示のときだけ訳す。"""
        name = self.groups.get(key, key)
        if name == DEFAULT_GROUPS.get(key):
            return tr(name)
        return name
