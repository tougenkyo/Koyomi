"""二重起動を防ぐ見張り。

同じ名前の窓口（ローカルソケット）を開けたほうが「本物」になる。
あとから起動したものは、その窓口へ「出てきて」と一言送って自分は終わる。
自動起動を入れると、Windows が開いたものと手で開いたものが並びやすく、
同じアラームが二重に鳴ってしまうため。

更新で開き直すとき、新しい版が古い版へ「立ち上がった」と知らせる窓口もここに置く。
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


# --------------------------------------------------------------------------
# 更新で開き直すときの受け渡し
# --------------------------------------------------------------------------
HANDOVER = "%s-handover-%d"      # 名前と、古い版の pid


class Handover(QObject):
    """古い版が開いて、新しい版から「立ち上がった」と知らせてもらう窓口。

    新しい版は部品を読み込み終えたところで繋いでくる。繋がれば、少なくとも
    起動でつまずいてはいないので、古い版は終わってよい。先に終わってしまうと、
    新しい版がつまずいたときにどちらも残らない。
    """

    arrived = Signal()

    def __init__(self, name: str, pid: int, parent=None):
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_visitor)
        self.listening = self._server.listen(HANDOVER % (name, pid))

    def _on_visitor(self) -> None:
        connection = self._server.nextPendingConnection()
        if connection is not None:
            connection.readAll()
            connection.disconnectFromServer()
            connection.deleteLater()
        self.arrived.emit()

    def close(self) -> None:
        self._server.close()


def tell_ready(name: str, pid: int) -> bool:
    """古い版の窓口へ、立ち上がったことを知らせる。知らせられたら True。"""
    probe = QLocalSocket()
    probe.connectToServer(HANDOVER % (name, pid))
    if not probe.waitForConnected(1000):
        return False
    probe.write(b"ready")
    probe.flush()
    probe.waitForBytesWritten(400)
    probe.disconnectFromServer()
    return True
