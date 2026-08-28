"""停止・スヌーズを確定させるための操作パネル。

どのパネルも ``solved`` を 1 回だけ出す。呼び出し側はその合図だけを見ればよい。
"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QGridLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from ..models import Guard, GuardPlan, Toughness
from . import theme
from .widgets import HoldButton, SlideToAct
from ..i18n import tr

SYMBOLS = ["★", "●", "▲", "■", "◆", "♥", "✚", "✦", "◐", "☘"]

SHAPE_NAMES = {"circle": "まる", "square": "しかく", "triangle": "さんかく",
               "diamond": "ひしがた"}
COLOR_NAMES = {"#f6b13c": "きいろ", "#6aa9ff": "あお", "#5fce9b": "みどり",
               "#ef6b6b": "あか", "#c89bf0": "むらさき"}


class GuardPad(QWidget):
    """解除パネルの共通の親。"""

    solved = Signal()

    def __init__(self, plan: GuardPlan, caption: str, tint: str, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.caption = caption
        self.tint = tint
        self._done = False

    def _finish(self) -> None:
        if self._done:
            return
        self._done = True
        self.solved.emit()


# --------------------------------------------------------------------------
# 単純な操作
# --------------------------------------------------------------------------
class TapPad(GuardPad):
    def __init__(self, plan, caption, tint, parent=None):
        super().__init__(plan, caption, tint, parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton(caption)
        btn.setMinimumHeight(62)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "background: %s; color: #1b1f27; border: none; border-radius: 12px;"
            "font-size: 17px; font-weight: bold;" % tint)
        btn.clicked.connect(self._finish)
        lay.addWidget(btn)


class HoldPad(GuardPad):
    def __init__(self, plan, caption, tint, parent=None):
        super().__init__(plan, caption, tint, parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        secs = max(0.5, plan.hold_seconds)
        btn = HoldButton(tr("%s（%.1f秒 長押し）") % (caption, secs), secs, tint)
        btn.setStyleSheet(
            "QPushButton { background: %s; color: #1b1f27; border: none;"
            "border-radius: 12px; font-size: 16px; font-weight: bold; }" % tint)
        btn.completed.connect(self._finish)
        lay.addWidget(btn)


class SlidePad(GuardPad):
    def __init__(self, plan, caption, tint, parent=None):
        super().__init__(plan, caption, tint, parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = SlideToAct(tr("スライドして%s") % caption, tint)
        bar.completed.connect(self._finish)
        lay.addWidget(bar)


# --------------------------------------------------------------------------
# 計算問題
# --------------------------------------------------------------------------
def make_sum(toughness: Toughness, rng: random.Random) -> tuple:
    """(問題文, 答え) を作る。"""
    if toughness == Toughness.LIGHT:
        a, b = rng.randint(2, 19), rng.randint(2, 19)
        if rng.random() < 0.4 and a > b:
            return "%d − %d" % (a, b), a - b
        return "%d ＋ %d" % (a, b), a + b
    if toughness == Toughness.MIDDLE:
        a, b = rng.randint(3, 12), rng.randint(3, 12)
        c = rng.randint(2, 19)
        if rng.random() < 0.5:
            return "%d × %d" % (a, b), a * b
        return "%d × %d ＋ %d" % (a, b, c), a * b + c
    a, b = rng.randint(12, 39), rng.randint(4, 19)
    c = rng.randint(11, 59)
    if rng.random() < 0.5:
        return "%d × %d − %d" % (a, b, c), a * b - c
    return "%d × %d ＋ %d" % (a, b, c), a * b + c


class MathPad(GuardPad):
    """計算問題を規定回数ぶん正解させる。"""

    def __init__(self, plan, caption, tint, parent=None):
        super().__init__(plan, caption, tint, parent)
        self.rng = random.Random()
        self.total = max(1, plan.rounds)
        self.cleared = 0
        self.answer = 0
        self.buffer = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.progress = QLabel()
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        lay.addWidget(self.progress)

        self.question = QLabel()
        self.question.setAlignment(Qt.AlignCenter)
        self.question.setStyleSheet("font-size: 30px; font-weight: bold;")
        lay.addWidget(self.question)

        self.entry = QLabel("_")
        self.entry.setAlignment(Qt.AlignCenter)
        self.entry.setMinimumHeight(42)
        self.entry.setStyleSheet(
            "background: %s; border: 1px solid %s; border-radius: 10px;"
            "font-size: 22px; letter-spacing: 2px;" % (theme.SLATE, theme.LINE))
        lay.addWidget(self.entry)

        self.hint = QLabel(" ")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet("color: %s; font-size: 12px;" % theme.WARN)
        lay.addWidget(self.hint)

        grid = QGridLayout()
        grid.setSpacing(6)
        keys = ["7", "8", "9", "4", "5", "6", "1", "2", "3", "−", "0", "←"]
        for idx, key in enumerate(keys):
            btn = QPushButton(key)
            btn.setMinimumHeight(46)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("font-size: 18px;")
            btn.clicked.connect(lambda _=False, k=key: self._press(k))
            grid.addWidget(btn, idx // 3, idx % 3)
        ok = QPushButton(tr("こたえる"))
        ok.setMinimumHeight(46)
        ok.setCursor(Qt.PointingHandCursor)
        ok.setStyleSheet(
            "background: %s; color: #1b1f27; border: none; border-radius: 8px;"
            "font-weight: bold; font-size: 15px;" % tint)
        ok.clicked.connect(self._submit)
        grid.addWidget(ok, 0, 3, 4, 1)
        lay.addLayout(grid)

        self._new_question()

    def _new_question(self):
        text, value = make_sum(self.plan.toughness, self.rng)
        self.answer = value
        self.buffer = ""
        self.question.setText(text + " ＝ ?")
        self.progress.setText(tr("%s：%d問中 %d問 正解") %
                              (self.caption, self.total, self.cleared))
        self._refresh_entry()

    def _refresh_entry(self):
        self.entry.setText(self.buffer or "_")

    def _press(self, key: str):
        if key == "←":
            self.buffer = self.buffer[:-1]
        elif key == "−":
            self.buffer = self.buffer[1:] if self.buffer.startswith("-") else "-" + self.buffer
        elif len(self.buffer.lstrip("-")) < 6:
            self.buffer += key
        self._refresh_entry()

    def _submit(self):
        try:
            given = int(self.buffer)
        except ValueError:
            self.hint.setText(tr("数字を入力してください"))
            return
        if given == self.answer:
            self.cleared += 1
            self.hint.setText("")
            if self.cleared >= self.total:
                self._finish()
                return
            self._new_question()
        else:
            self.hint.setText(tr("ちがいます。正解は %d でした。") % self.answer)
            self._new_question()

    def keyPressEvent(self, event):
        text = event.text()
        if text.isdigit():
            self._press(text)
        elif event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            self._press("←")
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._submit()
        elif text == "-":
            self._press("−")
        else:
            super().keyPressEvent(event)


# --------------------------------------------------------------------------
# 順番タップ
# --------------------------------------------------------------------------
class OrderPad(GuardPad):
    """並べ替えられた記号を、提示された順にタップする。"""

    COUNTS = {Toughness.LIGHT: 4, Toughness.MIDDLE: 6, Toughness.HEAVY: 8}

    def __init__(self, plan, caption, tint, parent=None):
        super().__init__(plan, caption, tint, parent)
        self.rng = random.Random()
        self.total = max(1, plan.rounds)
        self.cleared = 0
        self.sequence = []
        self.step = 0
        self.buttons = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.progress = QLabel()
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        lay.addWidget(self.progress)

        self.target = QLabel()
        self.target.setAlignment(Qt.AlignCenter)
        self.target.setStyleSheet("font-size: 26px; letter-spacing: 10px;")
        lay.addWidget(self.target)

        self.hint = QLabel(" ")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet("color: %s; font-size: 12px;" % theme.WARN)
        lay.addWidget(self.hint)

        self.grid = QGridLayout()
        self.grid.setSpacing(6)
        lay.addLayout(self.grid)

        self._new_round()

    def _clear_grid(self):
        while self.grid.count():
            entry = self.grid.takeAt(0)
            widget = entry.widget()
            if widget:
                widget.deleteLater()
        self.buttons = []

    def _new_round(self):
        count = self.COUNTS.get(self.plan.toughness, 4)
        self.sequence = self.rng.sample(SYMBOLS, count)
        self.step = 0
        shuffled = self.sequence[:]
        self.rng.shuffle(shuffled)
        self.target.setText(" ".join(self.sequence))
        self.progress.setText(tr("%s：この順に押してください（%d問中 %d問）") %
                              (self.caption, self.total, self.cleared))
        self._clear_grid()
        cols = 4 if count > 4 else count
        for idx, symbol in enumerate(shuffled):
            btn = QPushButton(symbol)
            btn.setMinimumHeight(54)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("font-size: 22px;")
            btn.clicked.connect(lambda _=False, s=symbol, b=btn: self._tap(s, b))
            self.grid.addWidget(btn, idx // cols, idx % cols)
            self.buttons.append(btn)

    def _tap(self, symbol: str, button: QPushButton):
        if symbol == self.sequence[self.step]:
            button.setEnabled(False)
            button.setStyleSheet("font-size: 22px; color: %s;" % self.tint)
            self.step += 1
            self.hint.setText("")
            if self.step >= len(self.sequence):
                self.cleared += 1
                if self.cleared >= self.total:
                    self._finish()
                    return
                QTimer.singleShot(250, self._new_round)
        else:
            self.hint.setText(tr("順番が違います。最初からやり直しです。"))
            QTimer.singleShot(350, self._new_round)


# --------------------------------------------------------------------------
# 色・形マッチ
# --------------------------------------------------------------------------
class ShapeChip(QPushButton):
    """色と形を持つ選択肢。塗りは QSS ではなく描画で作る。"""

    def __init__(self, color: str, shape: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.shape = shape
        self.setMinimumSize(70, 70)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background: %s; border: 1px solid %s; border-radius: 12px;"
                           % (theme.SLATE, theme.LINE))

    def paintEvent(self, event):
        super().paintEvent(event)
        from PySide6.QtGui import QColor, QPainter, QPolygonF
        from PySide6.QtCore import QPointF, QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.color))
        side = min(self.width(), self.height()) * 0.52
        cx, cy = self.width() / 2, self.height() / 2
        box = QRectF(cx - side / 2, cy - side / 2, side, side)
        if self.shape == "circle":
            p.drawEllipse(box)
        elif self.shape == "square":
            p.drawRoundedRect(box, 4, 4)
        elif self.shape == "triangle":
            p.drawPolygon(QPolygonF([QPointF(cx, cy - side / 2),
                                     QPointF(cx + side / 2, cy + side / 2),
                                     QPointF(cx - side / 2, cy + side / 2)]))
        else:
            p.drawPolygon(QPolygonF([QPointF(cx, cy - side / 2),
                                     QPointF(cx + side / 2, cy),
                                     QPointF(cx, cy + side / 2),
                                     QPointF(cx - side / 2, cy)]))
        p.end()


class ShapePad(GuardPad):
    """提示された色と形の組み合わせに合う図形を選ぶ。"""

    def __init__(self, plan, caption, tint, parent=None):
        super().__init__(plan, caption, tint, parent)
        self.rng = random.Random()
        self.total = max(1, plan.rounds)
        self.cleared = 0
        self.want = ("", "")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.progress = QLabel()
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("color: %s; font-size: 12px;" % theme.TEXT_SUB)
        lay.addWidget(self.progress)

        self.target = QLabel()
        self.target.setAlignment(Qt.AlignCenter)
        self.target.setStyleSheet("font-size: 22px; font-weight: bold;")
        lay.addWidget(self.target)

        self.hint = QLabel(" ")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet("color: %s; font-size: 12px;" % theme.WARN)
        lay.addWidget(self.hint)

        self.grid = QGridLayout()
        self.grid.setSpacing(8)
        lay.addLayout(self.grid)

        self._new_round()

    def _clear_grid(self):
        while self.grid.count():
            entry = self.grid.takeAt(0)
            widget = entry.widget()
            if widget:
                widget.deleteLater()

    def _new_round(self):
        colors = list(COLOR_NAMES)
        shapes = list(SHAPE_NAMES)
        pool = []
        while len(pool) < 6:
            cand = (self.rng.choice(colors), self.rng.choice(shapes))
            if cand not in pool:
                pool.append(cand)
        self.want = pool[self.rng.randrange(len(pool))]
        self.rng.shuffle(pool)
        self.target.setText(tr("%s の %s を選んでください") %
                            (tr(COLOR_NAMES[self.want[0]]),
                             tr(SHAPE_NAMES[self.want[1]])))
        self.progress.setText(tr("%s：%d問中 %d問 正解") %
                              (self.caption, self.total, self.cleared))
        self._clear_grid()
        for idx, (color, shape) in enumerate(pool):
            chip = ShapeChip(color, shape)
            chip.clicked.connect(lambda _=False, c=color, s=shape: self._pick(c, s))
            self.grid.addWidget(chip, idx // 3, idx % 3)

    def _pick(self, color: str, shape: str):
        if (color, shape) == self.want:
            self.cleared += 1
            self.hint.setText("")
            if self.cleared >= self.total:
                self._finish()
                return
            self._new_round()
        else:
            self.hint.setText(tr("ちがいます。もう一度。"))
            self._new_round()


# --------------------------------------------------------------------------
# 生成
# --------------------------------------------------------------------------
_PADS = {
    Guard.TAP: TapPad,
    Guard.HOLD: HoldPad,
    Guard.SLIDE: SlidePad,
    Guard.ARITHMETIC: MathPad,
    Guard.ORDER_TAP: OrderPad,
    Guard.SHAPE_MATCH: ShapePad,
}


def build_pad(plan: GuardPlan, caption: str, tint: str = "",
              parent=None) -> GuardPad:
    return _PADS.get(plan.style, TapPad)(plan, caption, tint or theme.ACCENT,
                                         parent)


def describe(plan: GuardPlan) -> str:
    """設定内容を 1 行で説明する。"""
    base = plan.style.label
    if plan.style == Guard.HOLD:
        return tr("%s（%.1f秒）") % (base, plan.hold_seconds)
    if plan.style in (Guard.ARITHMETIC, Guard.SHAPE_MATCH):
        return tr("%s／%s／%d問") % (base, plan.toughness.label, max(1, plan.rounds))
    if plan.style == Guard.ORDER_TAP:
        return tr("%s／%s／%d問") % (base, plan.toughness.label, max(1, plan.rounds))
    return base
