"""カレンダー。祝日に色を付けた月の暦と、選んだ日の予定を見る窓。

祝日は almanac（中身は jpholiday）から引く。日曜と祝日は赤、土曜は青。
右側には選んだ日の祝日名・日付リスト・その日に鳴るアラームと、
表示している月の祝日を並べる。

トレイの右クリックメニューには、小さな暦（MiniMonth）も埋め込む。
"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate, QEvent, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QTextCharFormat
from PySide6.QtWidgets import (QCalendarWidget, QDialog, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton,
                               QToolButton, QToolTip, QVBoxLayout, QWidget)

from .. import planner
from ..models import WEEKDAY_LABELS, WEEKDAY_ORDER
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
        self.pick(dt.date.today())

    def pick(self, day: dt.date) -> None:
        self.calendar.setSelectedDate(_to_qdate(day))

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


class MiniMonth(QWidget):
    """トレイの右クリックメニューに埋め込む、小さな月の暦。

    日曜と祝日は赤、土曜は青、今日はさし色の地で示す。祝日には
    名前の吹き出しが出て、下にその月の祝日を並べる。
    日付を押すと ``picked`` を出す（カレンダーの窓をその日で開く）。
    """

    picked = Signal(object)

    CELL_W = 30
    CELL_H = 22
    PAD = 8

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.setMouseTracking(True)
        self.today = dt.date.today()
        self.year, self.month = self.today.year, self.today.month
        self.names = {}             # 日付 → 祝日名（はみ出して見える日も含む）

        root = QVBoxLayout(self)
        root.setContentsMargins(self.PAD, self.PAD, self.PAD, 4)
        root.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(4)
        self.back = self._arrow("◀", -1)
        head.addWidget(self.back)
        self.title = QLabel("")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-weight: bold; background: transparent;")
        head.addWidget(self.title, 1)
        self.ahead = self._arrow("▶", 1)
        head.addWidget(self.ahead)
        root.addLayout(head)

        # 暦のマスは paintEvent で自分で描く。ここは場所取りだけ
        self.grid = QWidget()
        self.grid.setFixedSize(7 * self.CELL_W, 7 * self.CELL_H)
        self.grid.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.grid.setStyleSheet("background: transparent;")
        root.addWidget(self.grid, 0, Qt.AlignHCenter)

        self.holidays = QLabel("")
        self.holidays.setStyleSheet("color: %s; font-size: 11px; background: transparent;"
                                    % theme.TEXT_SUB)
        root.addWidget(self.holidays)
        self.reset()

    def _arrow(self, text: str, step: int) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.NoFocus)
        button.setStyleSheet("QToolButton { background: transparent; border: none;"
                             " color: %s; padding: 0 6px; }"
                             "QToolButton:hover { color: %s; }"
                             % (theme.TEXT_SUB, theme.ACCENT))
        button.clicked.connect(lambda: self.step(step))
        return button

    @property
    def almanac(self):
        return self.vault.almanac

    # ---- 月 ---------------------------------------------------------------
    def reset(self) -> None:
        """今日の月に戻す。メニューを開くたびに呼ぶ。"""
        self.today = dt.date.today()
        self.show_month(self.today.year, self.today.month)

    def step(self, months: int) -> None:
        index = self.year * 12 + (self.month - 1) + months
        self.show_month(index // 12, index % 12 + 1)

    def show_month(self, year: int, month: int) -> None:
        self.year, self.month = year, month
        self.title.setText(tr("%d年%d月") % (year, month))
        start, end = _month_span(year, month)
        self.names = dict(self.almanac.holidays_between(start, end))
        lines = []
        for day, name in sorted(self.names.items()):
            if (day.year, day.month) == (year, month):
                weekday = tr("（%s）") % tr(WEEKDAY_LABELS[day.weekday()])
                lines.append("%d/%d%s  %s" % (day.month, day.day, weekday, name))
        self.holidays.setText("\n".join(lines) or tr("この月に祝日はありません"))
        self.update()

    def first_cell(self) -> dt.date:
        """左上のマスの日付（1 日を含む週の日曜）。"""
        first = dt.date(self.year, self.month, 1)
        return first - dt.timedelta(days=(first.weekday() + 1) % 7)

    def day_at(self, point) -> dt.date | None:
        """この部品の上の位置にある日付。マスの外なら None。"""
        x = point.x() - self.grid.x()
        y = point.y() - self.grid.y()
        if x < 0 or y < 0:
            return None
        col, row = int(x // self.CELL_W), int(y // self.CELL_H) - 1   # 1 行目は曜日
        if not (0 <= col < 7 and 0 <= row < 6):
            return None
        return self.first_cell() + dt.timedelta(days=row * 7 + col)

    def color_of(self, day: dt.date) -> str:
        if (day.year, day.month) != (self.year, self.month):
            return theme.TEXT_SUB
        if day in self.names or day.weekday() == 6:
            return theme.WARN
        if day.weekday() == 5:
            return theme.COOL
        return theme.TEXT

    # ---- 描く -------------------------------------------------------------
    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.translate(self.grid.pos())
        small = QFont(self.font())
        small.setPointSizeF(max(7.0, small.pointSizeF() - 1))
        p.setFont(small)
        for col, weekday in enumerate(WEEKDAY_ORDER):
            p.setPen(QColor({6: theme.WARN, 5: theme.COOL}.get(weekday, theme.TEXT_SUB)))
            p.drawText(QRectF(col * self.CELL_W, 0, self.CELL_W, self.CELL_H),
                       Qt.AlignCenter, tr(WEEKDAY_LABELS[weekday]))
        p.setFont(self.font())
        day = self.first_cell()
        for index in range(42):
            col, row = index % 7, index // 7 + 1
            cell = QRectF(col * self.CELL_W, row * self.CELL_H, self.CELL_W, self.CELL_H)
            color = self.color_of(day)
            if day == self.today:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(theme.ACCENT))
                p.drawRoundedRect(cell.adjusted(2, 1, -2, -1), 5, 5)
                color = theme.ON_ACCENT
            p.setPen(QColor(color))
            p.drawText(cell, Qt.AlignCenter, str(day.day))
            day += dt.timedelta(days=1)
        p.end()

    # ---- 触る -------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        event.accept()          # メニューへ渡すと、押しただけで閉じてしまう

    def mouseReleaseEvent(self, event) -> None:
        day = self.day_at(event.position().toPoint())
        if day is not None and event.button() == Qt.LeftButton:
            self.picked.emit(day)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        day = self.day_at(event.position().toPoint())
        self.setCursor(Qt.PointingHandCursor if day else Qt.ArrowCursor)
        event.accept()

    def wheelEvent(self, event) -> None:
        self.step(-1 if event.angleDelta().y() > 0 else 1)
        event.accept()

    def event(self, event) -> bool:
        if event.type() == QEvent.ToolTip:
            day = self.day_at(event.pos())
            name = self.names.get(day) if day else None
            if name:
                QToolTip.showText(event.globalPos(), "%s\n%s" % (day_heading(day), name), self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)
