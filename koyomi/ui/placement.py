"""窓の大きさ（と位置）を覚えて、次に開いたときに戻す。

控えは設定の ``Prefs.window_sizes`` に置くので、ほかの設定と一緒に
store.json へ残る。

  - 本体や、タイマーのように自分で開け閉めする窓は、位置と最大化も戻す
  - 編集画面のようなダイアログは大きさだけを戻す。位置まで戻すと、
    親の窓の真ん中に出す Qt の振る舞いが効かなくなるため
"""
from __future__ import annotations

import base64
import binascii

from PySide6.QtCore import QByteArray, QEvent, QObject, QSize

# 大きさや位置、最大化が変わったと分かる出来事。どれが来ても控え直す
_CHANGES = (QEvent.Resize, QEvent.Move, QEvent.WindowStateChange, QEvent.Hide)


class Placement(QObject):
    """1 つの窓に付き添い、大きさが変わるたびに控えておく。

    控えるのは、一度でも表示した窓だけ。自動起動でトレイに畳んだまま
    終えたときに、覚えていた大きさを初期値で上書きしないため。
    最小化している間も控えない。最小化する前の大きさを残したいため。
    """

    def __init__(self, window, vault, key: str, position: bool = True):
        super().__init__(window)
        self.window = window
        self.vault = vault          # 設定は復元で器ごと差し替わるので、vault を持つ
        self.key = key
        self.position = position
        self.shown = False
        self.restore()
        window.installEventFilter(self)

    # ------------------------------------------------------------------
    @property
    def notes(self) -> dict:
        return self.vault.prefs.window_sizes

    def remember(self) -> None:
        window = self.window
        if not self.shown or window.isMinimized():
            return
        if self.position:
            blob = bytes(window.saveGeometry())
            self.notes[self.key] = base64.b64encode(blob).decode("ascii")
        else:
            self.notes[self.key] = "%dx%d" % (window.width(), window.height())

    def restore(self) -> bool:
        """控えがあれば戻す。読めない控えは黙って見送る。"""
        text = str(self.notes.get(self.key) or "")
        if not text:
            return False
        if not self.position:
            width, _, height = text.partition("x")
            if not (width.isdigit() and height.isdigit()):
                return False
            self.window.resize(self._fit(int(width), int(height)))
            return True
        try:
            blob = base64.b64decode(text.encode("ascii"), validate=True)
        except (binascii.Error, ValueError):
            return False
        # 画面の外になる位置や、無くなった画面は Qt が見える所へ直してくれる
        return bool(self.window.restoreGeometry(QByteArray(blob)))

    def _fit(self, width: int, height: int) -> QSize:
        """いまの画面に収まる大きさにする。小さい画面へ移ったときのため。"""
        screen = self.window.screen()
        if screen is not None:
            area = screen.availableGeometry()
            width = min(width, area.width())
            height = min(height, area.height())
        return QSize(width, height)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.window:
            kind = event.type()
            if kind == QEvent.Show:
                self.shown = True
            elif kind in _CHANGES:
                self.remember()
        return False
