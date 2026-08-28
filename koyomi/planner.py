"""「次にいつ鳴るか」を求める計算。

方針はいたって素直で、候補日を 1 日ずつ前に進めながら
``day_matches`` と除外判定を順に当て、最初に通った日を採用する。
探索は既定で 800 日先まで（毎年繰り返しでも 2 回分は入る）。
"""
from __future__ import annotations

import calendar
import datetime as dt

from .models import WEEKDAY_LABELS, Cycle, RepeatRule, WakeItem
from .i18n import tr

SEARCH_HORIZON_DAYS = 800


# --------------------------------------------------------------------------
# 日付が条件に合うか
# --------------------------------------------------------------------------
def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _nth_weekday_of_month(year: int, month: int, weekday: int, index: int) -> dt.date | None:
    """index=1..5 は第n週、index=0 は最終週。該当なしなら None。"""
    span = _last_day_of_month(year, month)
    hits = [d for d in range(1, span + 1)
            if dt.date(year, month, d).weekday() == weekday]
    if not hits:
        return None
    if index <= 0:
        return dt.date(year, month, hits[-1])
    if index > len(hits):
        return None
    return dt.date(year, month, hits[index - 1])


def day_matches(rule: RepeatRule, day: dt.date, almanac=None) -> bool:
    """繰り返し条件そのもの（除外判定は含まない）を満たす日か。"""
    cycle = rule.cycle

    if cycle in (Cycle.SINGLE,):
        return True

    if cycle == Cycle.ON_DATE:
        return day == rule.anchor_date()

    if cycle == Cycle.WEEKDAYS:
        if day.weekday() in rule.weekdays:
            return True
        if rule.add_marked_days and almanac is not None:
            return almanac.is_marked(day, rule.mark_lists)
        return False

    if cycle == Cycle.EVERY_N_DAYS:
        step = max(1, rule.step_days)
        delta = (day - rule.anchor_date()).days
        return delta >= 0 and delta % step == 0

    if cycle == Cycle.DAY_OF_MONTH:
        if rule.day_of_month <= 0:
            return day.day == _last_day_of_month(day.year, day.month)
        return day.day == rule.day_of_month

    if cycle == Cycle.NTH_WEEKDAY:
        target = _nth_weekday_of_month(day.year, day.month, rule.weekday, rule.week_index)
        return target == day

    if cycle == Cycle.ANNUAL:
        if rule.month == 2 and rule.day == 29 and not calendar.isleap(day.year):
            # うるう日指定の平年は 2/28 に寄せる
            return day.month == 2 and day.day == 28
        return day.month == rule.month and day.day == rule.day

    if cycle == Cycle.RUN_REST:
        run = max(1, rule.run_days)
        rest = max(0, rule.rest_days)
        delta = (day - rule.anchor_date()).days
        if delta < 0:
            return False
        return delta % (run + rest) < run

    return False


# --------------------------------------------------------------------------
# 次回鳴動時刻
# --------------------------------------------------------------------------
def upcoming_times(item: WakeItem, almanac=None, after: dt.datetime | None = None,
                   count: int = 1) -> list:
    """``after`` より後に鳴る日時を古い順に最大 ``count`` 件返す。"""
    now = after or dt.datetime.now()
    at = item.time_of_day()
    found = []
    day = now.date()
    for _ in range(SEARCH_HORIZON_DAYS):
        moment = dt.datetime.combine(day, at)
        if moment > now and day_matches(item.repeat, day, almanac):
            blocked = False
            if almanac is not None:
                blocked = almanac.is_blocked(day, item.dodge_holidays, item.dodge_lists)
            if not blocked:
                found.append(moment)
                if len(found) >= count:
                    break
        day += dt.timedelta(days=1)
    return found


def next_time(item: WakeItem, almanac=None, after: dt.datetime | None = None):
    """次に鳴る日時。``skip_once`` が立っていれば 1 回分読み飛ばす。"""
    want = 2 if item.skip_once else 1
    hits = upcoming_times(item, almanac, after, count=want)
    if len(hits) < want:
        return None
    return hits[-1]


def times_in_range(item: WakeItem, almanac, start: dt.datetime,
                   end: dt.datetime) -> list:
    """(start, end] の間に鳴るはずだった日時を列挙する。取りこぼし検出用。"""
    if end <= start:
        return []
    at = item.time_of_day()
    hits = []
    day = start.date()
    limit = end.date()
    while day <= limit:
        moment = dt.datetime.combine(day, at)
        if start < moment <= end and day_matches(item.repeat, day, almanac):
            if almanac is None or not almanac.is_blocked(
                    day, item.dodge_holidays, item.dodge_lists):
                hits.append(moment)
        day += dt.timedelta(days=1)
    return hits


def next_time_for_display(item: WakeItem, almanac=None):
    """一覧に出すための次回時刻。OFF のときは None。"""
    if not item.active:
        return None
    return next_time(item, almanac)


def can_skip(item: WakeItem) -> bool:
    """「次の 1 回だけ飛ばす」を適用できるアラームか。"""
    return item.active and item.repeat.cycle not in (Cycle.SINGLE, Cycle.ON_DATE)


# --------------------------------------------------------------------------
# 表示用の文字列
# --------------------------------------------------------------------------
def weekday_digest(days) -> str:
    picked = sorted(set(days))
    if not picked:
        return tr("曜日未選択")
    if picked == [0, 1, 2, 3, 4, 5, 6]:
        return tr("毎日")
    if picked == [0, 1, 2, 3, 4]:
        return tr("平日")
    if picked == [5, 6]:
        return tr("週末")
    return tr("・").join(tr(WEEKDAY_LABELS[d]) for d in picked)


def repeat_digest(item: WakeItem, almanac=None) -> str:
    """繰り返し条件を 1 行にまとめる。"""
    rule = item.repeat
    cycle = rule.cycle
    if cycle == Cycle.SINGLE:
        text = tr("1回だけ")
    elif cycle == Cycle.ON_DATE:
        d = rule.anchor_date()
        text = tr("%d/%d に1回") % (d.month, d.day)
    elif cycle == Cycle.WEEKDAYS:
        text = tr("毎週 ") + weekday_digest(rule.weekdays)
        if rule.add_marked_days and rule.mark_lists:
            text += tr(" ＋登録日")
    elif cycle == Cycle.EVERY_N_DAYS:
        text = tr("%d日おき") % max(1, rule.step_days)
    elif cycle == Cycle.DAY_OF_MONTH:
        text = tr("毎月 末日") if rule.day_of_month <= 0 else tr("毎月 %d日") % rule.day_of_month
    elif cycle == Cycle.NTH_WEEKDAY:
        nth = tr("最終") if rule.week_index <= 0 else tr("第%d") % rule.week_index
        text = tr("毎月 %s%s曜") % (nth, tr(WEEKDAY_LABELS[rule.weekday]))
    elif cycle == Cycle.ANNUAL:
        text = tr("毎年 %d/%d") % (rule.month, rule.day)
    elif cycle == Cycle.RUN_REST:
        text = tr("%d日鳴らして%d日休む") % (max(1, rule.run_days), max(0, rule.rest_days))
    else:
        text = "-"

    extras = []
    if item.dodge_holidays:
        extras.append(tr("祝日を除く"))
    if item.dodge_lists and almanac is not None:
        names = [almanac.list_label(k) for k in item.dodge_lists
                 if k in almanac.lists]
        if names:
            extras.append("／".join(names) + tr("を除く"))
    elif item.dodge_lists:
        extras.append(tr("登録日を除く"))
    if extras:
        text += tr("（%s）") % tr("、").join(extras)
    return text


def humanize_gap(target: dt.datetime, now: dt.datetime | None = None) -> str:
    """「あと 3 時間 20 分」のような相対表現。"""
    now = now or dt.datetime.now()
    secs = int((target - now).total_seconds())
    if secs < 0:
        return tr("経過")
    if secs < 60:
        return tr("まもなく")
    mins = secs // 60
    days, rem = divmod(mins, 1440)
    hours, minutes = divmod(rem, 60)
    parts = []
    if days:
        parts.append(tr("%d日") % days)
    if hours:
        parts.append(tr("%d時間") % hours)
    if minutes and not days:
        parts.append(tr("%d分") % minutes)
    return tr("あと ") + " ".join(parts) if parts else tr("まもなく")


def duration_text(total_seconds: int) -> str:
    """秒数を 1:02:03 形式に。1 日を超えるぶんは日数を前に出す。"""
    total_seconds = max(0, int(total_seconds))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    if days:
        return tr("%d日 %d:%02d:%02d") % (days, hours, mins, secs)
    if hours:
        return "%d:%02d:%02d" % (hours, mins, secs)
    return "%d:%02d" % (mins, secs)


def span_text(total_seconds: int) -> str:
    """「3日 と 4時間」のような、ざっくりした長さの言い方。"""
    total_seconds = max(0, int(total_seconds))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(tr("%d日") % days)
    if hours:
        parts.append(tr("%d時間") % hours)
    if mins and not days:
        parts.append(tr("%d分") % mins)
    if secs and not days and not hours:
        parts.append(tr("%d秒") % secs)
    return " ".join(parts) or tr("0秒")
