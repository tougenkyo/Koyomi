"""一覧画面。アプリの入口。"""
from __future__ import annotations

import datetime as dt
import os
import sys

from PySide6.QtCore import QTime, Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QMainWindow,
                               QMenu, QMessageBox, QPushButton, QScrollArea,
                               QSystemTrayIcon, QTimeEdit, QVBoxLayout, QWidget)

from .. import APP_TITLE, actions, i18n, planner, power
from ..director import RingDirector
from ..models import (QUICK_ACTIONS, WEEKDAY_LABELS, Cycle, ListOrder,
                      WakeItem, as_enum)
from ..player import SoundEngine
from ..tonesmith import ensure_icon
from . import theme
from .bulk import BulkDialog
from .datelists import DateListDialog
from .editor import AlarmEditor
from .floatbar import FloatBar
from .ring_window import RingWindow
from .settings import SettingsDialog
from .timers import TimerWindow
from .todo import TodoWindow
from .widgets import Pill, ToggleSwitch
from .worldclock import WorldClockWindow
from ..i18n import tr


# --------------------------------------------------------------------------
class AlarmRow(QWidget):
    """一覧に並ぶ 1 行。"""

    def __init__(self, item: WakeItem, window: "MainWindow", parent=None):
        super().__init__(parent)
        self.item = item
        self.window = window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("AlarmRow")
        self._paint_frame()
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(14)

        self.toggle = ToggleSwitch(item.active)
        self.toggle.setLocked(item.toggle_locked)
        self.toggle.toggled.connect(self._on_toggle)
        self.toggle.blocked.connect(self._on_blocked)
        lay.addWidget(self.toggle, 0, Qt.AlignVCenter)

        clock_col = QVBoxLayout()
        clock_col.setSpacing(0)
        self.clock = QLabel(item.clock_text)
        self.clock.setStyleSheet("font-size: 30px; font-weight: bold;")
        clock_col.addWidget(self.clock)
        lay.addLayout(clock_col)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.title = QLabel(item.display_title())
        align = Qt.AlignLeft if window.vault.prefs.left_align_titles else Qt.AlignLeft
        self.title.setAlignment(align | Qt.AlignVCenter)
        self.title.setStyleSheet("font-size: 14px;")
        text_col.addWidget(self.title)

        self.detail = QLabel()
        self.detail.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        text_col.addWidget(self.detail)
        lay.addLayout(text_col, 1)

        self.pills = QHBoxLayout()
        self.pills.setSpacing(5)
        lay.addLayout(self.pills)

        self.countdown = QLabel()
        self.countdown.setMinimumWidth(110)
        self.countdown.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.countdown.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        lay.addWidget(self.countdown)

        self.refresh()

    def _paint_frame(self) -> None:
        tint = theme.group_tint(self.item.group)
        alive = self.item.active
        self.setStyleSheet(
            "#AlarmRow { background: %s; border: 1px solid %s;"
            " border-left: 4px solid %s; border-radius: 10px; }"
            "#AlarmRow:hover { background: %s; }"
            % (theme.SLATE, theme.LINE,
               tint if alive else theme.LINE, theme.SLATE_HI))

    def _clear_pills(self) -> None:
        while self.pills.count():
            entry = self.pills.takeAt(0)
            widget = entry.widget()
            if widget:
                widget.deleteLater()

    def refresh(self) -> None:
        item = self.item
        self.clock.setText(item.clock_text)
        self.clock.setStyleSheet(
            "font-size: 30px; font-weight: bold; color: %s;"
            % (theme.TEXT if item.active else "#606a7a"))
        self.title.setText(item.display_title())
        self.title.setStyleSheet(
            "font-size: 14px; color: %s;"
            % (theme.TEXT if item.active else "#707a8a"))
        self.detail.setText(planner.repeat_digest(item, self.window.vault.almanac))
        self.toggle.setChecked(item.active, animate=False)
        self.toggle.setLocked(item.toggle_locked)
        self._paint_frame()

        self._clear_pills()
        self.pills.addWidget(Pill(self.window.vault.group_name(item.group),
                                  theme.group_tint(item.group)))
        if item.toggle_locked:
            self.pills.addWidget(Pill(tr("固定"), theme.TEXT_SUB))
        if item.skip_once:
            self.pills.addWidget(Pill(tr("次は飛ばす"), theme.WARN))
        if self.window.director.is_snoozing(item.uid):
            state = self.window.director.snooze_state(item.uid)
            self.pills.addWidget(Pill(tr("スヌーズ %d回目") % state.rounds, theme.COOL))
        self.refresh_countdown()

    def refresh_countdown(self) -> None:
        item = self.item
        if not item.active:
            self.countdown.setText("OFF")
            return
        state = self.window.director.snooze_state(item.uid)
        if state:
            self.countdown.setText(tr("%s に再通知") % state.due_at.strftime("%H:%M"))
            return
        when = planner.next_time(item, self.window.vault.almanac)
        if when is None:
            self.countdown.setText(tr("予定なし"))
            return
        self.countdown.setText("%s\n%s" % (when.strftime("%m/%d %H:%M"),
                                           planner.humanize_gap(when)))

    # ---- 操作 -------------------------------------------------------------
    def _on_toggle(self, state: bool) -> None:
        self.item.active = state
        self.window.after_change()

    def _on_blocked(self) -> None:
        self.window.flash_status(tr("このアラームはスイッチが固定されています。"
                                 "右クリックから解除できます。"))

    def mouseDoubleClickEvent(self, _event):
        self.window.edit_item(self.item)

    def _menu(self, point) -> None:
        menu = QMenu(self)
        menu.addAction(tr("編集"), lambda: self.window.edit_item(self.item))
        menu.addAction(tr("複製"), lambda: self.window.duplicate_item(self.item))
        menu.addSeparator()
        if planner.can_skip(self.item):
            caption = tr("次の1回を飛ばすのをやめる") if self.item.skip_once else tr("次の1回だけ飛ばす")
            menu.addAction(caption, lambda: self.window.toggle_skip(self.item))
        lock_caption = tr("スイッチの固定を解く") if self.item.toggle_locked else tr("スイッチを固定する")
        menu.addAction(lock_caption, lambda: self.window.toggle_lock(self.item))
        if self.window.director.is_snoozing(self.item.uid):
            menu.addSeparator()
            menu.addAction(tr("スヌーズを解除"), lambda: self.window.cancel_snooze(self.item))
            menu.addAction(tr("スヌーズ間隔を変える"),
                           lambda: self.window.change_snooze(self.item))
        menu.addSeparator()
        menu.addAction(tr("いま鳴らしてみる"), lambda: self.window.preview_ring(self.item))
        menu.addSeparator()
        menu.addAction(tr("削除"), lambda: self.window.delete_item(self.item))
        menu.exec(self.mapToGlobal(point))


# --------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """アラーム一覧を出す親ウィンドウ。"""

    def __init__(self, vault, engine: SoundEngine):
        super().__init__()
        self.vault = vault
        self.engine = engine
        self.rows = []
        self.ring_windows = {}
        self.timer_window = None
        self.world_window = None
        self.todo_window = None
        self.float_bar = None
        self.wake_clock = power.WakeClock()
        self._sleep_done_for = ""
        self._quitting = False
        self._torn_down = False

        self.director = RingDirector(vault, self)
        self.director.due.connect(self._on_due)
        self.director.tick.connect(self._on_tick)

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(760, 620)
        self.setWindowIcon(QIcon(ensure_icon()))

        self._build()
        self._build_tray()
        self.reload()
        self.director.start()
        if self.vault.prefs.float_bar:
            QTimer.singleShot(200, self.show_float_bar)
        QTimer.singleShot(400, self._report_missed)
        QTimer.singleShot(600, self._review_pending_actions)

    # ------------------------------------------------------------------
    # 画面の組み立て
    # ------------------------------------------------------------------
    def _build(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        head = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(0)
        self.big_clock = QLabel()
        self.big_clock.setStyleSheet("font-size: 34px; font-weight: bold;")
        left.addWidget(self.big_clock)
        self.today_label = QLabel()
        self.today_label.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        left.addWidget(self.today_label)
        head.addLayout(left)
        head.addStretch(1)

        right = QVBoxLayout()
        right.setSpacing(0)
        cap = QLabel(tr("次のアラーム"))
        cap.setAlignment(Qt.AlignRight)
        cap.setStyleSheet("color: %s; font-size: 11px;" % theme.TEXT_SUB)
        right.addWidget(cap)
        self.next_label = QLabel("—")
        self.next_label.setAlignment(Qt.AlignRight)
        self.next_label.setStyleSheet("font-size: 17px; color: %s;" % theme.ACCENT)
        right.addWidget(self.next_label)
        head.addLayout(right)
        root.addLayout(head)

        tools = QHBoxLayout()
        add = QPushButton(tr("＋ 追加"))
        add.setProperty("tone", "accent")
        add.clicked.connect(self.add_item)
        tools.addWidget(add)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText(tr("アラーム名やグループ名で絞り込む"))
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(lambda _: self.reload())
        tools.addWidget(self.search_field, 1)

        self.group_btn = QPushButton(tr("グループ"))
        self.group_btn.clicked.connect(self._group_menu)
        tools.addWidget(self.group_btn)

        self.order_box = QComboBox()
        for order in ListOrder:
            self.order_box.addItem(order.label, order)
        self.order_box.setCurrentIndex(list(ListOrder).index(self.vault.prefs.order))
        self.order_box.currentIndexChanged.connect(self._change_order)
        tools.addWidget(self.order_box)

        more = QPushButton(tr("メニュー"))
        more.clicked.connect(self._more_menu)
        tools.addWidget(more)
        root.addLayout(tools)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        holder = QWidget()
        self.list_layout = QVBoxLayout(holder)
        self.list_layout.setSpacing(8)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.addStretch(1)
        area.setWidget(holder)
        root.addWidget(area, 1)

        self.empty_note = QLabel(tr("まだアラームがありません。「＋ 追加」から作ってください。"))
        self.empty_note.setAlignment(Qt.AlignCenter)
        self.empty_note.setStyleSheet("color: %s; padding: 40px;" % theme.TEXT_SUB)
        self.list_layout.insertWidget(0, self.empty_note)

        self.quick_bar = QWidget()
        self.quick_layout = QHBoxLayout(self.quick_bar)
        self.quick_layout.setContentsMargins(0, 0, 0, 0)
        self.quick_layout.setSpacing(8)
        root.addWidget(self.quick_bar)
        self._build_quick_bar()

        self.status = QLabel("")
        self.status.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        root.addWidget(self.status)

    def _build_quick_bar(self) -> None:
        while self.quick_layout.count():
            entry = self.quick_layout.takeAt(0)
            widget = entry.widget()
            if widget:
                widget.deleteLater()
        handlers = {
            "add": self.add_item,
            "all_on": lambda: self.set_all(True),
            "all_off": lambda: self.set_all(False),
            "purge_off": self.purge_inactive,
            "timers": self.open_timers,
            "search": lambda: self.search_field.setFocus(),
        }
        for key in self.vault.prefs.quick_actions:
            btn = QPushButton(tr(QUICK_ACTIONS.get(key, key)))
            btn.setMinimumHeight(38)
            btn.clicked.connect(handlers.get(key, lambda: None))
            self.quick_layout.addWidget(btn)
        self.quick_bar.setVisible(self.vault.prefs.show_quick_bar)

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon(ensure_icon()), self)
        menu = QMenu()
        show = QAction(tr("ウィンドウを開く"), self)
        show.triggered.connect(self._restore_window)
        menu.addAction(show)
        menu.addSeparator()
        off = QAction(tr("すべて OFF"), self)
        off.triggered.connect(lambda: self.set_all(False))
        menu.addAction(off)
        menu.addSeparator()
        quit_action = QAction(tr("終了"), self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self._restore_window()
            if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    # ------------------------------------------------------------------
    # 一覧の更新
    # ------------------------------------------------------------------
    def visible_items(self) -> list:
        needle = self.search_field.text().strip().lower()
        picked = []
        for item in self.vault.items:
            if self.vault.prefs.group_filter and item.group not in self.vault.prefs.group_filter:
                continue
            if needle:
                hay = (item.display_title() + " "
                       + self.vault.group_name(item.group)).lower()
                if needle not in hay:
                    continue
            picked.append(item)
        return self._sorted(picked)

    def _sorted(self, items: list) -> list:
        order = self.vault.prefs.order
        almanac = self.vault.almanac

        def clock_key(i):
            return (i.hour, i.minute)

        def next_key(i):
            when = planner.next_time(i, almanac) if i.active else None
            return when or dt.datetime.max

        if order == ListOrder.TIME:
            return sorted(items, key=clock_key)
        if order == ListOrder.NAME:
            return sorted(items, key=lambda i: (i.display_title(), clock_key(i)))
        if order == ListOrder.GROUP:
            return sorted(items, key=lambda i: (i.group, clock_key(i)))
        if order == ListOrder.ACTIVE_FIRST:
            return sorted(items, key=lambda i: (not i.active, clock_key(i)))
        return sorted(items, key=lambda i: (not i.active, next_key(i)))

    def reload(self) -> None:
        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows = []
        items = self.visible_items()
        for index, item in enumerate(items):
            row = AlarmRow(item, self)
            self.list_layout.insertWidget(index + 1, row)
            self.rows.append(row)
        self.empty_note.setVisible(not items)
        if not items and self.vault.items:
            self.empty_note.setText(tr("条件に合うアラームがありません。"))
        elif not items:
            self.empty_note.setText(tr("まだアラームがありません。「＋ 追加」から作ってください。"))
        self._refresh_group_button()
        self._refresh_header()

    def after_change(self) -> None:
        """変更を保存してから一覧を描き直す。

        保存でつまずいても一覧の更新までは必ず行う。ここで例外が抜けると
        画面が古いまま残り、操作が効かなかったように見えてしまうため。
        """
        trouble = ""
        try:
            self.vault.save()
        except Exception as err:                      # noqa: BLE001 - 保存失敗は握って通知
            trouble = tr("設定を保存できませんでした: %s") % err
        self.reload()
        if trouble:
            self.flash_status(trouble)

    def repaint_theme(self) -> None:
        """配色を変えたあと、開いている画面へ行き渡らせる。"""
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(theme.stylesheet())
        self.setWindowIcon(QIcon(ensure_icon()))
        self.next_label.setStyleSheet("font-size: 17px; color: %s;" % theme.ACCENT)
        self.today_label.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        self.status.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        self.empty_note.setStyleSheet(
            "color: %s; padding: 40px;" % theme.TEXT_SUB)
        self.reload()
        if self.float_bar is not None:
            self.float_bar.update()

    def _refresh_group_button(self) -> None:
        picked = self.vault.prefs.group_filter
        if not picked:
            self.group_btn.setText(tr("グループ: すべて"))
        elif len(picked) == 1:
            self.group_btn.setText(tr("グループ: %s") % self.vault.group_name(picked[0]))
        else:
            self.group_btn.setText(tr("グループ: %d件") % len(picked))

    def _refresh_header(self) -> None:
        now = dt.datetime.now()
        self.big_clock.setText(now.strftime("%H:%M:%S"))
        weekday = tr(WEEKDAY_LABELS[now.weekday()])
        holiday = self.vault.almanac.holiday_name(now.date())
        text = now.strftime(tr("%Y年%m月%d日")) + tr("（%s）") % weekday
        if holiday:
            text += "　%s" % holiday
        self.today_label.setText(text)

        soonest, owner = self.next_ring()
        if soonest is None:
            self.next_label.setText(tr("予定なし"))
            tip = tr("%s ｜ 予定なし") % APP_TITLE
        else:
            self.next_label.setText("%s  %s" % (soonest.strftime("%m/%d %H:%M"),
                                                owner.display_title()))
            tip = tr("%s ｜ 次は %s（%s）") % (APP_TITLE, soonest.strftime("%m/%d %H:%M"),
                                          owner.display_title())
        if self.vault.prefs.tray_next_alarm:
            self.tray.setToolTip(tip)
        else:
            self.tray.setToolTip(APP_TITLE)
        self._arm_wake_clock(soonest)

    def next_ring(self) -> tuple:
        """次に鳴る (日時, アラーム)。何も無ければ (None, None)。"""
        soonest = None
        owner = None
        for item in self.vault.items:
            if not item.active:
                continue
            state = self.director.snooze_state(item.uid)
            when = state.due_at if state else planner.next_time(item, self.vault.almanac)
            if when and (soonest is None or when < soonest):
                soonest, owner = when, item
        return soonest, owner

    def running_timers(self) -> list:
        """走っているカウントダウン。フローティング表示が使う。"""
        if self.timer_window is None:
            return []
        return [r for r in self.timer_window.rows if r.running]

    # ---- 電源まわり -------------------------------------------------------
    def _arm_wake_clock(self, when) -> None:
        """次のアラームに合わせて、PC を起こす予約を入れ直す。"""
        if not self.vault.prefs.wake_pc or not self.wake_clock.supported():
            self.wake_clock.disarm()
            return
        if when is None:
            self.wake_clock.disarm()
            return
        self.wake_clock.arm(when)

    def _maybe_auto_sleep(self) -> None:
        """決めた時刻になったら PC をスリープさせる。"""
        prefs = self.vault.prefs
        if not prefs.auto_sleep or not power.IS_WINDOWS:
            return
        if self.ring_windows or self.director._snoozes:
            return
        now = dt.datetime.now()
        stamp = now.strftime("%Y-%m-%d ") + prefs.auto_sleep_at
        if self._sleep_done_for == stamp:
            return
        try:
            hour, minute = (int(x) for x in prefs.auto_sleep_at.split(":"))
        except ValueError:
            return
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if not (0 <= (now - due).total_seconds() <= 90):
            return
        self._sleep_done_for = stamp
        self.flash_status(tr("設定時刻になったので PC をスリープさせます。"))
        self.vault.save()
        QTimer.singleShot(1500, power.sleep_now)

    def _on_tick(self) -> None:
        self._refresh_header()
        for row in self.rows:
            row.refresh_countdown()
        self._maybe_auto_sleep()

    def flash_status(self, text: str) -> None:
        self.status.setText(text)
        QTimer.singleShot(6000, lambda: self.status.setText("")
                          if self.status.text() == text else None)

    # ------------------------------------------------------------------
    # アラームの編集
    # ------------------------------------------------------------------
    def add_item(self) -> None:
        item = self.vault.prefs.new_item()
        dialog = AlarmEditor(item, self.vault, self.engine, self, tr("アラームを追加"))
        if dialog.exec() == QDialog.Accepted:
            self.vault.add(dialog.result_item())
            self.after_change()
            self.flash_status(tr("アラームを追加しました。"))

    def edit_item(self, item: WakeItem) -> None:
        dialog = AlarmEditor(item, self.vault, self.engine, self)
        if dialog.exec() == QDialog.Accepted:
            self.vault.replace(dialog.result_item())
            self.after_change()

    def duplicate_item(self, item: WakeItem) -> None:
        self.vault.add(item.copy_as_new())
        self.after_change()
        self.flash_status(tr("複製しました。"))

    def delete_item(self, item: WakeItem) -> None:
        answer = QMessageBox.question(
            self, tr("削除"), tr("「%s」を削除します。よろしいですか？") % item.display_title())
        if answer != QMessageBox.Yes:
            return
        self.director.cancel_snooze(item.uid)
        self.vault.remove(item.uid)
        self.after_change()

    def toggle_skip(self, item: WakeItem) -> None:
        if not planner.can_skip(item):
            self.flash_status(tr("繰り返しのないアラームは飛ばせません。"))
            return
        item.skip_once = not item.skip_once
        self.after_change()

    def toggle_lock(self, item: WakeItem) -> None:
        item.toggle_locked = not item.toggle_locked
        self.after_change()

    def cancel_snooze(self, item: WakeItem) -> None:
        self.director.cancel_snooze(item.uid)
        self.after_change()
        self.flash_status(tr("スヌーズを解除しました。"))

    def change_snooze(self, item: WakeItem) -> None:
        state = self.director.snooze_state(item.uid)
        if not state:
            return
        value, ok = QInputDialog.getInt(self, tr("スヌーズ間隔"), tr("何分後にしますか"),
                                        state.minutes, 1, 1439)
        if ok:
            self.director.change_snooze_interval(item.uid, value)
            self.reload()

    def preview_ring(self, item: WakeItem) -> None:
        self._open_ring(item, round_no=0, preview=True)

    # ------------------------------------------------------------------
    # まとめて操作
    # ------------------------------------------------------------------
    def set_all(self, state: bool, respect_lock: bool = False) -> None:
        changed = 0
        for item in self.vault.items:
            if respect_lock and item.toggle_locked:
                continue
            if item.active != state:
                item.active = state
                changed += 1
        self.after_change()
        self.flash_status(tr("%d件を%sにしました。") % (changed, "ON" if state else "OFF"))

    def set_group(self, key: str, state: bool) -> None:
        changed = 0
        for item in self.vault.items:
            if item.group == key and item.active != state:
                item.active = state
                changed += 1
        self.after_change()
        self.flash_status(tr("%s の %d件を%sにしました。")
                          % (self.vault.group_name(key), changed,
                             "ON" if state else "OFF"))

    def purge_inactive(self) -> None:
        targets = [i for i in self.vault.items if not i.active]
        if not targets:
            self.flash_status(tr("OFF のアラームはありません。"))
            return
        answer = QMessageBox.question(
            self, tr("削除"), tr("OFF になっている %d件を削除します。よろしいですか？") % len(targets))
        if answer != QMessageBox.Yes:
            return
        for item in targets:
            self.vault.remove(item.uid)
        self.after_change()

    def quiet_until(self) -> None:
        """今日の指定時刻までに鳴る予定のものを止める。"""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("この時刻までを止める"))
        lay = QVBoxLayout(dialog)
        lay.addWidget(QLabel(tr("今日のこの時刻までに鳴る予定のアラームを止めます。\n"
                             "繰り返しのあるものは「次の1回だけ飛ばす」になります。")))
        field = QTimeEdit(QTime.currentTime().addSecs(3600))
        field.setDisplayFormat("HH:mm")
        field.setWrapping(True)
        lay.addWidget(field)
        go = QPushButton(tr("実行"))
        go.setProperty("tone", "accent")
        go.clicked.connect(dialog.accept)
        lay.addWidget(go)
        if dialog.exec() != QDialog.Accepted:
            return

        picked = field.time()
        limit = dt.datetime.combine(dt.date.today(), dt.time(picked.hour(), picked.minute()))
        touched = 0
        for item in self.vault.items:
            if not item.active:
                continue
            when = planner.next_time(item, self.vault.almanac)
            if not when or when > limit:
                continue
            if item.repeat.cycle in (Cycle.SINGLE, Cycle.ON_DATE):
                item.active = False
            else:
                item.skip_once = True
            touched += 1
        self.after_change()
        self.flash_status(tr("%d件を止めました。") % touched)

    def open_bulk(self) -> None:
        if not self.vault.items:
            self.flash_status(tr("アラームがありません。"))
            return
        dialog = BulkDialog(self.vault.items, self.vault, self)
        if dialog.exec() != QDialog.Accepted:
            return
        uids = dialog.chosen_uids()
        if not uids:
            self.flash_status(tr("アラームが選ばれていません。"))
            return
        for uid in uids:
            item = self.vault.find(uid)
            if item:
                dialog.apply_to(item)
        self.after_change()
        self.flash_status(tr("%d件に反映しました。") % len(uids))

    # ------------------------------------------------------------------
    # メニュー
    # ------------------------------------------------------------------
    def _group_menu(self) -> None:
        menu = QMenu(self)
        show_all = menu.addAction(tr("すべて表示"))
        show_all.setCheckable(True)
        show_all.setChecked(not self.vault.prefs.group_filter)
        show_all.triggered.connect(lambda: self._set_group_filter([]))
        menu.addSeparator()
        for key, name in sorted(self.vault.groups.items()):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(key in self.vault.prefs.group_filter)
            action.triggered.connect(lambda _=False, k=key: self._flip_group_filter(k))
        menu.addSeparator()
        for key, name in sorted(self.vault.groups.items()):
            sub = menu.addMenu(name + tr(" をまとめて"))
            sub.addAction(tr("ON にする"), lambda _=False, k=key: self.set_group(k, True))
            sub.addAction(tr("OFF にする"), lambda _=False, k=key: self.set_group(k, False))
        menu.exec(self.group_btn.mapToGlobal(self.group_btn.rect().bottomLeft()))

    def _set_group_filter(self, keys: list) -> None:
        self.vault.prefs.group_filter = list(keys)
        self.after_change()

    def _flip_group_filter(self, key: str) -> None:
        picked = list(self.vault.prefs.group_filter)
        if key in picked:
            picked.remove(key)
        else:
            picked.append(key)
        self._set_group_filter(picked)

    def _change_order(self) -> None:
        self.vault.prefs.order = as_enum(ListOrder, self.order_box.currentData())
        self.after_change()

    def _more_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction(tr("すべて ON"), lambda: self.set_all(True))
        menu.addAction(tr("すべて OFF"), lambda: self.set_all(False))
        menu.addAction(tr("固定していないものだけ OFF"),
                       lambda: self.set_all(False, respect_lock=True))
        menu.addAction(tr("この時刻までを止める…"), self.quiet_until)
        menu.addSeparator()
        menu.addAction(tr("まとめて設定…"), self.open_bulk)
        menu.addAction(tr("OFF のアラームを削除"), self.purge_inactive)
        menu.addSeparator()
        menu.addAction(tr("日付リストの管理…"), self.open_date_lists)
        menu.addAction(tr("タイマー・ストップウォッチ…"), self.open_timers)
        menu.addAction(tr("世界時計…"), self.open_world_clock)
        menu.addAction(tr("やることリスト…"), self.open_todo)
        menu.addSeparator()
        caption = (tr("フローティング表示をしまう") if self.float_bar
                   else tr("フローティング表示を出す"))
        menu.addAction(caption, self.toggle_float_bar)
        menu.addSeparator()
        menu.addAction(tr("設定…"), self.open_settings)
        menu.addAction(tr("このアプリについて"), self.show_about)
        menu.addSeparator()
        menu.addAction(tr("終了"), self.quit_app)
        menu.exec(self.cursor().pos())

    def open_date_lists(self) -> None:
        DateListDialog(self.vault.almanac, self).exec()
        self.after_change()

    def open_timers(self) -> None:
        if self.timer_window is None:
            self.timer_window = TimerWindow(self.vault, self.engine, self)
            self.timer_window.finished.connect(self._forget_timers)
        self.timer_window.show()
        self.timer_window.raise_()
        self.timer_window.activateWindow()

    def _forget_timers(self, *_args) -> None:
        self.vault.save()
        self.timer_window = None

    def open_world_clock(self) -> None:
        if self.world_window is None:
            self.world_window = WorldClockWindow(self.vault, self)
            self.world_window.finished.connect(self._forget_world)
        self.world_window.show()
        self.world_window.raise_()
        self.world_window.activateWindow()

    def _forget_world(self, *_args) -> None:
        self.vault.save()
        self.world_window = None

    def open_todo(self) -> None:
        if self.todo_window is None:
            self.todo_window = TodoWindow(self.vault, self)
            self.todo_window.finished.connect(self._forget_todo)
        self.todo_window.show()
        self.todo_window.raise_()
        self.todo_window.activateWindow()

    def _forget_todo(self, *_args) -> None:
        self.vault.save()
        self.todo_window = None

    # ---- フローティング表示 -----------------------------------------------
    def show_float_bar(self) -> None:
        if self.float_bar is None:
            self.float_bar = FloatBar(self)
            self.float_bar.opened.connect(self._restore_window)
            self.float_bar.closed.connect(self.hide_float_bar)
        self.float_bar.show()
        self.vault.prefs.float_bar = True

    def hide_float_bar(self) -> None:
        if self.float_bar is not None:
            self.float_bar.hide()
        self.vault.prefs.float_bar = False
        self.vault.save()

    def toggle_float_bar(self) -> None:
        if self.float_bar is not None and self.float_bar.isVisible():
            self.hide_float_bar()
        else:
            self.show_float_bar()
            self.vault.save()

    # ---- 連動動作の承認 ---------------------------------------------------
    def _review_pending_actions(self) -> None:
        """外から来たアラームの起動指定を、本人に見せて判断してもらう。"""
        waiting = [self.vault.find(uid) for uid in self.vault.pending_actions]
        waiting = [i for i in waiting if i is not None]
        if not waiting:
            self.vault.pending_actions = []
            return
        lines = [tr("読み込んだアラームに、アプリやページを開く指定が含まれています。"),
                 tr("身に覚えのないものは「使わない」を選んでください。"), ""]
        for item in waiting[:10]:
            lines.append("・%s … %s" % (item.display_title(), item.launch.summary()))
        if len(waiting) > 10:
            lines.append(tr("ほか %d件") % (len(waiting) - 10))
        answer = QMessageBox.question(
            self, tr("連動動作の確認"), "\n".join(lines),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        self.vault.approve_actions(answer == QMessageBox.Yes)
        self.after_change()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.vault, self.engine, self)
        if dialog.exec() == QDialog.Accepted:
            theme.apply(self.vault.prefs.theme)
            i18n.set_language(self.vault.prefs.language)
            if self.vault.prefs.float_bar:
                self.show_float_bar()
            elif self.float_bar is not None:
                self.float_bar.hide()
            self.repaint_theme()
            self.order_box.blockSignals(True)
            self.order_box.setCurrentIndex(
                list(ListOrder).index(self.vault.prefs.order))
            self.order_box.blockSignals(False)
            self._build_quick_bar()
            self.after_change()

    def show_about(self) -> None:
        from .. import APP_VERSION
        from ..almanac import HOLIDAY_LIB_READY
        from ..vault import data_dir
        lines = [
            "%s %s" % (APP_TITLE, APP_VERSION),
            "",
            tr("デスクトップ向けの目覚ましアプリです。"),
            tr("祝日の判定は公開ライブラリ jpholiday を利用しています"
            "（%s）。") % (tr("利用可能") if HOLIDAY_LIB_READY else tr("未導入")),
            "",
            tr("設定の保存先:"),
            data_dir(),
        ]
        QMessageBox.information(self, tr("このアプリについて"), "\n".join(lines))

    # ------------------------------------------------------------------
    # 鳴動
    # ------------------------------------------------------------------
    def _on_due(self, item: WakeItem, round_no: int) -> None:
        if self.ring_windows and self.vault.prefs.overlap_policy != "queue":
            self._handle_overlap(item, round_no)
            return
        self._open_ring(item, round_no)

    def _handle_overlap(self, item: WakeItem, round_no: int) -> None:
        policy = self.vault.prefs.overlap_policy
        if policy == "snooze" and item.snooze.enabled:
            self.director.begin_snooze(item, dt.datetime.now())
            self.flash_status(tr("「%s」は別のアラームと重なったのでスヌーズにしました。")
                              % item.display_title())
        else:
            self.director.settle_after_stop(item)
            self.flash_status(tr("「%s」は別のアラームと重なったため見送りました。")
                              % item.display_title())
        self.after_change()

    def _open_ring(self, item: WakeItem, round_no: int, preview: bool = False) -> None:
        left = self.director.snooze_rounds_left(item)
        window = RingWindow(item, self.engine, round_no, left, None,
                            hold_awake=self.vault.prefs.keep_awake_ringing)
        if not preview:
            self._fire_actions(item, at_stop=False)
        if preview:
            window.setWindowTitle(tr("試し鳴動 ｜ ") + item.display_title())
            window.stopped.connect(lambda _i: self.director.release(item.uid))
            window.snoozed.connect(lambda _i, _m: self.director.release(item.uid))
            window.auto_stopped.connect(lambda _i: self.director.release(item.uid))
        else:
            window.stopped.connect(self._on_ring_stopped)
            window.snoozed.connect(self._on_ring_snoozed)
            window.auto_stopped.connect(self._on_ring_auto_stopped)
        window.destroyed.connect(lambda _=None, uid=item.uid: self._forget_ring(uid))
        self.ring_windows[item.uid] = window
        window.show()
        window.raise_()
        window.activateWindow()

    def _forget_ring(self, uid: str) -> None:
        self.ring_windows.pop(uid, None)
        self.director.release(uid)

    def _fire_actions(self, item: WakeItem, at_stop: bool) -> None:
        note = actions.run(item.launch, at_stop)
        if note:
            self.flash_status(note)

    def _on_ring_stopped(self, item: WakeItem) -> None:
        self._fire_actions(item, at_stop=True)
        self.director.settle_after_stop(item)
        if item.erase_after_stop:
            self.vault.remove(item.uid)
        self.after_change()

    def _on_ring_snoozed(self, item: WakeItem, minutes: int) -> None:
        left = self.director.snooze_rounds_left(item)
        if left == 0:
            self.director.settle_after_stop(item)
            self.flash_status(tr("スヌーズの上限に達したので停止しました。"))
        else:
            state = self.director.begin_snooze(item, dt.datetime.now(), minutes)
            self.flash_status(tr("%s に再通知します。") % state.due_at.strftime("%H:%M"))
        self.after_change()

    def _on_ring_auto_stopped(self, item: WakeItem) -> None:
        if item.snooze.enabled and self.director.snooze_rounds_left(item) != 0:
            state = self.director.begin_snooze(item, dt.datetime.now())
            message = tr("「%s」は自動停止し、%s に再通知します。") % (
                item.display_title(), state.due_at.strftime("%H:%M"))
        else:
            self.director.settle_after_stop(item)
            message = tr("「%s」は時間が来たので自動停止しました。") % item.display_title()
        if self.vault.prefs.notify_auto_stop:
            self.flash_status(message)
            if self.tray.isVisible():
                self.tray.showMessage(APP_TITLE, message,
                                      QSystemTrayIcon.Information, 6000)
        self.after_change()

    def _report_missed(self) -> None:
        found = self.director.sweep_missed()
        if not found:
            return
        lines = [tr("アプリが動いていない間に、次のアラームの時刻が過ぎていました。"), ""]
        for item, when in found[:8]:
            lines.append("・%s  %s" % (when.strftime("%m/%d %H:%M"),
                                       item.display_title()))
        if len(found) > 8:
            lines.append(tr("ほか %d件") % (len(found) - 8))
        QMessageBox.warning(self, tr("鳴らせなかったアラーム"), "\n".join(lines))

    # ------------------------------------------------------------------
    # 終了まわり
    # ------------------------------------------------------------------
    def _restore_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _teardown(self) -> None:
        """終了時の後片付け。

        どの手順でつまずいても残りを必ず実行する。ここで例外が抜けると
        トレイアイコンが残ったままプロセスが終われなくなるため、
        1 手ずつ握りつぶして先へ進める。
        """
        if self._torn_down:
            return
        self._torn_down = True

        steps = (
            (tr("時刻の記録"), self.director.remember_now),
            (tr("見張りの停止"), self.director.stop),
            (tr("鳴動画面を閉じる"), self._close_ring_windows),
            (tr("タイマーを閉じる"), self._close_timer_window),
            (tr("小窓を閉じる"), self._close_extras),
            (tr("設定の保存"), self.vault.save),
            (tr("音の停止"), self.engine.shutdown),
            (tr("トレイアイコンの削除"), self._drop_tray),
        )
        for label, action in steps:
            try:
                action()
            except Exception as err:            # noqa: BLE001 - 終了は必ず完遂させる
                print(tr("[%s] 終了処理でつまずきました: %s: %s")
                      % (APP_TITLE, label, err), file=sys.stderr)

    def _close_ring_windows(self) -> None:
        for window in list(self.ring_windows.values()):
            window.close()
        self.ring_windows.clear()

    def _close_timer_window(self) -> None:
        if self.timer_window is not None:
            self.timer_window.close()
            self.timer_window = None

    def _close_extras(self) -> None:
        for attr in ("float_bar", "world_window", "todo_window"):
            window = getattr(self, attr, None)
            if window is not None:
                window.close()
                setattr(self, attr, None)

    def _drop_tray(self) -> None:
        self.tray.hide()
        self.tray.setVisible(False)
        self.tray.deleteLater()

    def quit_app(self) -> None:
        self._quitting = True
        self._teardown()
        self.close()
        QApplication.instance().quit()
        # モーダルダイアログの入れ子ループなどが残っていても確実に終わらせる。
        # 後片付けは上で済ませてあるので、ここで落としても失うものはない。
        QTimer.singleShot(1500, lambda: os._exit(0))

    def closeEvent(self, event):
        if not self._quitting and self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                APP_TITLE, tr("常駐しています。アラームは動き続けます。"),
                QSystemTrayIcon.Information, 4000)
            return
        self._teardown()
        super().closeEvent(event)
        QApplication.instance().quit()
