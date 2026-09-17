"""次回鳴動時刻の計算を確かめる。"""
import _home
_home.guard()   # 本物の %APPDATA% を触らせない。koyomi を読み込む前に済ませる

import datetime as dt
import unittest

from koyomi import i18n, planner
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

    def test_every_day_rings_every_day(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.EVERY_DAY))
        self.assertEqual(days(item, self.almanac, 5),
                         ["2026/08/27", "2026/08/28", "2026/08/29",
                          "2026/08/30", "2026/08/31"])

    def test_every_day_still_steps_over_holidays(self):
        # 2026/09/21 敬老の日・09/22 国民の休日・09/23 秋分の日
        item = alarm(repeat=RepeatRule(cycle=Cycle.EVERY_DAY),
                     dodge_holidays=True)
        eve = dt.datetime(2026, 9, 19, 12, 0)
        self.assertEqual(days(item, self.almanac, 3, after=eve),
                         ["2026/09/20", "2026/09/24", "2026/09/25"])

    def test_every_day_is_not_the_same_as_a_single_shot(self):
        # 見た目は「次に来る時刻」で同じでも、鳴らしたあとの扱いが違う
        from koyomi.director import RingDirector
        from koyomi.vault import Vault
        vault = Vault()
        for cycle, still_on in ((Cycle.SINGLE, False), (Cycle.EVERY_DAY, True)):
            item = alarm(repeat=RepeatRule(cycle=cycle))
            RingDirector(vault).settle_after_stop(item)
            self.assertIs(item.active, still_on, cycle.value)

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

    def test_nth_weekday_can_take_several_weeks(self):
        # 第 2・第 4 木曜日。8/27 は第 4 木曜日
        item = alarm(repeat=RepeatRule(cycle=Cycle.NTH_WEEKDAY,
                                       week_indexes=[2, 4], weekday=3))
        self.assertEqual(days(item, self.almanac, 5),
                         ["2026/08/27", "2026/09/10", "2026/09/24",
                          "2026/10/08", "2026/10/22"])

    def test_fourth_and_last_are_one_day_when_the_month_has_four(self):
        # 9 月の木曜は 4 回（第 4 = 最終）、10 月は 5 回
        item = alarm(repeat=RepeatRule(cycle=Cycle.NTH_WEEKDAY,
                                       week_indexes=[4, 0], weekday=3))
        self.assertEqual(days(item, self.almanac, 5),
                         ["2026/08/27", "2026/09/24", "2026/10/22",
                          "2026/10/29", "2026/11/26"])

    def test_fifth_week_rings_only_in_months_that_have_one(self):
        item = alarm(repeat=RepeatRule(cycle=Cycle.NTH_WEEKDAY,
                                       week_indexes=[5], weekday=3))
        self.assertEqual(days(item, self.almanac, 2),
                         ["2026/10/29", "2026/12/31"])

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
        daily = alarm(repeat=RepeatRule(cycle=Cycle.EVERY_DAY))
        self.assertFalse(planner.can_skip(once))
        self.assertTrue(planner.can_skip(weekly))
        self.assertTrue(planner.can_skip(daily))
        weekly.active = False
        self.assertFalse(planner.can_skip(weekly))


# 2026/09/10 木・09/13 日・09/17 木・09/20 日
SATURDAY = dt.datetime(2026, 9, 12, 10, 0)


def shipping_day(**kw) -> WakeItem:
    """木・日の 03:00。"""
    return alarm(hour=3, minute=0,
                 repeat=RepeatRule(cycle=Cycle.WEEKDAYS, weekdays=[3, 6]), **kw)


class SkipOnce(unittest.TestCase):
    """「次の 1 回だけ飛ばす」は、決まった日の 1 回だけを飛ばす。"""

    def setUp(self):
        i18n.set_language("ja")
        self.almanac = Almanac()

    def armed(self) -> WakeItem:
        item = shipping_day()
        self.assertTrue(planner.arm_skip(item, self.almanac, SATURDAY))
        return item

    def test_arming_names_the_day_it_skips(self):
        item = self.armed()
        self.assertEqual(item.skip_on, "2026-09-13")
        self.assertEqual(planner.next_time(item, self.almanac, SATURDAY),
                         dt.datetime(2026, 9, 17, 3, 0))

    def test_once_that_day_is_past_the_next_one_is_left_alone(self):
        # 以前は「日曜 9/20」を返していた。木曜 9/17 まで飛ばしてしまう
        item = self.armed()
        self.assertEqual(
            planner.next_time(item, self.almanac, dt.datetime(2026, 9, 13, 4, 10)),
            dt.datetime(2026, 9, 17, 3, 0))

    def test_it_is_over_exactly_at_the_skipped_time(self):
        item = self.armed()
        self.assertFalse(planner.skip_is_over(item, dt.datetime(2026, 9, 13, 2, 59, 59)))
        self.assertTrue(planner.skip_is_over(item, dt.datetime(2026, 9, 13, 3, 0)))

    def test_the_card_says_which_day(self):
        self.assertEqual(planner.skip_label(self.armed()), "9/13(日) は飛ばす")

    def test_the_day_survives_saving_but_not_copying(self):
        item = self.armed()
        self.assertEqual(WakeItem.from_dict(item.to_dict()).skip_on, "2026-09-13")
        copy = item.copy_as_new()
        self.assertFalse(copy.skip_once)
        self.assertEqual(copy.skip_on, "")

    def test_old_saved_skips_point_at_the_one_after_the_last_ring(self):
        from koyomi.vault import Vault
        saved = shipping_day(skip_once=True,
                             last_fired_at="2026-09-10T03:00:38").to_dict()
        del saved["skip_on"]                     # 0.9.010 までの保存形式
        vault = Vault()
        vault.apply({"items": [saved]})
        self.assertEqual(vault.items[0].skip_on, "2026-09-13")

    def test_old_skips_that_never_rang_count_from_when_the_app_last_ran(self):
        from koyomi.vault import Vault
        saved = shipping_day(skip_once=True).to_dict()
        del saved["skip_on"]
        vault = Vault()
        vault.apply({"items": [saved], "last_seen": "2026-09-12T23:30:00"})
        self.assertEqual(vault.items[0].skip_on, "2026-09-13")

    def test_an_edit_keeps_the_same_day(self):
        item = self.armed()
        was = planner.skip_moment(item)
        item.title = "名前だけ変えた"
        planner.carry_skip(item, True, was, self.almanac, SATURDAY)
        self.assertEqual(item.skip_on, "2026-09-13")

    def test_an_edit_that_drops_that_day_skips_the_new_next_one(self):
        item = self.armed()
        was = planner.skip_moment(item)
        item.repeat = RepeatRule(cycle=Cycle.WEEKDAYS, weekdays=[0])   # 月曜だけ
        planner.carry_skip(item, True, was, self.almanac, SATURDAY)
        self.assertEqual(item.skip_on, "2026-09-14")

    def test_an_edit_saved_after_the_skipped_time_does_not_skip_again(self):
        item = self.armed()
        was = planner.skip_moment(item)
        planner.carry_skip(item, True, was, self.almanac,
                           dt.datetime(2026, 9, 13, 3, 5))
        self.assertFalse(item.skip_once)
        self.assertEqual(item.skip_on, "")

    def test_unticking_clears_the_day_too(self):
        item = self.armed()
        planner.carry_skip(item, False, planner.skip_moment(item),
                           self.almanac, SATURDAY)
        self.assertFalse(item.skip_once)
        self.assertEqual(item.skip_on, "")


class SkipWhileWatching(unittest.TestCase):
    """見張りが、飛ばす回をどう扱うか。時計は引数で渡す。"""

    def setUp(self):
        from koyomi.director import RingDirector
        from koyomi.vault import Vault
        self.vault = Vault()
        self.item = shipping_day()
        planner.arm_skip(self.item, self.vault.almanac, SATURDAY)
        self.vault.add(self.item)
        self.director = RingDirector(self.vault)
        self.rang, self.released = [], []
        self.director.due.connect(lambda item, _round: self.rang.append(item.uid))
        self.director.skip_over.connect(self.released.extend)

    def pass_through(self, start, end):
        self.director._last_check = start
        self.director._on_tick(end)

    def test_passing_the_skipped_time_rings_nothing_and_lets_go(self):
        self.pass_through(dt.datetime(2026, 9, 13, 2, 59, 59, 900000),
                          dt.datetime(2026, 9, 13, 3, 0, 0, 150000))
        self.assertEqual(self.rang, [])
        self.assertFalse(self.item.skip_once)
        self.assertEqual(self.released, [self.item],
                         "下ろしたことを画面と保存へ知らせていない")

    def test_a_restart_soon_after_does_not_call_the_skip_missed(self):
        plain = shipping_day()
        self.vault.add(plain)
        self.vault.last_seen = "2026-09-13T02:50:00"
        found = self.director.sweep_missed(dt.datetime(2026, 9, 13, 3, 20))
        self.assertEqual([item.uid for item, _when in found], [plain.uid])

    def test_when_the_app_was_off_at_that_time_thursday_still_rings(self):
        # 日曜の朝 9 時に起動。飛ばす回は、見張りの見ていないうちに過ぎている
        self.pass_through(dt.datetime(2026, 9, 13, 9, 0),
                          dt.datetime(2026, 9, 13, 9, 0, 0, 250000))
        self.assertFalse(self.item.skip_once, "過ぎた指定が残っている")
        self.pass_through(dt.datetime(2026, 9, 17, 2, 59, 59, 900000),
                          dt.datetime(2026, 9, 17, 3, 0, 0, 150000))
        self.assertEqual(self.rang, [self.item.uid])

    def test_stopping_a_ring_keeps_a_skip_meant_for_later(self):
        self.director.settle_after_stop(self.item)
        self.assertTrue(self.item.skip_once)
        self.assertEqual(self.item.skip_on, "2026-09-13")

    def test_a_flag_without_a_day_skips_the_first_one_it_meets(self):
        loose = shipping_day(skip_once=True)
        self.vault.add(loose)
        self.pass_through(dt.datetime(2026, 9, 13, 2, 59, 59, 900000),
                          dt.datetime(2026, 9, 13, 3, 0, 0, 150000))
        self.assertNotIn(loose.uid, self.rang)
        self.assertFalse(loose.skip_once)

    def test_a_dateless_flag_found_at_startup_counts_from_the_last_ring(self):
        # 60 分より長く止まっていても、見張りの起点ではなく最後に鳴った回から数える
        loose = shipping_day(skip_once=True, last_fired_at="2026-09-10T03:00:38")
        self.vault.add(loose)
        self.vault.last_seen = "2026-09-12T23:30:00"
        self.director.sweep_missed(dt.datetime(2026, 9, 13, 9, 0))
        self.assertEqual(loose.skip_on, "2026-09-13")


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


class Seconds(unittest.TestCase):
    def test_seconds_are_part_of_the_ring_time(self):
        item = alarm(hour=6, minute=30, second=15,
                     repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                       weekdays=[0, 1, 2, 3, 4, 5, 6]))
        when = planner.upcoming_times(item, Almanac(),
                                      dt.datetime(2026, 8, 27, 6, 0), 1)[0]
        self.assertEqual(when, dt.datetime(2026, 8, 27, 6, 30, 15))

    def test_a_second_before_still_counts_as_upcoming(self):
        item = alarm(hour=6, minute=30, second=15,
                     repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                       weekdays=[0, 1, 2, 3, 4, 5, 6]))
        just_before = dt.datetime(2026, 8, 27, 6, 30, 14)
        self.assertEqual(planner.upcoming_times(item, Almanac(), just_before, 1)[0],
                         dt.datetime(2026, 8, 27, 6, 30, 15))
        exactly = dt.datetime(2026, 8, 27, 6, 30, 15)
        self.assertEqual(planner.upcoming_times(item, Almanac(), exactly, 1)[0],
                         dt.datetime(2026, 8, 28, 6, 30, 15))

    def test_missed_sweep_sees_a_seconds_alarm(self):
        item = alarm(hour=6, minute=30, second=42,
                     repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                       weekdays=[0, 1, 2, 3, 4, 5, 6]))
        hits = planner.times_in_range(item, Almanac(),
                                      dt.datetime(2026, 8, 27, 6, 30, 41),
                                      dt.datetime(2026, 8, 27, 6, 30, 43))
        self.assertEqual(hits, [dt.datetime(2026, 8, 27, 6, 30, 42)])


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

    def test_repeat_digest_says_every_day_plainly(self):
        almanac = Almanac()
        item = alarm(repeat=RepeatRule(cycle=Cycle.EVERY_DAY))
        self.assertEqual(planner.repeat_digest(item, almanac), "毎日")
        item.dodge_holidays = True
        self.assertEqual(planner.repeat_digest(item, almanac),
                         "毎日（祝日を除く）")

    def test_weekdays_are_listed_from_sunday(self):
        i18n.set_language("ja")
        self.assertEqual(planner.weekday_digest([3, 6]), "日・木")
        self.assertEqual(planner.weekday_digest([0, 2, 6]), "日・月・水")
        self.assertEqual(planner.weekday_digest([6, 5]), "週末")
        self.assertEqual(planner.weekday_digest([4, 0, 1, 2, 3]), "平日")

    def test_repeat_digest_lists_every_chosen_week(self):
        i18n.set_language("ja")
        item = alarm(repeat=RepeatRule(cycle=Cycle.NTH_WEEKDAY,
                                       week_indexes=[4, 2], weekday=3))
        self.assertEqual(planner.repeat_digest(item), "毎月 第2・第4木曜")
        item.repeat.week_indexes = [0, 1]
        self.assertEqual(planner.repeat_digest(item), "毎月 第1・最終木曜")
        item.repeat = RepeatRule(cycle=Cycle.NTH_WEEKDAY, week_index=2, weekday=0)
        self.assertEqual(planner.repeat_digest(item), "毎月 第2月曜")

    def test_repeat_digest_uses_ordinals_in_english(self):
        self.addCleanup(i18n.set_language, "ja")
        i18n.set_language("en")
        item = alarm(repeat=RepeatRule(cycle=Cycle.NTH_WEEKDAY,
                                       week_indexes=[2, 4], weekday=3))
        self.assertEqual(planner.repeat_digest(item), "2nd, 4th Thu of every month")
        item.repeat.week_indexes = [0]
        self.assertEqual(planner.repeat_digest(item), "last Thu of every month")

    def test_every_day_reads_differently_from_all_seven_weekdays(self):
        # 同じ日に鳴っても、一覧の見え方で区別が付くこと
        almanac = Almanac()
        daily = alarm(repeat=RepeatRule(cycle=Cycle.EVERY_DAY))
        spelled = alarm(repeat=RepeatRule(cycle=Cycle.WEEKDAYS,
                                          weekdays=list(range(7))))
        self.assertEqual(days(daily, almanac, 3), days(spelled, almanac, 3))
        self.assertNotEqual(planner.repeat_digest(daily, almanac),
                            planner.repeat_digest(spelled, almanac))


if __name__ == "__main__":
    unittest.main()
