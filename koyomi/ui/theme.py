"""配色とスタイルシート。素材は使わず、色と角丸だけで組み立てる。

色は palettes.py の見本帳から選んで、このモジュールの変数に流し込む。
各画面は ``theme.ACCENT`` のように参照時に読むので、``apply()`` を呼んだあとに
作られたウィジェットには新しい色が乗る。すでに開いている画面については、
呼び出し側が作り直す。
"""
from __future__ import annotations

from . import palettes

# ---- 現在の色（apply() で入れ替わる）-------------------------------------
CURRENT = palettes.DEFAULT_KEY
DARK = True

INK = "#1b1f27"
SLATE = "#242a35"
SLATE_HI = "#2e3542"
LINE = "#39414f"
TEXT = "#f2f4f8"
TEXT_SUB = "#9aa4b5"
SWITCH_OFF = "#39414f"
ACCENT = "#f6b13c"
ACCENT_DIM = "#8a6221"
ON_ACCENT = "#16191f"
GOOD = "#5fce9b"
WARN = "#ef6b6b"
COOL = "#6aa9ff"
GROUP_TINTS = {"a": "#f6b13c", "b": "#6aa9ff", "c": "#5fce9b",
               "d": "#c89bf0", "e": "#ef8f6b"}


def apply(key: str) -> str:
    """見本帳から 1 つ選んで、この先に作る画面へ効かせる。"""
    global CURRENT, DARK, INK, SLATE, SLATE_HI, LINE, TEXT, TEXT_SUB
    global SWITCH_OFF, ACCENT, ACCENT_DIM, ON_ACCENT, GOOD, WARN, COOL, GROUP_TINTS
    palette = palettes.get(key)
    CURRENT = palette["key"]
    DARK = palette["dark"]
    INK = palette["INK"]
    SLATE = palette["SLATE"]
    SLATE_HI = palette["SLATE_HI"]
    LINE = palette["LINE"]
    TEXT = palette["TEXT"]
    TEXT_SUB = palette["TEXT_SUB"]
    SWITCH_OFF = palette["SWITCH_OFF"]
    ACCENT = palette["ACCENT"]
    ACCENT_DIM = palette["ACCENT_DIM"]
    ON_ACCENT = palette["ON_ACCENT"]
    GOOD = palette["GOOD"]
    WARN = palette["WARN"]
    COOL = palette["COOL"]
    GROUP_TINTS = dict(palette["GROUP_TINTS"])
    return CURRENT


def group_tint(key: str) -> str:
    return GROUP_TINTS.get(key, ACCENT)


def catalog() -> dict:
    return palettes.catalog()


def hover_tint() -> str:
    """ボタンなどに重ねる、ほんの少し持ち上げた色。"""
    return palettes._blend(SLATE_HI, TEXT, 0.10)


def sunken_tint() -> str:
    return palettes._blend(SLATE_HI, INK, 0.45)


_TEMPLATE = """
* { font-family: "Yu Gothic UI", "Meiryo", "Segoe UI", sans-serif; }

QWidget { background: %(INK)s; color: %(TEXT)s; font-size: 13px; }

/* ラベルは常に下地を透かす。カードの上に置いても四角く浮かないように。 */
QLabel, QCheckBox, QRadioButton, QGroupBox { background: transparent; }

QToolTip { background: %(SLATE_HI)s; color: %(TEXT)s; border: 1px solid %(LINE)s;
           padding: 4px 6px; border-radius: 4px; }

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: %(LINE)s; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: %(TEXT_SUB)s; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: %(LINE)s; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QPushButton {
    background: %(SLATE_HI)s; color: %(TEXT)s; border: 1px solid %(LINE)s;
    border-radius: 8px; padding: 7px 14px;
}
QPushButton:hover { background: %(HOVER)s; }
QPushButton:pressed { background: %(SUNKEN)s; }
QPushButton:disabled { color: %(TEXT_SUB)s; background: %(SLATE)s; }
QPushButton[tone="accent"] {
    background: %(ACCENT)s; color: %(ON_ACCENT)s; border: none; font-weight: bold;
}
QPushButton[tone="accent"]:hover { background: %(ACCENT_HOT)s; }
QPushButton[tone="danger"] { background: %(WARN)s; color: %(ON_WARN)s; border: none; }
QPushButton[tone="ghost"] { background: transparent; border: 1px solid %(LINE)s; }
QPushButton[tone="ghost"]:hover { background: %(SLATE_HI)s; }
QPushButton[tone="flat"] { background: transparent; border: none; color: %(TEXT_SUB)s; }
QPushButton[tone="flat"]:hover { color: %(TEXT)s; }

QLineEdit, QSpinBox, QComboBox, QDateEdit, QTimeEdit, QDateTimeEdit,
QDoubleSpinBox, QPlainTextEdit, QTextEdit {
    background: %(SLATE)s; border: 1px solid %(LINE)s; border-radius: 7px;
    padding: 6px 8px; selection-background-color: %(ACCENT_DIM)s;
    selection-color: %(TEXT)s;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QDateEdit:focus,
QTimeEdit:focus, QDateTimeEdit:focus { border: 1px solid %(ACCENT)s; }

QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: url(%(ARROW_DOWN)s); width: 11px; height: 7px;
                        margin-right: 7px; }
QComboBox QAbstractItemView {
    background: %(SLATE_HI)s; border: 1px solid %(LINE)s; color: %(TEXT)s;
    selection-background-color: %(ACCENT_DIM)s; outline: none;
}

QSpinBox::up-button, QDoubleSpinBox::up-button, QTimeEdit::up-button,
QDateEdit::up-button, QDateTimeEdit::up-button {
    subcontrol-origin: border; subcontrol-position: top right; width: 20px;
    background: %(SLATE_HI)s; border-left: 1px solid %(LINE)s;
    border-top-right-radius: 6px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button, QTimeEdit::down-button,
QDateEdit::down-button, QDateTimeEdit::down-button {
    subcontrol-origin: border; subcontrol-position: bottom right; width: 20px;
    background: %(SLATE_HI)s; border-left: 1px solid %(LINE)s;
    border-bottom-right-radius: 6px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QTimeEdit::up-button:hover, QDateEdit::up-button:hover,
QDateTimeEdit::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover,
QTimeEdit::down-button:hover, QDateEdit::down-button:hover,
QDateTimeEdit::down-button:hover { background: %(HOVER)s; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QTimeEdit::up-arrow,
QDateEdit::up-arrow, QDateTimeEdit::up-arrow {
    image: url(%(ARROW_UP)s); width: 11px; height: 7px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QTimeEdit::down-arrow,
QDateEdit::down-arrow, QDateTimeEdit::down-arrow {
    image: url(%(ARROW_DOWN)s); width: 11px; height: 7px;
}

QCheckBox, QRadioButton { spacing: 7px; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }
QCheckBox::indicator { border: 1px solid %(LINE)s; border-radius: 4px; background: %(SLATE)s; }
QCheckBox::indicator:checked {
    background: %(ACCENT)s; border-color: %(ACCENT)s; image: url(%(TICK)s);
}
QRadioButton::indicator { border: 1px solid %(LINE)s; border-radius: 8px; background: %(SLATE)s; }
QRadioButton::indicator:checked { background: %(ACCENT)s; border-color: %(ACCENT)s; }

QGroupBox {
    border: 1px solid %(LINE)s; border-radius: 10px; margin-top: 14px; padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 5px; color: %(TEXT_SUB)s;
}

QTabWidget::pane { border: 1px solid %(LINE)s; border-radius: 10px; top: -1px; }
QTabBar::tab {
    background: transparent; color: %(TEXT_SUB)s; padding: 8px 16px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: %(TEXT)s; border-bottom: 2px solid %(ACCENT)s; }

QSlider::groove:horizontal { height: 5px; background: %(LINE)s; border-radius: 3px; }
QSlider::sub-page:horizontal { background: %(ACCENT)s; border-radius: 3px; }
QSlider::handle:horizontal {
    background: %(TEXT)s; width: 15px; height: 15px; margin: -6px 0; border-radius: 8px;
}

QListWidget, QTableWidget, QTreeWidget {
    background: %(SLATE)s; border: 1px solid %(LINE)s; border-radius: 8px; outline: none;
}
QListWidget::item { padding: 6px; border-radius: 5px; }
QListWidget::item:selected { background: %(ACCENT_DIM)s; color: %(TEXT)s; }

QHeaderView::section {
    background: %(SLATE_HI)s; color: %(TEXT_SUB)s; border: none;
    border-bottom: 1px solid %(LINE)s; padding: 6px;
}

QMenu { background: %(SLATE_HI)s; border: 1px solid %(LINE)s; padding: 5px; }
QMenu::item { padding: 6px 22px; border-radius: 5px; }
QMenu::item:selected { background: %(ACCENT_DIM)s; }
QMenu::separator { height: 1px; background: %(LINE)s; margin: 4px 8px; }

QCalendarWidget QWidget { background: %(SLATE)s; }
QCalendarWidget QAbstractItemView:enabled {
    background: %(SLATE)s; color: %(TEXT)s; selection-background-color: %(ACCENT_DIM)s;
}
QCalendarWidget QToolButton { background: transparent; color: %(TEXT)s; }
QCalendarWidget QToolButton::menu-indicator { image: none; }
"""


def stylesheet() -> str:
    """描き出した小さな図版のパスを埋め込んで、完成した QSS を返す。"""
    from ..tonesmith import ensure_glyphs

    glyphs = ensure_glyphs(TEXT_SUB, ON_ACCENT)
    return _TEMPLATE % {
        "INK": INK, "SLATE": SLATE, "SLATE_HI": SLATE_HI, "LINE": LINE,
        "TEXT": TEXT, "TEXT_SUB": TEXT_SUB, "ACCENT": ACCENT,
        "ACCENT_DIM": ACCENT_DIM, "WARN": WARN, "ON_ACCENT": ON_ACCENT,
        "ON_WARN": "#ffffff" if palettes._luma(WARN) < 0.6 else "#1b1f27",
        "ACCENT_HOT": palettes._blend(ACCENT, "#ffffff", 0.22),
        "HOVER": hover_tint(),
        "SUNKEN": sunken_tint(),
        "ARROW_DOWN": glyphs["down"].replace("\\", "/"),
        "ARROW_UP": glyphs["up"].replace("\\", "/"),
        "TICK": glyphs["tick"].replace("\\", "/"),
    }
