"""ToDo リストのデータ。

アラームとは独立した覚え書き。期限を入れておくと、期日が近い順に並ぶ。
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from .i18n import tr


class Weight(str, Enum):
    """優先度。"""

    HIGH = "high"
    MID = "mid"
    LOW = "low"

    @property
    def label(self) -> str:
        return {"high": tr("高"), "mid": tr("中"), "low": tr("低")}[self.value]

    @property
    def rank(self) -> int:
        return {"high": 0, "mid": 1, "low": 2}[self.value]


@dataclass
class TodoItem:
    uid: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str = ""
    weight: Weight = Weight.MID
    done: bool = False
    due: str = ""                  # ISO の日付。空なら期限なし
    note: str = ""
    created: str = field(
        default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    # ---- 期限まわり -------------------------------------------------------
    def due_date(self):
        if not self.due:
            return None
        try:
            return dt.date.fromisoformat(self.due)
        except ValueError:
            return None

    def days_left(self):
        day = self.due_date()
        if day is None:
            return None
        return (day - dt.date.today()).days

    def due_text(self) -> str:
        left = self.days_left()
        if left is None:
            return ""
        if left < 0:
            return tr("%d日 超過") % abs(left)
        if left == 0:
            return tr("今日まで")
        if left == 1:
            return tr("明日まで")
        return tr("あと %d日") % left

    def overdue(self) -> bool:
        left = self.days_left()
        return left is not None and left < 0 and not self.done

    # ---- 直列化 -----------------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["weight"] = (self.weight.value if isinstance(self.weight, Weight)
                       else str(self.weight))
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TodoItem":
        d = dict(d or {})
        raw = d.get("weight", Weight.MID.value)
        try:
            d["weight"] = Weight(raw)
        except (ValueError, TypeError):
            d["weight"] = Weight.MID
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def sort_key(item: TodoItem):
    """未完了を先に、次に期限の近さ、次に優先度。"""
    left = item.days_left()
    return (item.done, left if left is not None else 10_000,
            item.weight.rank, item.created)
