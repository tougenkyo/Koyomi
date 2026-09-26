"""起動処理。"""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .. import APP_NAME, APP_TITLE, APP_VERSION, autostart, i18n, updater
from ..logbook import AFTER_UPDATE, BY_AUTOSTART, BY_HAND, BY_TROUBLE, Logbook
from ..player import SoundEngine
from ..tonesmith import ensure_icon, ensure_tones
from ..vault import Vault
from . import theme
from .main_window import MainWindow
from .solo import SoloGuard, tell_ready

# 更新で開き直したとき、前の版が終わるのを待つ長さ（秒）
PREDECESSOR_WAIT = 60


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setQuitOnLastWindowClosed(False)   # 常駐させるので最後の窓を閉じても終わらない

    # 更新で開き直された。立ち上がれたことを前の版へ知らせ、終わるのを待つ。
    # 前の版が動いているうちに下の見張りを通ろうとすると、「すでに動いている」と
    # 見なして引き下がってしまい、どちらも残らない。
    before = updater.predecessor()
    if before:
        tell_ready(APP_NAME, before)
        updater.wait_for_exit(before, PREDECESSOR_WAIT)

    # すでに動いていたら、そちらを前に出して自分は引き下がる。
    # 二重に動くと同じアラームが二度鳴ってしまう。
    guard = SoloGuard(APP_NAME)
    if not guard.claim():
        Logbook().note("二重起動", "先に動いていた方を前に出して、こちらは終了")
        return 0

    if before:
        how = AFTER_UPDATE % before
    elif autostart.wants_tray():
        how = BY_AUTOSTART
    else:
        how = BY_HAND
    logbook = Logbook()
    logbook.open(how, APP_VERSION)
    try:
        return _open_window(app, guard, logbook)
    except BaseException:
        # 起動の途中でつまずいた。中身は run.pyw が error.log へ残す
        logbook.close(BY_TROUBLE)
        raise


def _open_window(app, guard, logbook) -> int:
    vault = Vault()
    vault.load()

    # 保存されている好みを、画面を作る前に効かせておく
    theme.apply(vault.prefs.theme)
    i18n.set_language(vault.prefs.language)

    app.setStyleSheet(theme.stylesheet())
    ensure_tones()
    app.setWindowIcon(QIcon(ensure_icon()))

    engine = SoundEngine()

    window = MainWindow(vault, engine, logbook)
    window.guard = guard
    guard.summoned.connect(window.summon)
    # Windows の終了（シャットダウン・再起動・サインアウト）でも、保存と記録を済ませる
    app.aboutToQuit.connect(window.on_app_quitting)

    if autostart.wants_tray():
        # Windows の起動でついでに開いたときは、いきなり画面を出さない
        window.hide()
    else:
        window.show()
    return app.exec()
