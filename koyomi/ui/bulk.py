"""選んだアラームへまとめて同じ設定を流し込むダイアログ。

左のチェックを入れた項目だけが対象へ書き込まれる。
チェックしていない項目は元の値のまま残る。
"""
from __future__ import annotations

from PySide6.QtCore import QTime, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QGridLayout, QGroupBox, QLabel, QListWidget,
                               QListWidgetItem, QSpinBox, QVBoxLayout,
                               QWidget)

from ..models import Guard, ToneKind, WakeItem, as_enum
from ..tonesmith import TONE_CATALOG
from . import theme
from .widgets import TimeSpinner
from ..i18n import tr


class BulkDialog(QDialog):
    """一括設定。"""

    def __init__(self, items: list, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.all_items = items
        self.setWindowTitle(tr("まとめて設定"))
        self.setMinimumSize(560, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(QLabel(tr("設定を変えるアラームを選んでください。")))
        self.picker = QListWidget()
        self.picker.setSelectionMode(QListWidget.NoSelection)
        for item in items:
            row = QListWidgetItem("%s  %s" % (item.clock_text, item.display_title()))
            row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
            row.setCheckState(Qt.Unchecked)
            row.setData(Qt.UserRole, item.uid)
            self.picker.addItem(row)
        root.addWidget(self.picker, 1)

        box = QGroupBox(tr("変更する項目"))
        grid = QGridLayout(box)
        grid.setVerticalSpacing(8)
        self.rows = {}

        def add_row(key: str, caption: str, widget: QWidget):
            flag = QCheckBox(caption)
            widget.setEnabled(False)
            flag.toggled.connect(widget.setEnabled)
            r = grid.rowCount()
            grid.addWidget(flag, r, 0)
            grid.addWidget(widget, r, 1)
            self.rows[key] = (flag, widget)

        time_field = TimeSpinner(QTime(7, 0, 0), "HH:mm:ss")
        add_row("time", tr("時刻"), time_field)

        group_box = QComboBox()
        for key, name in sorted(vault.groups.items()):
            group_box.addItem(name, key)
        add_row("group", tr("グループ"), group_box)

        state_box = QComboBox()
        state_box.addItem(tr("ON にする"), True)
        state_box.addItem(tr("OFF にする"), False)
        add_row("active", "ON / OFF", state_box)

        tone_box = QComboBox()
        for key, label in TONE_CATALOG.items():
            tone_box.addItem(tr(label), key)
        add_row("tone", tr("内蔵の音"), tone_box)

        volume_box = QSpinBox()
        volume_box.setRange(0, 100)
        volume_box.setSuffix(" %")
        volume_box.setValue(70)
        add_row("volume", tr("音量"), volume_box)

        guard_box = QComboBox()
        for style in Guard:
            guard_box.addItem(style.label, style)
        add_row("stop_guard", tr("止め方"), guard_box)

        snooze_box = QComboBox()
        snooze_box.addItem(tr("スヌーズを使う"), True)
        snooze_box.addItem(tr("スヌーズを使わない"), False)
        add_row("snooze_on", tr("スヌーズ"), snooze_box)

        interval_box = QSpinBox()
        interval_box.setRange(1, 1439)
        interval_box.setSuffix(tr(" 分"))
        interval_box.setValue(5)
        add_row("snooze_minutes", tr("スヌーズ間隔"), interval_box)

        autostop_box = QSpinBox()
        autostop_box.setRange(0, 120)
        autostop_box.setSuffix(tr(" 分"))
        autostop_box.setValue(5)
        add_row("auto_stop", tr("鳴り続ける時間"), autostop_box)

        holiday_box = QComboBox()
        holiday_box.addItem(tr("祝日は鳴らさない"), True)
        holiday_box.addItem(tr("祝日でも鳴らす"), False)
        add_row("holiday", tr("祝日"), holiday_box)

        lock_box = QComboBox()
        lock_box.addItem(tr("スイッチを固定する"), True)
        lock_box.addItem(tr("固定を解く"), False)
        add_row("lock", tr("ON/OFF の固定"), lock_box)

        root.addWidget(box)

        hint = QLabel(tr("チェックを入れた項目だけが上書きされます。"))
        hint.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        root.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Apply).setText(tr("適用"))
        buttons.button(QDialogButtonBox.Apply).setProperty("tone", "accent")
        buttons.button(QDialogButtonBox.Cancel).setText(tr("やめる"))
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    def chosen_uids(self) -> list:
        picked = []
        for row in range(self.picker.count()):
            entry = self.picker.item(row)
            if entry.checkState() == Qt.Checked:
                picked.append(entry.data(Qt.UserRole))
        return picked

    def apply_to(self, item: WakeItem) -> None:
        """チェックされた項目だけを 1 件へ書き込む。"""
        def on(key: str) -> bool:
            return self.rows[key][0].isChecked()

        if on("time"):
            picked = self.rows["time"][1].time()
            item.hour, item.minute = picked.hour(), picked.minute()
            item.second = picked.second()
        if on("group"):
            item.group = self.rows["group"][1].currentData()
        if on("active"):
            item.active = self.rows["active"][1].currentData()
        if on("tone"):
            item.sound.kind = ToneKind.BUILTIN
            item.sound.source = self.rows["tone"][1].currentData()
        if on("volume"):
            item.sound.volume = self.rows["volume"][1].value()
        if on("stop_guard"):
            item.stop_guard.style = as_enum(
                Guard, self.rows["stop_guard"][1].currentData())
        if on("snooze_on"):
            item.snooze.enabled = self.rows["snooze_on"][1].currentData()
        if on("snooze_minutes"):
            item.snooze.minutes = self.rows["snooze_minutes"][1].value()
        if on("auto_stop"):
            item.auto_stop_minutes = self.rows["auto_stop"][1].value()
        if on("holiday"):
            item.dodge_holidays = self.rows["holiday"][1].currentData()
        if on("lock"):
            item.toggle_locked = self.rows["lock"][1].currentData()
