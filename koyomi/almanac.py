"""祝日と「登録日リスト」を束ねて、除外日の判定を提供する。

祝日そのものの定義は自前では持たず、公開ライブラリ jpholiday に委ねる。
未インストールの場合でもアプリは動くように、その場合は祝日判定を
常に「祝日でない」として扱う（UI 側で注意書きを出す）。
"""
from __future__ import annotations

import datetime as dt

from .i18n import tr
from .models import DEFAULT_DATE_LISTS, DayList

try:                                   # pragma: no cover - 環境依存
    import jpholiday
    HOLIDAY_LIB_READY = True
except ImportError:                    # pragma: no cover
    jpholiday = None
    HOLIDAY_LIB_READY = False


class Almanac:
    """祝日判定と日付リストの保管庫。"""

    def __init__(self, lists: dict | None = None):
        self.lists: dict = {}
        for key, name in DEFAULT_DATE_LISTS.items():
            self.lists[key] = DayList(key=key, name=name)
        if lists:
            for key, payload in lists.items():
                entry = DayList.from_dict(payload)
                entry.key = key
                if not entry.name:
                    entry.name = DEFAULT_DATE_LISTS.get(key, key)
                self.lists[key] = entry
        self._holiday_cache: dict = {}

    # ---- 祝日 -------------------------------------------------------------
    @staticmethod
    def holidays_available() -> bool:
        return HOLIDAY_LIB_READY

    def is_holiday(self, day: dt.date) -> bool:
        if not HOLIDAY_LIB_READY:
            return False
        hit = self._holiday_cache.get(day)
        if hit is None:
            hit = bool(jpholiday.is_holiday(day))
            self._holiday_cache[day] = hit
        return hit

    def holiday_name(self, day: dt.date) -> str:
        if not HOLIDAY_LIB_READY:
            return ""
        return jpholiday.is_holiday_name(day) or ""

    def holidays_between(self, start: dt.date, end: dt.date) -> list:
        """[start, end] の祝日を (日付, 名称) の並びで返す。"""
        if not HOLIDAY_LIB_READY:
            return []
        found = []
        for day, name in jpholiday.between(start, end):
            found.append((day, name))
        return found

    # ---- 日付リスト -------------------------------------------------------
    def list_names(self) -> dict:
        return {key: self.list_label(key) for key in self.lists}

    def list_label(self, key: str) -> str:
        """まだ名前を変えていないリストは、表示のときだけ訳す。"""
        entry = self.lists.get(key)
        if entry is None:
            return key
        if entry.name == DEFAULT_DATE_LISTS.get(key):
            return tr(entry.name)
        return entry.name

    def rename_list(self, key: str, name: str) -> None:
        if key in self.lists:
            self.lists[key].name = name.strip() or DEFAULT_DATE_LISTS.get(key, key)

    def days_of(self, key: str) -> set:
        entry = self.lists.get(key)
        return set(entry.days) if entry else set()

    def toggle_day(self, key: str, day: dt.date) -> bool:
        """指定日をリストに入れる／外す。入れたら True。"""
        entry = self.lists.get(key)
        if entry is None:
            return False
        if day in entry.days:
            entry.days.discard(day)
            return False
        entry.days.add(day)
        return True

    def add_days(self, key: str, days) -> int:
        entry = self.lists.get(key)
        if entry is None:
            return 0
        before = len(entry.days)
        entry.days.update(days)
        return len(entry.days) - before

    def remove_days(self, key: str, days) -> int:
        entry = self.lists.get(key)
        if entry is None:
            return 0
        before = len(entry.days)
        entry.days.difference_update(days)
        return before - len(entry.days)

    def clear_list(self, key: str) -> None:
        if key in self.lists:
            self.lists[key].days.clear()

    def import_holidays(self, key: str, start: dt.date, end: dt.date) -> int:
        """期間内の祝日をまとめてリストへ取り込む。"""
        return self.add_days(key, [d for d, _ in self.holidays_between(start, end)])

    # ---- 判定 -------------------------------------------------------------
    def is_blocked(self, day: dt.date, dodge_holidays: bool, list_keys) -> bool:
        """このアラームにとって day が除外日かどうか。"""
        if dodge_holidays and self.is_holiday(day):
            return True
        for key in list_keys or ():
            entry = self.lists.get(key)
            if entry and day in entry.days:
                return True
        return False

    def is_marked(self, day: dt.date, list_keys) -> bool:
        """「曜日＋リストの日」用: リストのいずれかに含まれるか。"""
        for key in list_keys or ():
            entry = self.lists.get(key)
            if entry and day in entry.days:
                return True
        return False

    # ---- 直列化 -----------------------------------------------------------
    def to_dict(self) -> dict:
        return {key: entry.to_dict() for key, entry in self.lists.items()}
