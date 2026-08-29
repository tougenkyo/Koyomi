"""アプリ全体の設定画面。"""
from __future__ import annotations

import os

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

from .. import autostart, power
from ..i18n import LANGUAGES
from ..models import QUICK_ACTIONS, ListOrder, WakeItem, as_enum
from ..vault import backups_dir, data_dir
from . import theme
from .widgets import TimeSpinner
from .editor import AlarmEditor
from ..i18n import tr


class SettingsDialog(QDialog):
    """一覧の見せ方、グループ名、新規作成の初期値、バックアップをまとめる。"""

    def __init__(self, vault, engine, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.engine = engine
        self.restored = False
        self.setWindowTitle(tr("設定"))
        self.setMinimumSize(560, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self._theme_at_open = theme.CURRENT

        tabs = QTabWidget()
        tabs.addTab(self._wrap(self._tab_view()), tr("一覧"))
        tabs.addTab(self._wrap(self._tab_look()), tr("外観"))
        tabs.addTab(self._wrap(self._tab_power()), tr("電源"))
        tabs.addTab(self._wrap(self._tab_groups()), tr("グループ"))
        tabs.addTab(self._wrap(self._tab_defaults()), tr("新規作成の初期値"))
        tabs.addTab(self._wrap(self._tab_data()), tr("データ"))
        root.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText(tr("保存"))
        buttons.button(QDialogButtonBox.Save).setProperty("tone", "accent")
        buttons.button(QDialogButtonBox.Cancel).setText(tr("やめる"))
        buttons.accepted.connect(self._commit)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def reject(self):
        # 見た目だけ試して「やめる」を押したときは、元の配色へ戻す
        if theme.CURRENT != self._theme_at_open:
            theme.apply(self._theme_at_open)
            window = self.parent()
            if hasattr(window, "repaint_theme"):
                window.repaint_theme()
        super().reject()

    @staticmethod
    def _wrap(inner: QWidget) -> QWidget:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setWidget(inner)
        return area

    # ------------------------------------------------------------------
    def _tab_view(self) -> QWidget:
        prefs = self.vault.prefs
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        box = QGroupBox(tr("並び順と表示"))
        form = QFormLayout(box)
        self.order_box = QComboBox()
        for order in ListOrder:
            self.order_box.addItem(order.label, order)
        self.order_box.setCurrentIndex(list(ListOrder).index(prefs.order))
        form.addRow(tr("並び順"), self.order_box)

        self.left_align = QCheckBox(tr("アラーム名を左寄せにする"))
        self.left_align.setChecked(prefs.left_align_titles)
        form.addRow(self.left_align)

        self.keep_filter = QCheckBox(tr("グループの絞り込みを次回起動時も保つ"))
        self.keep_filter.setChecked(prefs.keep_group_filter)
        form.addRow(self.keep_filter)
        lay.addWidget(box)

        quick = QGroupBox(tr("下部のクイックメニュー"))
        ql = QVBoxLayout(quick)
        self.show_quick = QCheckBox(tr("クイックメニューを表示する"))
        self.show_quick.setChecked(prefs.show_quick_bar)
        ql.addWidget(self.show_quick)
        ql.addWidget(QLabel(tr("6 つの中から 3 つを選びます。")))
        self.quick_boxes = []
        for slot in range(3):
            row = QComboBox()
            for key, label in QUICK_ACTIONS.items():
                row.addItem(tr(label), key)
            hit = row.findData(prefs.quick_actions[slot])
            row.setCurrentIndex(max(0, hit))
            ql.addWidget(row)
            self.quick_boxes.append(row)
        lay.addWidget(quick)

        alerts = QGroupBox(tr("お知らせ"))
        al = QFormLayout(alerts)
        self.tray_next = QCheckBox(tr("タスクトレイに次のアラーム時刻を出す"))
        self.tray_next.setChecked(prefs.tray_next_alarm)
        al.addRow(self.tray_next)
        self.notify_auto = QCheckBox(tr("自動停止したときに知らせる"))
        self.notify_auto.setChecked(prefs.notify_auto_stop)
        al.addRow(self.notify_auto)

        self.overlap_box = QComboBox()
        self.overlap_box.addItem(tr("鳴動中なら後から来た方をスヌーズにする"), "snooze")
        self.overlap_box.addItem(tr("鳴動中なら後から来た方を止める"), "stop")
        self.overlap_box.addItem(tr("鳴動中でも別ウィンドウで重ねて鳴らす"), "queue")
        hit = self.overlap_box.findData(prefs.overlap_policy)
        self.overlap_box.setCurrentIndex(max(0, hit))
        al.addRow(tr("重なったとき"), self.overlap_box)

        self.catchup_box = QSpinBox()
        self.catchup_box.setRange(0, 720)
        self.catchup_box.setSuffix(tr(" 分（0 で拾わない）"))
        self.catchup_box.setValue(prefs.catch_up_window_minutes)
        al.addRow(tr("起動時に取りこぼしを拾う範囲"), self.catchup_box)
        lay.addWidget(alerts)

        lay.addStretch(1)
        return page

    def _tab_look(self) -> QWidget:
        prefs = self.vault.prefs
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        box = QGroupBox(tr("配色"))
        bl = QVBoxLayout(box)
        self.theme_box = QComboBox()
        for key, label in theme.catalog().items():
            self.theme_box.addItem(label, key)
        hit = self.theme_box.findData(prefs.theme)
        self.theme_box.setCurrentIndex(max(0, hit))
        self.theme_box.currentIndexChanged.connect(self._preview_theme)
        bl.addWidget(self.theme_box)
        note = QLabel(tr("下地 3 系統とさし色 9 色の組み合わせで %d 通りあります。"
                      "選ぶとその場で反映されます。") % len(theme.catalog()))
        note.setWordWrap(True)
        note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        bl.addWidget(note)
        lay.addWidget(box)

        lang = QGroupBox(tr("ことば"))
        ll = QVBoxLayout(lang)
        self.lang_box = QComboBox()
        for code, label in LANGUAGES.items():
            self.lang_box.addItem(label, code)
        hit = self.lang_box.findData(prefs.language)
        self.lang_box.setCurrentIndex(max(0, hit))
        ll.addWidget(self.lang_box)
        hint = QLabel(tr("切り替えたあと、アプリを開き直すとすべての画面に行き渡ります。"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        ll.addWidget(hint)
        lay.addWidget(lang)

        floater = QGroupBox(tr("フローティング表示"))
        fl = QVBoxLayout(floater)
        self.float_box = QCheckBox(tr("小さな窓を画面のすみに出しておく"))
        self.float_box.setChecked(prefs.float_bar)
        fl.addWidget(self.float_box)
        fnote = QLabel(tr("次のアラームと、走っているタイマーの残りを常に表示します。"
                       "どこを掴んでも動かせます。"))
        fnote.setWordWrap(True)
        fnote.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        fl.addWidget(fnote)
        lay.addWidget(floater)

        lay.addStretch(1)
        return page

    def _preview_theme(self) -> None:
        key = self.theme_box.currentData()
        if not key:
            return
        theme.apply(key)
        window = self.parent()
        if hasattr(window, "repaint_theme"):
            window.repaint_theme()

    def _tab_power(self) -> QWidget:
        prefs = self.vault.prefs
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        if not power.IS_WINDOWS:
            warn = QLabel(tr("この OS では電源まわりの操作に対応していません。"))
            warn.setStyleSheet("color: %s;" % theme.WARN)
            warn.setWordWrap(True)
            lay.addWidget(warn)

        boot = QGroupBox(tr("Windows の起動時に始める"))
        bl = QVBoxLayout(boot)
        self.boot_box = QCheckBox(tr("Windows を起動したら、このアプリも開始する"))
        self.boot_box.setChecked(autostart.healthy())
        self.boot_box.setEnabled(autostart.IS_WINDOWS)
        bl.addWidget(self.boot_box)

        self.boot_tray = QCheckBox(tr("そのときはトレイに畳んでおく"))
        self.boot_tray.setChecked(prefs.start_minimized)
        self.boot_tray.setEnabled(autostart.IS_WINDOWS)
        bl.addWidget(self.boot_tray)

        self.boot_state = QLabel(autostart.state())
        self.boot_state.setWordWrap(True)
        self.boot_state.setStyleSheet("color: %s; font-size: 11px;"
                                      % theme.TEXT_SUB)
        bl.addWidget(self.boot_state)

        boot_row = QHBoxLayout()
        again = QPushButton(tr("登録し直す"))
        again.setProperty("tone", "ghost")
        again.setEnabled(autostart.IS_WINDOWS)
        again.clicked.connect(self._reregister_boot)
        boot_row.addWidget(again)
        opener = QPushButton(tr("Windows の設定を開く"))
        opener.setProperty("tone", "ghost")
        opener.setEnabled(autostart.IS_WINDOWS)
        opener.clicked.connect(autostart.open_startup_settings)
        boot_row.addWidget(opener)
        boot_row.addStretch(1)
        bl.addLayout(boot_row)

        note = QLabel(tr("このフォルダを移動すると登録が外れます。"
                         "移動したときは「登録し直す」を押してください。"))
        note.setWordWrap(True)
        note.setStyleSheet("color: %s; font-size: 11px;" % theme.TEXT_SUB)
        bl.addWidget(note)
        lay.addWidget(boot)

        fresh = QGroupBox(tr("更新"))
        fl = QVBoxLayout(fresh)
        self.update_box = QCheckBox(tr("起動したときに新しい版が出ていないか調べる"))
        self.update_box.setChecked(prefs.check_updates)
        fl.addWidget(self.update_box)
        unote = QLabel(tr("調べるときだけ GitHub へ問い合わせます。"
                          "切っていても、メニューの「更新を確認」からいつでも調べられます。"))
        unote.setWordWrap(True)
        unote.setStyleSheet("color: %s; font-size: 11px;" % theme.TEXT_SUB)
        fl.addWidget(unote)
        lay.addWidget(fresh)

        wake = QGroupBox(tr("時刻に合わせて PC を起こす"))
        wl = QVBoxLayout(wake)
        self.wake_box = QCheckBox(tr("スリープ中でも、次のアラームの少し前に復帰させる"))
        self.wake_box.setChecked(prefs.wake_pc)
        self.wake_box.setEnabled(power.IS_WINDOWS)
        wl.addWidget(self.wake_box)
        caution = QLabel(
            tr("Windows の電源オプションで「スリープ解除タイマーの許可」が"
            "有効になっている必要があります。"
            "休止状態や電源を切った状態からは復帰できません。"))
        caution.setWordWrap(True)
        caution.setStyleSheet("color: %s; font-size: 11px;" % theme.TEXT_SUB)
        wl.addWidget(caution)

        probe = QPushButton(tr("いまの予約状況を確かめる"))
        probe.setProperty("tone", "ghost")
        probe.clicked.connect(self._probe_wake)
        wl.addWidget(probe)
        self.wake_report = QPlainTextEdit()
        self.wake_report.setReadOnly(True)
        self.wake_report.setMaximumHeight(130)
        self.wake_report.setPlaceholderText(tr("ここに確認結果が出ます。"))
        wl.addWidget(self.wake_report)
        lay.addWidget(wake)

        hold = QGroupBox(tr("鳴っている間"))
        hl = QVBoxLayout(hold)
        self.hold_box = QCheckBox(tr("アラームが鳴っている間はスリープさせない"))
        self.hold_box.setChecked(prefs.keep_awake_ringing)
        self.hold_box.setEnabled(power.IS_WINDOWS)
        hl.addWidget(self.hold_box)
        lay.addWidget(hold)

        rest = QGroupBox(tr("決めた時刻に PC をスリープさせる"))
        rl = QFormLayout(rest)
        self.sleep_box = QCheckBox(tr("使う"))
        self.sleep_box.setChecked(prefs.auto_sleep)
        self.sleep_box.setEnabled(power.IS_WINDOWS)
        rl.addRow(self.sleep_box)
        self.sleep_at = TimeSpinner(display="HH:mm")
        try:
            hour, minute = (int(x) for x in prefs.auto_sleep_at.split(":"))
        except ValueError:
            hour, minute = 1, 0
        self.sleep_at.setTime(QTime(hour, minute))
        rl.addRow(tr("時刻"), self.sleep_at)
        warn2 = QLabel(tr("作業中でもそのままスリープに入ります。"
                       "アラームが鳴っている間とスヌーズ中は見送ります。"))
        warn2.setWordWrap(True)
        warn2.setStyleSheet("color: %s; font-size: 11px;" % theme.TEXT_SUB)
        rl.addRow(warn2)
        lay.addWidget(rest)

        lay.addStretch(1)
        return page

    def _reregister_boot(self) -> None:
        trouble = autostart.enable(self.boot_tray.isChecked())
        self.boot_box.setChecked(autostart.healthy())
        self.boot_state.setText(trouble or autostart.state())

    def _probe_wake(self) -> None:
        self.wake_report.setPlainText(power.wake_timer_report())

    def _tab_groups(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)
        box = QGroupBox(tr("グループ名"))
        form = QFormLayout(box)
        self.group_fields = {}
        for key, name in sorted(self.vault.groups.items()):
            field = QLineEdit(name)
            form.addRow(key.upper(), field)
            self.group_fields[key] = field
        lay.addWidget(box)
        note = QLabel(tr("グループはアラームの絞り込みや、まとめて ON/OFF するときに使います。"))
        note.setWordWrap(True)
        note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        lay.addWidget(note)
        lay.addStretch(1)
        return page

    def _tab_defaults(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)
        note = QLabel(tr("「追加」で新しいアラームを作るときの初期値です。"
                      "すでにあるアラームには影響しません。"))
        note.setWordWrap(True)
        note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        lay.addWidget(note)

        self.default_summary = QLabel()
        self.default_summary.setWordWrap(True)
        self.default_summary.setStyleSheet(
            "background: %s; border: 1px solid %s; border-radius: 8px; padding: 10px;"
            % (theme.SLATE, theme.LINE))
        lay.addWidget(self.default_summary)

        edit = QPushButton(tr("初期値を編集する"))
        edit.setProperty("tone", "ghost")
        edit.clicked.connect(self._edit_defaults)
        lay.addWidget(edit)

        reset = QPushButton(tr("初期値を工場出荷時に戻す"))
        reset.setProperty("tone", "ghost")
        reset.clicked.connect(self._reset_defaults)
        lay.addWidget(reset)

        lay.addStretch(1)
        self._pending_default = dict(self.vault.prefs.default_item)
        self._refresh_default_summary()
        return page

    def _refresh_default_summary(self) -> None:
        from .. import planner
        item = WakeItem.from_dict(self._pending_default)
        lines = [
            tr("時刻　　： %s") % item.clock_text,
            tr("繰り返し： %s") % planner.repeat_digest(item, self.vault.almanac),
            tr("音　　　： %s / 音量 %d%%") % (item.sound.source or "-", item.sound.volume),
            tr("止め方　： %s") % item.stop_guard.style.label,
            tr("スヌーズ： %s") % (tr("%d分 / 最大%s") % (
                item.snooze.minutes,
                tr("無制限") if item.snooze.max_rounds == 0 else tr("%d回") % item.snooze.max_rounds)
                if item.snooze.enabled else tr("使わない")),
        ]
        self.default_summary.setText("\n".join(lines))

    def _edit_defaults(self) -> None:
        item = WakeItem.from_dict(self._pending_default)
        dialog = AlarmEditor(item, self.vault, self.engine, self,
                             title=tr("新規作成の初期値"))
        if dialog.exec() == QDialog.Accepted:
            self._pending_default = dialog.result_item().to_dict()
            self._refresh_default_summary()

    def _reset_defaults(self) -> None:
        self._pending_default = WakeItem().to_dict()
        self._refresh_default_summary()

    def _tab_data(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        box = QGroupBox(tr("保存場所"))
        bl = QVBoxLayout(box)
        path = QLabel(data_dir())
        path.setWordWrap(True)
        path.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        bl.addWidget(path)
        open_btn = QPushButton(tr("フォルダを開く"))
        open_btn.setProperty("tone", "ghost")
        open_btn.clicked.connect(lambda: os.startfile(data_dir()))
        bl.addWidget(open_btn)
        lay.addWidget(box)

        backup = QGroupBox(tr("バックアップ"))
        kl = QVBoxLayout(backup)
        row = QHBoxLayout()
        save = QPushButton(tr("バックアップを作る"))
        save.setProperty("tone", "accent")
        save.clicked.connect(self._backup)
        row.addWidget(save)
        load = QPushButton(tr("バックアップから戻す"))
        load.clicked.connect(self._restore)
        row.addWidget(load)
        kl.addLayout(row)
        note = QLabel(tr("戻すと、いまのアラームと設定はすべて置き換わります。"))
        note.setWordWrap(True)
        note.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        kl.addWidget(note)
        lay.addWidget(backup)

        lay.addStretch(1)
        return page

    def _backup(self) -> None:
        default = os.path.join(backups_dir(), "koyomi-backup.json")
        path, _ = QFileDialog.getSaveFileName(self, tr("バックアップの保存先"), default,
                                              "JSON (*.json)")
        if not path:
            return
        try:
            self.vault.write_backup(path)
        except OSError as err:
            QMessageBox.warning(self, tr("保存できません"), str(err))
            return
        QMessageBox.information(self, tr("バックアップ"), tr("書き出しました。\n%s") % path)

    def _restore(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("バックアップを選ぶ"), backups_dir(),
                                              "JSON (*.json)")
        if not path:
            return
        answer = QMessageBox.question(
            self, tr("確認"),
            tr("いまのアラームと設定をすべて置き換えます。よろしいですか？"))
        if answer != QMessageBox.Yes:
            return
        try:
            self.vault.read_backup(path)
        except (OSError, ValueError) as err:
            QMessageBox.warning(self, tr("読み込めません"), str(err))
            return
        self.restored = True
        QMessageBox.information(self, tr("復元"), tr("バックアップから戻しました。"))
        self.accept()

    # ------------------------------------------------------------------
    def _commit(self) -> None:
        if self.restored:
            self.accept()
            return
        prefs = self.vault.prefs
        prefs.order = as_enum(ListOrder, self.order_box.currentData())
        prefs.left_align_titles = self.left_align.isChecked()
        prefs.keep_group_filter = self.keep_filter.isChecked()
        prefs.show_quick_bar = self.show_quick.isChecked()
        picked = []
        for box in self.quick_boxes:
            key = box.currentData()
            if key not in picked:
                picked.append(key)
        for key in QUICK_ACTIONS:
            if len(picked) >= 3:
                break
            if key not in picked:
                picked.append(key)
        prefs.quick_actions = picked[:3]
        prefs.tray_next_alarm = self.tray_next.isChecked()
        prefs.notify_auto_stop = self.notify_auto.isChecked()
        prefs.overlap_policy = self.overlap_box.currentData()
        prefs.catch_up_window_minutes = self.catchup_box.value()
        prefs.default_item = self._pending_default

        prefs.theme = self.theme_box.currentData() or prefs.theme
        prefs.language = self.lang_box.currentData() or prefs.language
        prefs.float_bar = self.float_box.isChecked()
        prefs.wake_pc = self.wake_box.isChecked()
        prefs.keep_awake_ringing = self.hold_box.isChecked()
        prefs.auto_sleep = self.sleep_box.isChecked()
        prefs.auto_sleep_at = self.sleep_at.time().toString("HH:mm")
        prefs.start_minimized = self.boot_tray.isChecked()
        prefs.check_updates = self.update_box.isChecked()
        if autostart.IS_WINDOWS:
            if self.boot_box.isChecked():
                autostart.enable(prefs.start_minimized)
            elif autostart.is_registered():
                autostart.disable()

        for key, field in self.group_fields.items():
            name = field.text().strip()
            if name:
                self.vault.groups[key] = name
        self.accept()
