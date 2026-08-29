"""起動処理。"""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .. import APP_NAME, APP_TITLE, autostart, i18n
from ..player import SoundEngine
from ..tonesmith import ensure_icon, ensure_tones
from ..vault import Vault
from . import theme
from .main_window import MainWindow
from .solo import SoloGuard


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setQuitOnLastWindowClosed(False)   # 常駐させるので最後の窓を閉じても終わらない

    # すでに動いていたら、そちらを前に出して自分は引き下がる。
    # 二重に動くと同じアラームが二度鳴ってしまう。
    guard = SoloGuard(APP_NAME)
    if not guard.claim():
        return 0

    vault = Vault()
    vault.load()

    # 保存されている好みを、画面を作る前に効かせておく
    theme.apply(vault.prefs.theme)
    i18n.set_language(vault.prefs.language)

    app.setStyleSheet(theme.stylesheet())
    ensure_tones()
    app.setWindowIcon(QIcon(ensure_icon()))

    engine = SoundEngine()

    window = MainWindow(vault, engine)
    window.guard = guard
    guard.summoned.connect(window.summon)

    if autostart.wants_tray():
        # Windows の起動でついでに開いたときは、いきなり画面を出さない
        window.hide()
    else:
        window.show()
    return app.exec()
