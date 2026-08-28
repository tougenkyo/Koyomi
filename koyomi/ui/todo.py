"""ToDo リストの画面。"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ..tasks import TodoItem, Weight, sort_key
from . import theme
from .widgets import Pill
from ..i18n import tr

WEIGHT_TINTS = {Weight.HIGH: "WARN", Weight.MID: "ACCENT", Weight.LOW: "TEXT_SUB"}


def weight_tint(weight: Weight) -> str:
    return getattr(theme, WEIGHT_TINTS.get(weight, "TEXT_SUB"))


class TodoRow(QWidget):
    """1 件ぶんの行。"""

    def __init__(self, item: TodoItem, window: "TodoWindow", parent=None):
        super().__init__(parent)
        self.item = item
        self.window = window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("TodoRow")
        self._paint()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        self.check = QCheckBox()
        self.check.setChecked(item.done)
        self.check.toggled.connect(self._on_check)
        lay.addWidget(self.check)

        column = QVBoxLayout()
        column.setSpacing(1)
        self.text = QLabel(item.text or tr("（無題）"))
        self.text.setWordWrap(True)
        column.addWidget(self.text)
        if item.note:
            note = QLabel(item.note)
            note.setWordWrap(True)
            note.setStyleSheet("font-size: 11px; color: %s;" % theme.TEXT_SUB)
            column.addWidget(note)
        lay.addLayout(column, 1)

        lay.addWidget(Pill(item.weight.label, weight_tint(item.weight)))

        due = item.due_text()
        if due:
            tint = theme.WARN if item.overdue() else theme.TEXT_SUB
            lay.addWidget(Pill(due, tint))

        edit = QPushButton(tr("編集"))
        edit.setProperty("tone", "ghost")
        edit.clicked.connect(lambda: self.window.edit(self.item))
        lay.addWidget(edit)

        drop = QPushButton(tr("削除"))
        drop.setProperty("tone", "ghost")
        drop.clicked.connect(lambda: self.window.remove(self.item))
        lay.addWidget(drop)

        self._restyle_text()

    def _paint(self) -> None:
        tint = theme.LINE if self.item.done else weight_tint(self.item.weight)
        self.setStyleSheet(
            "#TodoRow { background: %s; border: 1px solid %s;"
            " border-left: 4px solid %s; border-radius: 10px; }"
            % (theme.SLATE, theme.LINE, tint))

    def _restyle_text(self) -> None:
        if self.item.done:
            self.text.setStyleSheet(
                "font-size: 14px; color: %s; text-decoration: line-through;"
                % theme.TEXT_SUB)
        else:
            self.text.setStyleSheet("font-size: 14px; color: %s;" % theme.TEXT)

    def _on_check(self, state: bool) -> None:
        self.item.done = state
        self.window.after_change()


class TodoEditor(QDialog):
    """1 件の中身を書く小窓。"""

    def __init__(self, item: TodoItem, parent=None):
        super().__init__(parent)
        self.item = TodoItem.from_dict(item.to_dict())
        self.setWindowTitle(tr("やること"))
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        root.addWidget(QLabel(tr("やること")))
        self.text_field = QLineEdit(self.item.text)
        self.text_field.setPlaceholderText(tr("例: 電池を買う"))
        root.addWidget(self.text_field)

        root.addWidget(QLabel(tr("メモ")))
        self.note_field = QLineEdit(self.item.note)
        root.addWidget(self.note_field)

        row = QHBoxLayout()
        row.addWidget(QLabel(tr("優先度")))
        self.weight_box = QComboBox()
        for weight in Weight:
            self.weight_box.addItem(weight.label, weight.value)
        hit = self.weight_box.findData(self.item.weight.value)
        self.weight_box.setCurrentIndex(max(0, hit))
        row.addWidget(self.weight_box)
        row.addStretch(1)
        root.addLayout(row)

        due_row = QHBoxLayout()
        self.has_due = QCheckBox(tr("期限"))
        self.has_due.setChecked(bool(self.item.due))
        due_row.addWidget(self.has_due)
        self.due_field = QDateEdit(QDate.currentDate())
        self.due_field.setCalendarPopup(True)
        self.due_field.setDisplayFormat("yyyy/MM/dd")
        day = self.item.due_date()
        if day:
            self.due_field.setDate(QDate(day.year, day.month, day.day))
        self.due_field.setEnabled(self.has_due.isChecked())
        self.has_due.toggled.connect(self.due_field.setEnabled)
        due_row.addWidget(self.due_field, 1)
        root.addLayout(due_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton(tr("やめる"))
        cancel.setProperty("tone", "ghost")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton(tr("保存"))
        save.setProperty("tone", "accent")
        save.clicked.connect(self._commit)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _commit(self) -> None:
        self.item.text = self.text_field.text().strip()
        self.item.note = self.note_field.text().strip()
        try:
            self.item.weight = Weight(self.weight_box.currentData())
        except (ValueError, TypeError):
            self.item.weight = Weight.MID
        if self.has_due.isChecked():
            picked = self.due_field.date()
            self.item.due = dt.date(picked.year(), picked.month(),
                                    picked.day()).isoformat()
        else:
            self.item.due = ""
        self.accept()

    def result_item(self) -> TodoItem:
        return self.item


class TodoWindow(QDialog):
    """やることを並べる窓。"""

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.rows = []
        self.setWindowTitle(tr("やることリスト"))
        self.setMinimumSize(600, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        quick = QHBoxLayout()
        self.quick_field = QLineEdit()
        self.quick_field.setPlaceholderText(tr("やることを書いて Enter"))
        self.quick_field.returnPressed.connect(self._quick_add)
        quick.addWidget(self.quick_field, 1)
        self.quick_weight = QComboBox()
        for weight in Weight:
            self.quick_weight.addItem(weight.label, weight.value)
        self.quick_weight.setCurrentIndex(1)
        quick.addWidget(self.quick_weight)
        add = QPushButton(tr("追加"))
        add.setProperty("tone", "accent")
        add.clicked.connect(self._quick_add)
        quick.addWidget(add)
        detailed = QPushButton(tr("詳しく書く"))
        detailed.setProperty("tone", "ghost")
        detailed.clicked.connect(self._add_detailed)
        quick.addWidget(detailed)
        root.addLayout(quick)

        tools = QHBoxLayout()
        self.hide_done = QCheckBox(tr("済んだものを隠す"))
        self.hide_done.toggled.connect(lambda _: self.reload())
        tools.addWidget(self.hide_done)
        tools.addStretch(1)
        self.tally = QLabel("")
        self.tally.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        tools.addWidget(self.tally)
        purge = QPushButton(tr("済んだものを削除"))
        purge.setProperty("tone", "ghost")
        purge.clicked.connect(self._purge_done)
        tools.addWidget(purge)
        root.addLayout(tools)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        holder = QWidget()
        self.list_layout = QVBoxLayout(holder)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch(1)
        area.setWidget(holder)
        root.addWidget(area, 1)

        self.empty = QLabel(tr("まだ何もありません。上の欄から追加してください。"))
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color: %s; padding: 30px;" % theme.TEXT_SUB)
        self.list_layout.insertWidget(0, self.empty)

        self.reload()

    # ------------------------------------------------------------------
    def items(self) -> list:
        return self.vault.todos

    def reload(self) -> None:
        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows = []
        shown = sorted(self.items(), key=sort_key)
        if self.hide_done.isChecked():
            shown = [i for i in shown if not i.done]
        for index, item in enumerate(shown):
            row = TodoRow(item, self)
            self.list_layout.insertWidget(index + 1, row)
            self.rows.append(row)
        self.empty.setVisible(not shown)
        done = sum(1 for i in self.items() if i.done)
        late = sum(1 for i in self.items() if i.overdue())
        text = tr("全 %d 件 ／ 済 %d 件") % (len(self.items()), done)
        if late:
            text += tr(" ／ 期限切れ %d 件") % late
        self.tally.setText(text)

    def after_change(self) -> None:
        self.vault.save()
        self.reload()

    # ------------------------------------------------------------------
    def _quick_add(self) -> None:
        text = self.quick_field.text().strip()
        if not text:
            return
        item = TodoItem(text=text)
        try:
            item.weight = Weight(self.quick_weight.currentData())
        except (ValueError, TypeError):
            item.weight = Weight.MID
        self.items().append(item)
        self.quick_field.clear()
        self.after_change()

    def _add_detailed(self) -> None:
        dialog = TodoEditor(TodoItem(), self)
        if dialog.exec() == QDialog.Accepted:
            made = dialog.result_item()
            if made.text:
                self.items().append(made)
                self.after_change()

    def edit(self, item: TodoItem) -> None:
        dialog = TodoEditor(item, self)
        if dialog.exec() != QDialog.Accepted:
            return
        fresh = dialog.result_item()
        for index, existing in enumerate(self.items()):
            if existing.uid == item.uid:
                fresh.uid = item.uid
                fresh.done = existing.done
                self.items()[index] = fresh
                break
        self.after_change()

    def remove(self, item: TodoItem) -> None:
        self.vault.todos = [i for i in self.items() if i.uid != item.uid]
        self.after_change()

    def _purge_done(self) -> None:
        self.vault.todos = [i for i in self.items() if not i.done]
        self.after_change()

    def closeEvent(self, event):
        self.vault.save()
        super().closeEvent(event)
