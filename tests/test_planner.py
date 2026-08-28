"""次回鳴動時刻の計算を確かめる。"""
import datetime as dt
import unittest

from koyomi import planner
from koyomi.almanac import Almanac
from koyomi.models import Cycle, RepeatRule, WakeItem

# 2026/08/27 は木曜日
BASE = dt.datetime(2026, 8, 27, 6, 0)


def alarm(**kw) -> WakeItem:
    item = WakeItem(hour=7, minute=0)
    for key, value in kw.items():
        setattr(item, key, value)
    return item


def days(item, almanac, count, after=BASE):
    return [d.strftime("%Y/%m/%d")
            for d in planner.upcoming_times(item, almanac, after, count)]


class Repeats(unittest.TestCase):
    def setUp(self):
        self.almanac = Almanac()

    def test_weekdays_skips_the_weekend(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                       weekdays=[0, 1, 2, 3, 4]))
        self.assertEqual(days(item, self.almanac, 4),
                         ["2026/08/27", "2026/08/28", "2026/08/31",
                          "2026/09/01"])

    def test_every_n_days_counts_from_the_anchor(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.EVERY_N_DAYS, step_days=4,
                                       anchor="2026-08-27"))
        self.assertEqual(days(item, self.almanac, 3),
                         ["2026/08/27", "2026/08/31", "2026/09/04"])

    def test_last_day_of_month(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.DAY_OF_MONTH,
                                       day_of_month=0))
        self.assertEqual(days(item, self.almanac, 4),
                         ["2026/08/31", "2026/09/30", "2026/10/31",
                          "2026/11/30"])

    def test_nth_weekday(self):
        # 第 2 火曜日
        item = alarm(repeat=RepeatRule(cycle=Cycle.NTH_WEEKDAY, week_index=2,
                                       weekday=1))
        self.assertEqual(days(item, self.almanac, 3),
                         ["2026/09/08", "2026/10/13", "2026/11/10"])

    def test_last_weekday_of_month(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.NTH_WEEKDAY, week_index=0,
                                       weekday=4))
        self.assertEqual(days(item, self.almanac, 2),
                         ["2026/08/28", "2026/09/25"])

    def test_run_rest_cycle(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.RUN_REST, run_days=3,
                                       rest_days=2, anchor="2026-08-27"))
        self.assertEqual(days(item, self.almanac, 5),
                         ["2026/08/27", "2026/08/28", "2026/08/29",
                          "2026/09/01", "2026/09/02"])

    def test_annual_falls_back_on_a_common_year(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.ANNUAL, month=2, day=29))
        # 2027 はうるう年ではないので 2/28 に寄せる
        self.assertEqual(days(item, self.almanac, 1)[0], "2027/02/28")

    def test_month_day_skips_months_without_that_day(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.DAY_OF_MONTH,
                                       day_of_month=31))
        self.assertEqual(days(item, self.almanac, 3),
                         ["2026/08/31", "2026/10/31", "2026/12/31"])


class Exclusions(unittest.TestCase):
    def setUp(self):
        self.almanac = Almanac()

    @unittest.skipUnless(Almanac.holidays_available(), "jpholiday が無い")
    def test_holidays_are_skipped(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                       weekdays=[0, 1, 2, 3, 4]),
                     dodge_holidays=True)
        # 2026/09/21-23 は敬老の日・国民の休日・秋分の日
        after = dt.datetime(2026, 9, 18, 8, 0)
        self.assertEqual(days(item, self.almanac, 2, after),
                         ["2026/09/24", "2026/09/25"])

    def test_saved_dates_are_skipped(self):
        self.almanac.add_days("L1", [dt.date(2026, 8, 28)])
        item = alarm(repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                       weekdays=[0, 1, 2, 3, 4]),
                     dodge_lists=["L1"])
        self.assertEqual(days(item, self.almanac, 2),
                         ["2026/08/27", "2026/08/31"])

    def test_marked_days_are_added_to_weekdays(self):
        self.almanac.add_days("L2", [dt.date(2026, 8, 30)])   # 日曜
        item = alarm(repeat=RepeatRule(cycle=Cycle.WEEKDAYS, weekdays=[0],
                                       add_marked_days=True,
                                       mark_lists=["L2"]))
        self.assertEqual(days(item, self.almanac, 2),
                         ["2026/08/30", "2026/08/31"])

    def test_skip_once_moves_one_occurrence_forward(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                       weekdays=[0, 1, 2, 3, 4, 5, 6]),
                     skip_once=True)
        self.assertEqual(
            planner.next_time(item, self.almanac, BASE).strftime("%Y/%m/%d"),
            "2026/08/28")

    def test_can_skip_only_repeating_alarms(self):
        once = alarm(repeat=RepeatRule(cycle=Cycle.SINGLE))
        weekly = alarm(repeat=RepeatRule(cycle=Cycle.WEEKDAYS, weekdays=[0]))
        self.assertFalse(planner.can_skip(once))
        self.assertTrue(planner.can_skip(weekly))
        weekly.active = False
        self.assertFalse(planner.can_skip(weekly))


class MissedAlarms(unittest.TestCase):
    def test_times_in_range_finds_what_was_due(self):
        almanac = Almanac()
        item = alarm(hour=7, minute=0,
                     repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                       weekdays=[0, 1, 2, 3, 4, 5, 6]))
        hits = planner.times_in_range(item, almanac,
                                      dt.datetime(2026, 8, 27, 6, 0),
                                      dt.datetime(2026, 8, 29, 8, 0))
        self.assertEqual([h.strftime("%m/%d %H:%M") for h in hits],
                         ["08/27 07:00", "08/28 07:00", "08/29 07:00"])

    def test_range_is_exclusive_at_the_start(self):
        almanac = Almanac()
        item = alarm(hour=7, minute=0,
                     repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                       weekdays=[0, 1, 2, 3, 4, 5, 6]))
        hits = planner.times_in_range(item, almanac,
                                      dt.datetime(2026, 8, 27, 7, 0),
                                      dt.datetime(2026, 8, 27, 8, 0))
        self.assertEqual(hits, [])


class Wording(unittest.TestCase):
    def test_duration_text_grows_into_days(self):
        self.assertEqual(planner.duration_text(45), "0:45")
        self.assertEqual(planner.duration_text(3725), "1:02:05")
        self.assertEqual(planner.duration_text(90061), "1日 1:01:01")

    def test_humanize_gap(self):
        now = dt.datetime(2026, 8, 27, 6, 0)
        self.assertEqual(
            planner.humanize_gap(now + dt.timedelta(hours=3, minutes=20), now),
            "あと 3時間 20分")
        self.assertEqual(planner.humanize_gap(now - dt.timedelta(minutes=1), now),
                         "経過")

    def test_repeat_digest_mentions_exclusions(self):
        almanac = Almanac()
        item = alarm(repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                       weekdays=[0, 1, 2, 3, 4]),
                     dodge_holidays=True)
        self.assertEqual(planner.repeat_digest(item, almanac),
                         "毎週 平日（祝日を除く）")


if __name__ == "__main__":
    unittest.main()
