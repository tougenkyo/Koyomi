"""アプリが扱うデータの型定義。

すべて標準の dataclass で表現し、``to_dict`` / ``from_dict`` で JSON と
往復できるようにしてある。永続化の実体は vault.py が持つ。
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from .actions import LaunchPlan
from .i18n import tr


# --------------------------------------------------------------------------
# 列挙型
# --------------------------------------------------------------------------
class Cycle(str, Enum):
    """繰り返しの種別。"""

    SINGLE = "single"            # 繰り返さない（次に来る設定時刻に一度だけ）
    ON_DATE = "on_date"          # 指定した 1 日だけ
    WEEKDAYS = "weekdays"        # 選んだ曜日ごと
    EVERY_N_DAYS = "every_n"     # 起点日から N 日周期
    DAY_OF_MONTH = "day_of_mo"   # 毎月 x 日（0 は月末）
    NTH_WEEKDAY = "nth_wday"     # 毎月 第n週の曜日
    ANNUAL = "annual"            # 毎年 同じ月日
    RUN_REST = "run_rest"        # 起点日から「鳴らす a 日 / 休む b 日」の周期

    @property
    def label(self) -> str:
        return tr(_CYCLE_LABELS[self])


_CYCLE_LABELS = {
    Cycle.SINGLE: "繰り返さない",
    Cycle.ON_DATE: "日付を指定",
    Cycle.WEEKDAYS: "曜日を指定",
    Cycle.EVERY_N_DAYS: "N日おき",
    Cycle.DAY_OF_MONTH: "毎月・日付",
    Cycle.NTH_WEEKDAY: "毎月・第n曜日",
    Cycle.ANNUAL: "毎年",
    Cycle.RUN_REST: "鳴動／休止の周期",
}


class ToneKind(str, Enum):
    """鳴動音の供給元。"""

    BUILTIN = "builtin"      # 同梱の合成音
    FILE = "file"            # 指定した音声ファイル
    FOLDER_PICK = "folder"   # フォルダ内からランダムに 1 曲
    SILENT = "silent"        # 音を出さない


class Guard(str, Enum):
    """停止／スヌーズを確定させるための操作方法。"""

    TAP = "tap"              # 1 回押す
    HOLD = "hold"            # 長押し
    SLIDE = "slide"          # つまみを端までドラッグ
    ARITHMETIC = "math"      # 計算問題に答える
    ORDER_TAP = "order"      # 記号を提示順にタップ
    SHAPE_MATCH = "shape"    # 色と形が一致する選択肢を選ぶ

    @property
    def label(self) -> str:
        return tr(_GUARD_LABELS[self])


_GUARD_LABELS = {
    Guard.TAP: "ボタンを押す",
    Guard.HOLD: "長押しする",
    Guard.SLIDE: "スライドする",
    Guard.ARITHMETIC: "計算問題を解く",
    Guard.ORDER_TAP: "記号を順番にタップ",
    Guard.SHAPE_MATCH: "色と形を選ぶ",
}


class Toughness(str, Enum):
    LIGHT = "light"
    MIDDLE = "middle"
    HEAVY = "heavy"

    @property
    def label(self) -> str:
        return {"light": tr("やさしい"), "middle": tr("ふつう"), "heavy": tr("むずかしい")}[self.value]


class SnoozeOrigin(str, Enum):
    """スヌーズ間隔をどの時点から数えるか。"""

    RING_START = "ring_start"    # 鳴り始めた時刻から
    USER_ACTION = "user_action"  # スヌーズ操作をした時刻から


class ListOrder(str, Enum):
    TIME = "time"
    NAME = "name"
    GROUP = "group"
    ACTIVE_FIRST = "active_first"
    NEXT_RING = "next_ring"

    @property
    def label(self) -> str:
        return {
            "time": tr("設定時刻の早い順"),
            "name": tr("名前順"),
            "group": tr("グループ順"),
            "active_first": tr("ONを先に、次いで設定時刻"),
            "next_ring": tr("次に鳴る順"),
        }[self.value]


WEEKDAY_LABELS = ("月", "火", "水", "木", "金", "土", "日")


def as_enum(enum_cls, value, fallback=None):
    """値を列挙型に揃える。

    ここの列挙型はどれも ``str`` を継承しているため、Qt のウィジェットに
    預けて取り出すと素の文字列に戻ってくることがある。読み出し口では
    必ずこの関数を通して型を揃える。
    """
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except (ValueError, TypeError):
        return fallback if fallback is not None else list(enum_cls)[0]


# --------------------------------------------------------------------------
# 部品となる設定群
# --------------------------------------------------------------------------
@dataclass
class RepeatRule:
    """いつ鳴らすかの条件。``cycle`` に応じて使うフィールドが変わる。"""

    cycle: Cycle = Cycle.SINGLE
    weekdays: list = field(default_factory=list)   # 月=0 .. 日=6
    anchor: str = ""                               # 起点日 (ISO 文字列)
    step_days: int = 2                             # EVERY_N_DAYS
    day_of_month: int = 1                          # DAY_OF_MONTH (0 = 月末)
    week_index: int = 1                            # NTH_WEEKDAY: 1..5, 0 = 最終
    weekday: int = 0                               # NTH_WEEKDAY
    month: int = 1                                 # ANNUAL
    day: int = 1                                   # ANNUAL
    run_days: int = 1                              # RUN_REST 鳴らす日数
    rest_days: int = 1                             # RUN_REST 休む日数
    add_marked_days: bool = False                  # 曜日指定＋リストの日
    mark_lists: list = field(default_factory=list) # 追加対象にする DayList キー

    def anchor_date(self) -> dt.date:
        if self.anchor:
            try:
                return dt.date.fromisoformat(self.anchor)
            except ValueError:
                pass
        return dt.date.today()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cycle"] = as_enum(Cycle, self.cycle).value
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> "RepeatRule":
        d = dict(d or {})
        d["cycle"] = Cycle(d.get("cycle", Cycle.SINGLE.value))
        d["weekdays"] = sorted({int(x) for x in d.get("weekdays", [])})
        d["mark_lists"] = [str(x) for x in d.get("mark_lists", [])]
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SoundPlan:
    """鳴動音の設定。スヌーズ回ごとに別の SoundPlan を持たせられる。"""

    kind: ToneKind = ToneKind.BUILTIN
    source: str = "kizashi"      # BUILTIN なら合成音名、FILE/FOLDER ならパス
    volume: int = 70             # 0-100
    fade_seconds: int = 0        # 0 でフェードインなし
    delay_start: bool = False    # 鳴り始めを 2 秒遅らせる
    loop: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = as_enum(ToneKind, self.kind).value
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> "SoundPlan":
        d = dict(d or {})
        d["kind"] = ToneKind(d.get("kind", ToneKind.BUILTIN.value))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SnoozePlan:
    enabled: bool = True
    minutes: int = 5                       # 1 .. 1439
    max_rounds: int = 5                    # 0 で無制限
    origin: SnoozeOrigin = SnoozeOrigin.USER_ACTION
    allow_interval_change: bool = True     # 鳴動中に間隔を変えられるか
    show_round_count: bool = True
    tone_round1: Any = None                # SoundPlan | None
    tone_round2: Any = None
    tone_round3plus: Any = None

    def tone_for(self, round_no: int):
        if round_no <= 1:
            return self.tone_round1
        if round_no == 2:
            return self.tone_round2
        return self.tone_round3plus

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "minutes": self.minutes,
            "max_rounds": self.max_rounds,
            "origin": as_enum(SnoozeOrigin, self.origin).value,
            "allow_interval_change": self.allow_interval_change,
            "show_round_count": self.show_round_count,
            "tone_round1": self.tone_round1.to_dict() if self.tone_round1 else None,
            "tone_round2": self.tone_round2.to_dict() if self.tone_round2 else None,
            "tone_round3plus": (self.tone_round3plus.to_dict()
                                if self.tone_round3plus else None),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "SnoozePlan":
        d = dict(d or {})
        obj = cls()
        obj.enabled = bool(d.get("enabled", True))
        obj.minutes = int(d.get("minutes", 5))
        obj.max_rounds = int(d.get("max_rounds", 5))
        obj.origin = SnoozeOrigin(d.get("origin", SnoozeOrigin.USER_ACTION.value))
        obj.allow_interval_change = bool(d.get("allow_interval_change", True))
        obj.show_round_count = bool(d.get("show_round_count", True))
        for name in ("tone_round1", "tone_round2", "tone_round3plus"):
            raw = d.get(name)
            setattr(obj, name, SoundPlan.from_dict(raw) if raw else None)
        return obj


@dataclass
class GuardPlan:
    """解除操作の設定。停止用・スヌーズ用でそれぞれ 1 つ持つ。"""

    style: Guard = Guard.TAP
    toughness: Toughness = Toughness.LIGHT
    rounds: int = 1              # 計算問題／色形マッチ／順番タップの出題数
    hold_seconds: float = 2.0    # 長押しの必要時間
    confirm: bool = False        # 確定前に確認ダイアログを挟む

    def to_dict(self) -> dict:
        d = asdict(self)
        d["style"] = as_enum(Guard, self.style).value
        d["toughness"] = as_enum(Toughness, self.toughness).value
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> "GuardPlan":
        d = dict(d or {})
        d["style"] = Guard(d.get("style", Guard.TAP.value))
        d["toughness"] = Toughness(d.get("toughness", Toughness.LIGHT.value))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# --------------------------------------------------------------------------
# アラーム本体
# --------------------------------------------------------------------------
@dataclass
class WakeItem:
    """登録されたアラーム 1 件。"""

    uid: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    active: bool = True
    hour: int = 7
    minute: int = 0
    title: str = ""
    group: str = "a"
    repeat: RepeatRule = field(default_factory=RepeatRule)

    # 除外条件
    dodge_holidays: bool = False
    dodge_lists: list = field(default_factory=list)   # DayList のキー
    skip_once: bool = False

    # 音・振る舞い
    sound: SoundPlan = field(default_factory=SoundPlan)
    snooze: SnoozePlan = field(default_factory=SnoozePlan)
    stop_guard: GuardPlan = field(default_factory=GuardPlan)
    snooze_guard: GuardPlan = field(default_factory=GuardPlan)

    launch: Any = field(default_factory=LaunchPlan)   # 連動して起動するもの

    auto_stop_minutes: int = 5        # 0 で自動停止しない
    flash_screen: bool = True         # バイブレーションの代替
    erase_after_stop: bool = False
    shrink_text: bool = False
    toggle_locked: bool = False       # ON/OFF スイッチの誤操作防止

    last_fired_at: str = ""           # 実行時に更新

    # ---- 表示用ヘルパ -----------------------------------------------------
    @property
    def clock_text(self) -> str:
        return "%02d:%02d" % (self.hour, self.minute)

    def display_title(self, fallback: str = tr("アラーム")) -> str:
        return self.title.strip() or fallback

    def time_of_day(self) -> dt.time:
        return dt.time(self.hour, self.minute)

    def copy_as_new(self) -> "WakeItem":
        clone = WakeItem.from_dict(self.to_dict())
        clone.uid = uuid.uuid4().hex[:12]
        clone.skip_once = False
        clone.last_fired_at = ""
        clone.toggle_locked = False
        if clone.title:
            clone.title = clone.title + tr(" の控え")
        return clone

    # ---- 直列化 -----------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "active": self.active,
            "hour": self.hour,
            "minute": self.minute,
            "title": self.title,
            "group": self.group,
            "repeat": self.repeat.to_dict(),
            "dodge_holidays": self.dodge_holidays,
            "dodge_lists": list(self.dodge_lists),
            "skip_once": self.skip_once,
            "sound": self.sound.to_dict(),
            "snooze": self.snooze.to_dict(),
            "stop_guard": self.stop_guard.to_dict(),
            "snooze_guard": self.snooze_guard.to_dict(),
            "launch": self.launch.to_dict(),
            "auto_stop_minutes": self.auto_stop_minutes,
            "flash_screen": self.flash_screen,
            "erase_after_stop": self.erase_after_stop,
            "shrink_text": self.shrink_text,
            "toggle_locked": self.toggle_locked,
            "last_fired_at": self.last_fired_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WakeItem":
        d = dict(d or {})
        obj = cls()
        for key in ("uid", "title", "group", "last_fired_at"):
            if d.get(key) is not None:
                setattr(obj, key, str(d[key]))
        for key in ("hour", "minute", "auto_stop_minutes"):
            if d.get(key) is not None:
                setattr(obj, key, int(d[key]))
        for key in ("active", "dodge_holidays", "skip_once", "flash_screen",
                    "erase_after_stop", "shrink_text", "toggle_locked"):
            if d.get(key) is not None:
                setattr(obj, key, bool(d[key]))
        obj.dodge_lists = [str(x) for x in d.get("dodge_lists", [])]
        obj.repeat = RepeatRule.from_dict(d.get("repeat"))
        obj.sound = SoundPlan.from_dict(d.get("sound"))
        obj.snooze = SnoozePlan.from_dict(d.get("snooze"))
        obj.stop_guard = GuardPlan.from_dict(d.get("stop_guard"))
        obj.snooze_guard = GuardPlan.from_dict(d.get("snooze_guard"))
        obj.launch = LaunchPlan.from_dict(d.get("launch"))
        return obj


# --------------------------------------------------------------------------
# グループ・登録日リスト
# --------------------------------------------------------------------------
DEFAULT_GROUPS = {
    "a": "グループ 1",
    "b": "グループ 2",
    "c": "グループ 3",
    "d": "グループ 4",
    "e": "グループ 5",
}

DEFAULT_DATE_LISTS = {"L%d" % i: "日付リスト %d" % i for i in range(1, 9)}


@dataclass
class DayList:
    """「この日は鳴らさない」等に使う日付の集合。"""

    key: str
    name: str
    days: set = field(default_factory=set)

    def to_dict(self) -> dict:
        return {"key": self.key, "name": self.name,
                "days": sorted(d.isoformat() for d in self.days)}

    @classmethod
    def from_dict(cls, d: dict) -> "DayList":
        days = set()
        for s in d.get("days", []):
            try:
                days.add(dt.date.fromisoformat(s))
            except (TypeError, ValueError):
                continue
        return cls(key=str(d.get("key", "")), name=str(d.get("name", "")), days=days)


# --------------------------------------------------------------------------
# アプリ共通設定
# --------------------------------------------------------------------------
QUICK_ACTIONS = {
    "add": "追加",
    "all_on": "すべてON",
    "all_off": "すべてOFF",
    "purge_off": "OFFを削除",
    "timers": "タイマー",
    "search": "検索",
}


@dataclass
class Prefs:
    """全体設定と、新規アラームの初期値。"""

    order: ListOrder = ListOrder.TIME
    quick_actions: list = field(default_factory=lambda: ["add", "all_off", "timers"])
    show_quick_bar: bool = True
    group_filter: list = field(default_factory=list)   # 空なら全表示
    keep_group_filter: bool = True
    tray_next_alarm: bool = True
    notify_auto_stop: bool = True
    overlap_policy: str = "snooze"     # "snooze" | "stop" | "queue"
    catch_up_window_minutes: int = 60  # 起動時にこの範囲の取りこぼしを鳴らす
    left_align_titles: bool = False

    # 見た目とことば
    theme: str = "yoichi-kohaku"
    language: str = "ja"
    float_bar: bool = False

    # 電源まわり
    wake_pc: bool = True               # 時刻に合わせて PC を起こす
    keep_awake_ringing: bool = True    # 鳴っている間は寝かせない
    auto_sleep: bool = False           # 決めた時刻に PC をスリープさせる
    auto_sleep_at: str = "01:00"

    default_item: dict = field(default_factory=lambda: WakeItem().to_dict())

    def new_item(self) -> WakeItem:
        item = WakeItem.from_dict(self.default_item)
        item.uid = uuid.uuid4().hex[:12]
        item.skip_once = False
        item.last_fired_at = ""
        item.toggle_locked = False
        item.active = True
        return item

    def to_dict(self) -> dict:
        d = asdict(self)
        d["order"] = as_enum(ListOrder, self.order).value
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> "Prefs":
        d = dict(d or {})
        d["order"] = ListOrder(d.get("order", ListOrder.TIME.value))
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        obj = cls(**known)
        if not obj.default_item:
            obj.default_item = WakeItem().to_dict()
        obj.quick_actions = [a for a in obj.quick_actions if a in QUICK_ACTIONS][:3]
        for cand in QUICK_ACTIONS:
            if len(obj.quick_actions) >= 3:
                break
            if cand not in obj.quick_actions:
                obj.quick_actions.append(cand)
        return obj
