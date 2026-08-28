"""起動処理。"""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .. import APP_TITLE, i18n
from ..player import SoundEngine
from ..tonesmith import ensure_icon, ensure_tones
from ..vault import Vault
from . import theme
from .main_window import MainWindow


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setQuitOnLastWindowClosed(False)   # 常駐させるので最後の窓を閉じても終わらない

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
    window.show()
    return app.exec()
