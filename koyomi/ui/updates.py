"""更新の確認と取り込みの画面。"""
from __future__ import annotations

import threading
import webbrowser

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

from .. import APP_TITLE, APP_VERSION, updater
from ..i18n import tr
from . import theme


class Probe(QObject):
    """調べに行くあいだ画面が固まらないよう、別の流れで動かす。"""

    answered = Signal(object)

    def start(self) -> None:
        def work():
            try:
                self.answered.emit(updater.look_up())
            except Exception as err:            # noqa: BLE001 - 何があっても返す
                self.answered.emit({"ok": False, "version": "", "newer": False,
                                    "source": "", "url": "",
                                    "message": str(err)})
        threading.Thread(target=work, daemon=True).start()


class UpdateDialog(QDialog):
    """いまの版と向こうの版を見比べ、その場で取り込む。"""

    restart_wanted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("更新の確認"))
        self.setMinimumWidth(460)
        self._latest = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        self.headline = QLabel(tr("調べています…"))
        self.headline.setWordWrap(True)
        self.headline.setStyleSheet("font-size: 16px;")
        root.addWidget(self.headline)

        self.detail = QLabel(tr("いまの版: %s") % APP_VERSION)
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color: %s;" % theme.TEXT_SUB)
        root.addWidget(self.detail)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.log.hide()
        root.addWidget(self.log)

        buttons = QHBoxLayout()
        self.page_btn = QPushButton(tr("配布ページを開く"))
        self.page_btn.setProperty("tone", "ghost")
        self.page_btn.clicked.connect(self._open_page)
        self.page_btn.hide()
        buttons.addWidget(self.page_btn)
        buttons.addStretch(1)

        self.apply_btn = QPushButton(tr("いまの場所を更新する"))
        self.apply_btn.setProperty("tone", "accent")
        self.apply_btn.clicked.connect(self._apply)
        self.apply_btn.hide()
        buttons.addWidget(self.apply_btn)

        self.restart_btn = QPushButton(tr("開き直して反映する"))
        self.restart_btn.setProperty("tone", "accent")
        self.restart_btn.clicked.connect(self._restart)
        self.restart_btn.hide()
        buttons.addWidget(self.restart_btn)

        self.close_btn = QPushButton(tr("閉じる"))
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        root.addLayout(buttons)

        self.probe = Probe(self)
        self.probe.answered.connect(self._show_answer, Qt.QueuedConnection)
        self.probe.start()

    # ------------------------------------------------------------------
    def _show_answer(self, answer: dict) -> None:
        self._answer = answer
        if not answer.get("ok"):
            self.headline.setText(tr("確認できませんでした。"))
            self.detail.setText(answer.get("message")
                                or tr("通信できなかったようです。"))
            self.page_btn.show()
            return

        latest = answer.get("version", "")
        self._latest = latest
        if not answer.get("newer"):
            self.headline.setText(tr("最新版を使っています。"))
            self.detail.setText(tr("いまの版: %s") % APP_VERSION)
            return

        self.headline.setText(tr("新しい版 %s があります。") % latest)
        self.detail.setText(tr("いまの版: %s ／ 向こうの版: %s")
                            % (APP_VERSION, latest))
        self.page_btn.show()

        blocked = updater.can_pull()
        if blocked:
            self.log.setPlainText(blocked)
            self.log.show()
        else:
            self.apply_btn.show()

    def _open_page(self) -> None:
        url = (self._answer or {}).get("url")
        if url:
            webbrowser.open(url)

    def _apply(self) -> None:
        self.apply_btn.setEnabled(False)
        self.headline.setText(tr("取り込んでいます…"))
        ok, text = updater.pull()
        self.log.setPlainText(text or "")
        self.log.show()
        if ok:
            self.headline.setText(tr("取り込みました。開き直すと新しい版になります。"))
            self.restart_btn.show()
        else:
            self.headline.setText(tr("取り込めませんでした。"))
            self.page_btn.show()
            self.apply_btn.setEnabled(True)

    def _restart(self) -> None:
        if updater.relaunch():
            self.accept()
            self.restart_wanted.emit()
        else:
            self.headline.setText(tr("開き直せませんでした。"
                                     "手で起動し直してください。"))


def quiet_check(window) -> None:
    """起動時の自動確認。新しい版があるときだけ、そっと知らせる。"""
    probe = Probe(window)

    def announce(answer):
        if answer.get("ok") and answer.get("newer"):
            window.flash_status(
                tr("新しい版 %s が出ています。メニューの「更新を確認」から取り込めます。")
                % answer.get("version", ""))
            if window.tray.isVisible():
                window.tray.showMessage(
                    APP_TITLE,
                    tr("新しい版 %s が出ています。") % answer.get("version", ""),
                    window.tray.MessageIcon.Information, 6000)

    probe.answered.connect(announce, Qt.QueuedConnection)
    window._update_probe = probe        # 途中で片づけられないよう抱えておく
    probe.start()
