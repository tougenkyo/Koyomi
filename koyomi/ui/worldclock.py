"""世界時計。選んだ都市の「いま」を並べて見る。"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from ..models import WEEKDAY_LABELS
from . import theme
from ..i18n import tr

try:                                   # pragma: no cover - 環境依存
    from zoneinfo import ZoneInfo, available_timezones
    TZ_READY = True
except ImportError:                    # pragma: no cover
    ZoneInfo = None

    def available_timezones():
        return set()
    TZ_READY = False


# よく使う都市。ここに無い地域は下の検索欄から選べる。
FAVOURITES = [
    ("東京", "Asia/Tokyo"),
    ("ソウル", "Asia/Seoul"),
    ("北京・上海", "Asia/Shanghai"),
    ("台北", "Asia/Taipei"),
    ("香港", "Asia/Hong_Kong"),
    ("シンガポール", "Asia/Singapore"),
    ("バンコク", "Asia/Bangkok"),
    ("デリー", "Asia/Kolkata"),
    ("ドバイ", "Asia/Dubai"),
    ("モスクワ", "Europe/Moscow"),
    ("ベルリン", "Europe/Berlin"),
    ("パリ", "Europe/Paris"),
    ("ロンドン", "Europe/London"),
    ("ニューヨーク", "America/New_York"),
    ("シカゴ", "America/Chicago"),
    ("デンバー", "America/Denver"),
    ("ロサンゼルス", "America/Los_Angeles"),
    ("ホノルル", "Pacific/Honolulu"),
    ("メキシコシティ", "America/Mexico_City"),
    ("サンパウロ", "America/Sao_Paulo"),
    ("シドニー", "Australia/Sydney"),
    ("オークランド", "Pacific/Auckland"),
    ("協定世界時 (UTC)", "UTC"),
]

_LOOKUP = {key: name for name, key in FAVOURITES}


def pretty_name(key: str) -> str:
    """IANA の名前を、読みやすい形に。"""
    if key in _LOOKUP:
        return tr(_LOOKUP[key])
    return key.split("/")[-1].replace("_", " ")


def zone_now(key: str):
    if not TZ_READY:
        return None
    try:
        return dt.datetime.now(ZoneInfo(key))
    except Exception:              # noqa: BLE001 - 未知の地域名は静かに捨てる
        return None


def offset_text(moment) -> str:
    """ローカル時刻との差を ±h:mm で。"""
    here = dt.datetime.now().astimezone()
    delta = (moment.utcoffset() or dt.timedelta()) - (here.utcoffset() or dt.timedelta())
    total = int(delta.total_seconds())
    sign = "＋" if total >= 0 else "−"
    hours, rem = divmod(abs(total), 3600)
    minutes = rem // 60
    if hours == 0 and minutes == 0:
        return tr("現地と同じ")
    if minutes:
        return tr("%s%d時間%d分") % (sign, hours, minutes)
    return tr("%s%d時間") % (sign, hours)


class ClockRow(QWidget):
    """1 都市ぶんの行。"""

    def __init__(self, key: str, on_remove, parent=None):
        super().__init__(parent)
        self.key = key
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "ClockRow { background: %s; border: 1px solid %s; border-radius: 10px; }"
            % (theme.SLATE, theme.LINE))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        names = QVBoxLayout()
        names.setSpacing(0)
        self.city = QLabel(pretty_name(key))
        self.city.setStyleSheet("font-size: 15px;")
        names.addWidget(self.city)
        self.zone = QLabel(key)
        self.zone.setStyleSheet("font-size: 11px; color: %s;" % theme.TEXT_SUB)
        names.addWidget(self.zone)
        lay.addLayout(names, 1)

        stamp = QVBoxLayout()
        stamp.setSpacing(0)
        self.clock = QLabel("--:--")
        self.clock.setAlignment(Qt.AlignRight)
        self.clock.setStyleSheet("font-size: 26px; font-weight: bold;")
        stamp.addWidget(self.clock)
        self.detail = QLabel("")
        self.detail.setAlignment(Qt.AlignRight)
        self.detail.setStyleSheet("font-size: 11px; color: %s;" % theme.TEXT_SUB)
        stamp.addWidget(self.detail)
        lay.addLayout(stamp)

        drop = QPushButton(tr("削除"))
        drop.setProperty("tone", "ghost")
        drop.clicked.connect(lambda: on_remove(self))
        lay.addWidget(drop)

        self.refresh()

    def refresh(self) -> None:
        moment = zone_now(self.key)
        if moment is None:
            self.clock.setText("--:--")
            self.detail.setText(tr("この地域は表示できません"))
            return
        self.clock.setText(moment.strftime("%H:%M:%S"))
        weekday = tr(WEEKDAY_LABELS[moment.weekday()])
        today = dt.date.today()
        if moment.date() > today:
            day_note = tr("翌日")
        elif moment.date() < today:
            day_note = tr("前日")
        else:
            day_note = tr("今日")
        self.detail.setText("%s（%s）%s　%s"
                            % (moment.strftime("%m/%d"), weekday, day_note,
                               offset_text(moment)))


class WorldClockWindow(QDialog):
    """都市を並べて時刻を見る窓。"""

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.rows = []
        self.setWindowTitle(tr("世界時計"))
        self.setMinimumSize(560, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        if not TZ_READY:
            warn = QLabel(tr("地域データ（tzdata）が見つからないため、時刻を出せません。"))
            warn.setStyleSheet("color: %s;" % theme.WARN)
            warn.setWordWrap(True)
            root.addWidget(warn)

        picker = QHBoxLayout()
        self.city_box = QComboBox()
        for name, key in FAVOURITES:
            self.city_box.addItem(tr(name), key)
        picker.addWidget(self.city_box, 1)
        add = QPushButton(tr("追加"))
        add.setProperty("tone", "accent")
        add.clicked.connect(lambda: self.add_zone(self.city_box.currentData()))
        picker.addWidget(add)
        root.addLayout(picker)

        search = QHBoxLayout()
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText(
            tr("ほかの地域を探す（例: Lisbon, Cairo, Asia/）"))
        self.search_field.textChanged.connect(self._search)
        search.addWidget(self.search_field, 1)
        self.hit_box = QComboBox()
        self.hit_box.setMinimumWidth(200)
        search.addWidget(self.hit_box)
        add2 = QPushButton(tr("追加"))
        add2.clicked.connect(self._add_from_search)
        search.addWidget(add2)
        root.addLayout(search)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        holder = QWidget()
        self.list_layout = QVBoxLayout(holder)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch(1)
        area.setWidget(holder)
        root.addWidget(area, 1)

        self.empty = QLabel(tr("上の欄から都市を選んで追加してください。"))
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color: %s; padding: 30px;" % theme.TEXT_SUB)
        self.list_layout.insertWidget(0, self.empty)

        for key in self.vault.world_zones:
            self._make_row(key)
        self._refresh_empty()

        self.beat = QTimer(self)
        self.beat.setInterval(500)
        self.beat.timeout.connect(self._on_beat)
        self.beat.start()

    # ------------------------------------------------------------------
    def _search(self, text: str) -> None:
        self.hit_box.clear()
        needle = text.strip().lower()
        if len(needle) < 2:
            return
        hits = sorted(z for z in available_timezones() if needle in z.lower())
        for key in hits[:60]:
            self.hit_box.addItem(key, key)

    def _add_from_search(self) -> None:
        key = self.hit_box.currentData()
        if key:
            self.add_zone(key)

    def add_zone(self, key: str) -> None:
        if not key or key in self.vault.world_zones:
            return
        self.vault.world_zones.append(key)
        self._make_row(key)
        self._refresh_empty()

    def _make_row(self, key: str) -> None:
        row = ClockRow(key, self._remove)
        self.list_layout.insertWidget(self.list_layout.count() - 1, row)
        self.rows.append(row)

    def _remove(self, row: ClockRow) -> None:
        if row.key in self.vault.world_zones:
            self.vault.world_zones.remove(row.key)
        if row in self.rows:
            self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._refresh_empty()

    def _refresh_empty(self) -> None:
        self.empty.setVisible(not self.rows)

    def _on_beat(self) -> None:
        for row in self.rows:
            row.refresh()

    def closeEvent(self, event):
        self.beat.stop()
        super().closeEvent(event)
