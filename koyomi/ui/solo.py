"""二重起動を防ぐ見張り。

同じ名前の窓口（ローカルソケット）を開けたほうが「本物」になる。
あとから起動したものは、その窓口へ「出てきて」と一言送って自分は終わる。
自動起動を入れると、Windows が開いたものと手で開いたものが並びやすく、
同じアラームが二重に鳴ってしまうため。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SUMMON = b"show"


class SoloGuard(QObject):
    """先客がいるかを調べ、いなければ窓口を開いて待つ。"""

    summoned = Signal()          # あとから来た誰かが「出てきて」と言った

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self._server = None

    # ------------------------------------------------------------------
    def claim(self) -> bool:
        """自分が唯一なら True。先客がいたら知らせて False。"""
        probe = QLocalSocket()
        probe.connectToServer(self.name)
        if probe.waitForConnected(400):
            # 先客がいた。前に出るよう頼んでから引き下がる
            probe.write(SUMMON)
            probe.flush()
            probe.waitForBytesWritten(400)
            probe.disconnectFromServer()
            return False

        # 前回が異常終了して名前が残っていることがあるので、掃除してから開く
        QLocalServer.removeServer(self.name)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_visitor)
        if not self._server.listen(self.name):
            # 窓口を開けなくても、動作そのものは続けられる
            self._server = None
        return True

    def _on_visitor(self) -> None:
        """誰かが繋いできた＝もう一つ起動しようとした、と見なす。

        中身を読んでから判断すると、届く前に読み始めてしまうことがある。
        繋いでくるのは自分たちだけなので、接続そのものを合図として扱う。
        """
        connection = self._server.nextPendingConnection()
        if connection is not None:
            connection.readAll()          # 残っていれば捨てる
            connection.disconnectFromServer()
            connection.deleteLater()
        self.summoned.emit()

    def release(self) -> None:
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self.name)
            self._server = None
