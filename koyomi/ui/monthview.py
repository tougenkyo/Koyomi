"""カレンダー。祝日に色を付けた月の暦と、選んだ日の予定を見る窓。

祝日は almanac（中身は jpholiday）から引く。日曜と祝日は赤、土曜は青。
右側には選んだ日の祝日名・日付リスト・その日に鳴るアラームと、
表示している月の祝日を並べる。
"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QTextCharFormat
from PySide6.QtWidgets import (QCalendarWidget, QDialog, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout)

from .. import planner
from ..models import WEEKDAY_LABELS
from . import theme
from .widgets import month_arrows, sunday_first
from ..i18n import tr


def _to_qdate(day: dt.date) -> QDate:
    return QDate(day.year, day.month, day.day)


def _to_date(qd: QDate) -> dt.date:
    return dt.date(qd.year(), qd.month(), qd.day())


def _month_span(year: int, month: int):
    """暦に並ぶ範囲。前後の月がはみ出して見えるぶんも含める。"""
    first = dt.date(year, month, 1)
    return first - dt.timedelta(days=7), first + dt.timedelta(days=31 + 14)


def day_heading(day: dt.date) -> str:
    """「2026年10月12日（月）」。"""
    return (planner.date_text(day, tr("%Y年%m月%d日"))
            + tr("（%s）") % tr(WEEKDAY_LABELS[day.weekday()]))


class CalendarWindow(QDialog):
    """祝日の入った暦と、選んだ日の予定。"""

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.today = dt.date.today()
        self._painted = []          # 色を付けた日。塗り直す前に戻す
        self.setWindowTitle(tr("カレンダー"))
        self.setMinimumSize(720, 470)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        if not self.almanac.holidays_available():
            warn = QLabel(tr("jpholiday が入っていないため、祝日を表示できません。"))
            warn.setStyleSheet("color: %s;" % theme.WARN)
            warn.setWordWrap(True)
            root.addWidget(warn)

        body = QHBoxLayout()
        body.setSpacing(16)

        left = QVBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        sunday_first(self.calendar)
        month_arrows(self.calendar)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self._paint_weekends()
        self.calendar.selectionChanged.connect(self._show_day)
        self.calendar.currentPageChanged.connect(lambda *_: self._paint_month())
        left.addWidget(self.calendar, 1)

        legend = QHBoxLayout()
        for text, color in ((tr("今日"), theme.ACCENT), (tr("日曜・祝日"), theme.WARN),
                            (tr("土曜"), theme.COOL)):
            mark = QLabel("■ " + text)
            mark.setStyleSheet("color: %s; font-size: 12px;" % color)
            legend.addWidget(mark)
        legend.addStretch(1)
        back = QPushButton(tr("今日へ"))
        back.setProperty("tone", "ghost")
        back.clicked.connect(self.go_today)
        legend.addWidget(back)
        left.addLayout(legend)
        body.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(6)
        self.day_title = QLabel("")
        self.day_title.setStyleSheet("font-size: 17px; font-weight: bold;")
        right.addWidget(self.day_title)
        self.day_holiday = QLabel("")
        self.day_holiday.setStyleSheet("color: %s; font-size: 14px;" % theme.WARN)
        right.addWidget(self.day_holiday)
        self.day_lists = QLabel("")
        self.day_lists.setWordWrap(True)
        self.day_lists.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        right.addWidget(self.day_lists)

        right.addWidget(self._caption(tr("この日のアラーム")))
        self.alarm_list = QListWidget()
        self.alarm_list.setFocusPolicy(Qt.NoFocus)
        self.alarm_list.setSelectionMode(QListWidget.NoSelection)
        right.addWidget(self.alarm_list, 3)

        self.month_caption = self._caption("")
        right.addWidget(self.month_caption)
        self.holiday_list = QListWidget()
        self.holiday_list.itemClicked.connect(self._jump_to_holiday)
        right.addWidget(self.holiday_list, 2)
        body.addLayout(right, 2)

        root.addLayout(body, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton(tr("閉じる"))
        close.setProperty("tone", "accent")
        close.clicked.connect(self.close)
        footer.addWidget(close)
        root.addLayout(footer)

        # 日付が変わったら「今日」の印を付け直す
        self.beat = QTimer(self)
        self.beat.setInterval(60 * 1000)
        self.beat.timeout.connect(self._watch_date)
        self.beat.start()

        self._paint_month()
        self._show_day()

    # ------------------------------------------------------------------
    @property
    def almanac(self):
        return self.vault.almanac          # 復元で器ごと差し替わるので、都度引く

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: %s; font-size: 12px; padding-top: 6px;"
                            % theme.TEXT_SUB)
        return label

    def selected(self) -> dt.date:
        return _to_date(self.calendar.selectedDate())

    def go_today(self) -> None:
        self.calendar.setSelectedDate(_to_qdate(dt.date.today()))

    def refresh(self) -> None:
        """アラームや日付リストが変わったときに描き直す。"""
        self._paint_month()
        self._show_day()

    # ---- 暦の色 -----------------------------------------------------------
    def _paint_weekends(self) -> None:
        for weekday, color in ((Qt.Sunday, theme.WARN), (Qt.Saturday, theme.COOL)):
            look = QTextCharFormat()
            look.setForeground(QBrush(QColor(color)))
            self.calendar.setWeekdayTextFormat(weekday, look)

    def _paint_month(self) -> None:
        for qd in self._painted:
            self.calendar.setDateTextFormat(qd, QTextCharFormat())
        self._painted = []

        year, month = self.calendar.yearShown(), self.calendar.monthShown()
        start, end = _month_span(year, month)
        for day, _name in self.almanac.holidays_between(start, end):
            look = QTextCharFormat()
            look.setForeground(QBrush(QColor(theme.WARN)))
            self._mark(day, look)

        # 選んだ日の地の色とぶつからないよう、今日は字の色と太さで示す
        today = dt.date.today()
        look = QTextCharFormat()
        look.setForeground(QBrush(QColor(theme.ACCENT)))
        look.setFontWeight(QFont.Bold)
        look.setFontUnderline(True)
        self._mark(today, look)

        self.month_caption.setText(tr("%d年%d月の祝日") % (year, month))
        self.holiday_list.clear()
        first = dt.date(year, month, 1)
        last = (first + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
        for day, name in self.almanac.holidays_between(first, last):
            stamp = "%d/%d" % (day.month, day.day)
            weekday = tr("（%s）") % tr(WEEKDAY_LABELS[day.weekday()])
            row = QListWidgetItem("%s%s  %s" % (stamp, weekday, name))
            row.setData(Qt.UserRole, day.isoformat())
            self.holiday_list.addItem(row)
        if not self.holiday_list.count():
            row = QListWidgetItem(tr("この月に祝日はありません"))
            row.setFlags(Qt.NoItemFlags)
            self.holiday_list.addItem(row)

    def _mark(self, day: dt.date, look: QTextCharFormat) -> None:
        qd = _to_qdate(day)
        self.calendar.setDateTextFormat(qd, look)
        self._painted.append(qd)

    # ---- 選んだ日 ---------------------------------------------------------
    def _show_day(self) -> None:
        day = self.selected()
        self.day_title.setText(day_heading(day))
        name = self.almanac.holiday_name(day)
        self.day_holiday.setText(name)
        self.day_holiday.setVisible(bool(name))

        lists = [self.almanac.list_label(key) for key in sorted(self.almanac.lists)
                 if day in self.almanac.lists[key].days]
        self.day_lists.setText(tr("日付リスト: %s") % tr("、").join(lists))
        self.day_lists.setVisible(bool(lists))

        self.alarm_list.clear()
        for moment, item, why in self.alarms_on(day):
            text = "%s  %s" % (moment.strftime("%H:%M"), item.display_title())
            row = QListWidgetItem(text + ("  — " + why if why else ""))
            if why:
                row.setForeground(QBrush(QColor(theme.TEXT_SUB)))
            self.alarm_list.addItem(row)
        if not self.alarm_list.count():
            if day < dt.date.today():
                note = tr("過ぎた日の予定は出しません")
            else:
                note = tr("鳴る予定のアラームはありません")
            row = QListWidgetItem(note)
            row.setForeground(QBrush(QColor(theme.TEXT_SUB)))
            self.alarm_list.addItem(row)

    def alarms_on(self, day: dt.date, now: dt.datetime | None = None) -> list:
        """(日時, アラーム, 鳴らないわけ) を時刻順に。鳴るものは わけ が空。"""
        found = []
        for item in self.vault.items:
            plan = planner.day_plan(item, day, self.almanac, now)
            if plan is not None:
                found.append((plan[0], item, plan[1]))
        found.sort(key=lambda entry: entry[0])
        return found

    def _jump_to_holiday(self, row: QListWidgetItem) -> None:
        stamp = row.data(Qt.UserRole)
        if stamp:
            self.calendar.setSelectedDate(_to_qdate(dt.date.fromisoformat(stamp)))

    def _watch_date(self) -> None:
        today = dt.date.today()
        if today != self.today:
            self.today = today
            self.refresh()

    def closeEvent(self, event):
        self.beat.stop()
        super().closeEvent(event)
