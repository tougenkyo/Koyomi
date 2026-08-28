"""「鳴らさない日」などをためておく日付リストの編集画面。"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate
from PySide6.QtGui import QBrush, QColor, QTextCharFormat
from PySide6.QtWidgets import (QCalendarWidget, QComboBox, QDialog, QGroupBox,
                               QHBoxLayout, QInputDialog, QLabel, QListWidget,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout)

from . import theme
from ..i18n import tr


def _to_qdate(day: dt.date) -> QDate:
    return QDate(day.year, day.month, day.day)


def _to_date(qd: QDate) -> dt.date:
    return dt.date(qd.year(), qd.month(), qd.day())


class DateListDialog(QDialog):
    """8 本の日付リストを行き来しながら中身を編集する。"""

    def __init__(self, almanac, parent=None):
        super().__init__(parent)
        self.almanac = almanac
        self.setWindowTitle(tr("日付リストの管理"))
        self.setMinimumSize(720, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        picker = QHBoxLayout()
        self.list_box = QComboBox()
        for key in sorted(almanac.lists):
            self.list_box.addItem(almanac.list_label(key), key)
        self.list_box.currentIndexChanged.connect(self._reload)
        picker.addWidget(QLabel(tr("リスト")))
        picker.addWidget(self.list_box, 1)
        rename = QPushButton(tr("名前を変える"))
        rename.setProperty("tone", "ghost")
        rename.clicked.connect(self._rename)
        picker.addWidget(rename)
        root.addLayout(picker)

        body = QHBoxLayout()
        body.setSpacing(14)

        left = QVBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar.clicked.connect(self._toggle_day)
        self.calendar.currentPageChanged.connect(lambda *_: self._paint())
        left.addWidget(self.calendar)
        hint = QLabel(tr("日付をクリックすると登録／解除が切り替わります。"))
        hint.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        left.addWidget(hint)
        body.addLayout(left, 3)

        right = QVBoxLayout()
        right.addWidget(QLabel(tr("登録されている日")))
        self.day_list = QListWidget()
        right.addWidget(self.day_list, 1)

        tools = QGroupBox(tr("まとめて登録"))
        tl = QVBoxLayout(tools)

        holiday_row = QHBoxLayout()
        holiday_row.addWidget(QLabel(tr("祝日を")))
        self.year_from = QSpinBox()
        self.year_from.setRange(1955, 2099)
        self.year_from.setValue(dt.date.today().year)
        holiday_row.addWidget(self.year_from)
        holiday_row.addWidget(QLabel("〜"))
        self.year_to = QSpinBox()
        self.year_to.setRange(1955, 2099)
        self.year_to.setValue(dt.date.today().year + 1)
        holiday_row.addWidget(self.year_to)
        holiday_row.addWidget(QLabel(tr("年")))
        tl.addLayout(holiday_row)

        grab = QPushButton(tr("この期間の日本の祝日を取り込む"))
        grab.setProperty("tone", "accent")
        grab.clicked.connect(self._import_holidays)
        if not almanac.holidays_available():
            grab.setEnabled(False)
            grab.setText(tr("祝日の取り込みには jpholiday が必要です"))
        tl.addWidget(grab)

        weekday_row = QHBoxLayout()
        self.weekday_box = QComboBox()
        for idx, label in enumerate((tr("月"), tr("火"), tr("水"), tr("木"), tr("金"), tr("土"), tr("日"))):
            self.weekday_box.addItem(tr("%s曜日") % label, idx)
        weekday_row.addWidget(self.weekday_box)
        add_wd = QPushButton(tr("1年分を追加"))
        add_wd.clicked.connect(self._add_weekday_year)
        weekday_row.addWidget(add_wd)
        tl.addLayout(weekday_row)

        clear = QPushButton(tr("このリストを空にする"))
        clear.setProperty("tone", "danger")
        clear.clicked.connect(self._clear)
        tl.addWidget(clear)
        right.addWidget(tools)
        body.addLayout(right, 2)

        root.addLayout(body, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton(tr("閉じる"))
        close.setProperty("tone", "accent")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

        self._reload()

    # ------------------------------------------------------------------
    @property
    def key(self) -> str:
        return self.list_box.currentData()

    def _reload(self) -> None:
        self._paint()
        self.day_list.clear()
        for day in sorted(self.almanac.days_of(self.key)):
            note = self.almanac.holiday_name(day)
            text = day.strftime("%Y/%m/%d (%a)")
            if note:
                text += "  " + note
            self.day_list.addItem(text)

    def _paint(self) -> None:
        blank = QTextCharFormat()
        self.calendar.setDateTextFormat(QDate(), blank)
        marked = QTextCharFormat()
        marked.setBackground(QBrush(QColor(theme.ACCENT_DIM)))
        marked.setForeground(QBrush(QColor(theme.TEXT)))
        for day in self.almanac.days_of(self.key):
            self.calendar.setDateTextFormat(_to_qdate(day), marked)

    def _toggle_day(self, qd: QDate) -> None:
        self.almanac.toggle_day(self.key, _to_date(qd))
        self._reload()

    def _rename(self) -> None:
        current = self.almanac.lists[self.key].name
        name, ok = QInputDialog.getText(self, tr("リスト名"), tr("新しい名前"), text=current)
        if ok:
            self.almanac.rename_list(self.key, name)
            self.list_box.setItemText(self.list_box.currentIndex(),
                                      self.almanac.list_label(self.key))

    def _import_holidays(self) -> None:
        y1, y2 = self.year_from.value(), self.year_to.value()
        if y2 < y1:
            y1, y2 = y2, y1
        added = self.almanac.import_holidays(self.key, dt.date(y1, 1, 1),
                                             dt.date(y2, 12, 31))
        self._reload()
        QMessageBox.information(self, tr("取り込み"), tr("%d 件の祝日を追加しました。") % added)

    def _add_weekday_year(self) -> None:
        target = self.weekday_box.currentData()
        today = dt.date.today()
        days = []
        for offset in range(366):
            day = today + dt.timedelta(days=offset)
            if day.weekday() == target:
                days.append(day)
        added = self.almanac.add_days(self.key, days)
        self._reload()
        QMessageBox.information(self, tr("追加"), tr("%d 件を追加しました。") % added)

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self, tr("確認"), tr("「%s」の登録日をすべて消します。よろしいですか？")
            % self.almanac.list_label(self.key))
        if answer == QMessageBox.Yes:
            self.almanac.clear_list(self.key)
            self._reload()
