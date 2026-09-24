"""「次にいつ鳴るか」を求める計算。

方針はいたって素直で、候補日を 1 日ずつ前に進めながら
``day_matches`` と除外判定を順に当て、最初に通った日を採用する。
探索は既定で 800 日先まで（毎年繰り返しでも 2 回分は入る）。
"""
from __future__ import annotations

import calendar
import datetime as dt
import re

from .models import (NTH_WEEKS, ONE_SHOT, WEEKDAY_LABELS, WEEKDAY_ORDER, Cycle,
                     RepeatRule, WakeItem)
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

    if cycle == Cycle.EVERY_DAY:
        return True

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
        if day.weekday() != rule.weekday:
            return False
        return any(_nth_weekday_of_month(day.year, day.month, rule.weekday, n) == day
                   for n in rule.nth_weeks())

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
    """次に鳴る日時。飛ばすことになっている回は数えない。"""
    skip = skip_day(item, almanac, after)
    hits = upcoming_times(item, almanac, after, count=2 if skip else 1)
    for hit in hits:
        if hit.date() != skip:
            return hit
    return None


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
    return item.active and item.repeat.cycle not in ONE_SHOT


# --------------------------------------------------------------------------
# 「次の 1 回だけ飛ばす」
# --------------------------------------------------------------------------
# 飛ばす回は日付で覚えておく。1 日に 2 回鳴ることは無いので日付で足りる。
# 「見張りが次に見かけた回」を飛ばす作りだと、その時刻にアプリが
# 動いていなかったとき、続く回を代わりに飛ばしてしまう。

def skip_day(item: WakeItem, almanac=None, after: dt.datetime | None = None):
    """飛ばすことになっている回の日付。飛ばさないなら None。

    日付を持たない指定（``skip_once`` だけを立てたもの）は、
    ``after`` より後の最初の回を飛ばすものとして扱う。
    """
    if not item.skip_once:
        return None
    if item.skip_on:
        try:
            return dt.date.fromisoformat(item.skip_on)
        except ValueError:
            pass
    hits = upcoming_times(item, almanac, after, count=1)
    return hits[0].date() if hits else None


def skip_moment(item: WakeItem):
    """飛ばす回の日時。日付が決まっていなければ None。"""
    if not item.skip_once or not item.skip_on:
        return None
    try:
        day = dt.date.fromisoformat(item.skip_on)
    except ValueError:
        return None
    return dt.datetime.combine(day, item.time_of_day())


def arm_skip(item: WakeItem, almanac=None, after: dt.datetime | None = None) -> bool:
    """次の 1 回を飛ばすことにする。この先に鳴る回が無ければ False。"""
    hits = upcoming_times(item, almanac, after, count=1)
    if not hits:
        return False
    item.skip_once = True
    item.skip_on = hits[0].date().isoformat()
    return True


def disarm_skip(item: WakeItem) -> None:
    item.skip_once = False
    item.skip_on = ""


def pin_skip(item: WakeItem, almanac=None, after: dt.datetime | None = None) -> None:
    """日付を持たない飛ばし指定に、どの回のことかを書き添える。"""
    if not item.skip_once or item.skip_on:
        return
    day = skip_day(item, almanac, after)
    if day is None:
        disarm_skip(item)
    else:
        item.skip_on = day.isoformat()


def skip_is_over(item: WakeItem, now: dt.datetime) -> bool:
    """飛ばす回の時刻を過ぎたか。過ぎたら、もう飛ばすものは無い。"""
    if not item.skip_once or not item.skip_on:
        return False
    moment = skip_moment(item)
    return moment is None or now >= moment      # 読めない日付も当ての無い指定


def _rings_on(item: WakeItem, day: dt.date, almanac=None) -> bool:
    if not day_matches(item.repeat, day, almanac):
        return False
    return almanac is None or not almanac.is_blocked(
        day, item.dodge_holidays, item.dodge_lists)


def carry_skip(item: WakeItem, wanted: bool, was_due_at, almanac=None,
               now: dt.datetime | None = None) -> None:
    """編集して保存するときの「次の 1 回だけ飛ばす」。

    ``was_due_at`` は、編集画面を開いた時点で飛ばすことになっていた回の日時。

      - 開いている間にその回を過ぎていれば、飛ばし終えたものとして下ろす
      - 編集後もその日に鳴る予定が残っていれば、同じ回を飛ばす
      - 時刻や曜日を変えてその回が無くなったら、新しい予定の次の回を飛ばす
    """
    now = now or dt.datetime.now()
    if not wanted:
        disarm_skip(item)
        return
    if was_due_at is not None:
        if was_due_at <= now:
            disarm_skip(item)
            return
        day = was_due_at.date()
        if (dt.datetime.combine(day, item.time_of_day()) > now
                and _rings_on(item, day, almanac)):
            item.skip_once = True
            item.skip_on = day.isoformat()
            return
    if not arm_skip(item, almanac, now):
        disarm_skip(item)


def skip_label(item: WakeItem) -> str:
    """一覧の札に出す「9/13(日) は飛ばす」。"""
    moment = skip_moment(item)
    if moment is None:
        return tr("次は飛ばす")
    day = "%d/%d(%s)" % (moment.month, moment.day,
                         tr(WEEKDAY_LABELS[moment.weekday()]))
    return tr("%s は飛ばす") % day


# --------------------------------------------------------------------------
# 表示用の文字列
# --------------------------------------------------------------------------
def weekday_digest(days) -> str:
    picked = set(days)
    if not picked:
        return tr("曜日未選択")
    if picked == set(range(7)):
        return tr("毎日")
    if picked == set(range(5)):
        return tr("平日")
    if picked == {5, 6}:
        return tr("週末")
    # 日曜はじめに並べる（日・月・火…）
    return tr("・").join(tr(WEEKDAY_LABELS[d]) for d in WEEKDAY_ORDER if d in picked)


def repeat_digest(item: WakeItem, almanac=None) -> str:
    """繰り返し条件を 1 行にまとめる。"""
    rule = item.repeat
    cycle = rule.cycle
    if cycle == Cycle.SINGLE:
        text = tr("1回だけ")
    elif cycle == Cycle.ON_DATE:
        d = rule.anchor_date()
        text = tr("%d/%d に1回") % (d.month, d.day)
    elif cycle == Cycle.EVERY_DAY:
        text = tr("毎日")
    elif cycle == Cycle.WEEKDAYS:
        text = tr("毎週 ") + weekday_digest(rule.weekdays)
        if rule.add_marked_days and rule.mark_lists:
            text += tr(" ＋登録日")
    elif cycle == Cycle.EVERY_N_DAYS:
        text = tr("%d日おき") % max(1, rule.step_days)
    elif cycle == Cycle.DAY_OF_MONTH:
        text = tr("毎月 末日") if rule.day_of_month <= 0 else tr("毎月 %d日") % rule.day_of_month
    elif cycle == Cycle.NTH_WEEKDAY:
        nth = tr("・").join(tr(NTH_WEEKS[n]) for n in rule.nth_weeks())
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


def date_text(moment, pattern: str) -> str:
    """``pattern`` の %Y などを ``moment`` の値で埋める。

    Windows の strftime は、書式をいったん OS の文字コードへ直してから使う。
    英語版の Windows では「年」「月」を直せずに落ちるので、日本語の混ざった
    書式はそのまま渡さず、%Y のような指示子だけを 1 つずつ渡す。
    """
    return re.sub(r"%.", lambda hit: moment.strftime(hit.group()), pattern)
