"""配色の見本帳。

下地 3 系統 × さし色 9 種 = 27 通り。
補助的な色（選択中の背景、さし色の上に載せる文字色、グループの色分け）は
手で並べずに、下地とさし色から計算して作る。
"""
from __future__ import annotations
from ..i18n import tr


def _rgb(value: str) -> tuple:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def _blend(a: str, b: str, ratio: float) -> str:
    """``a`` に ``b`` を ``ratio`` の割合で混ぜる。"""
    x, y = _rgb(a), _rgb(b)
    return _hex(x[i] + (y[i] - x[i]) * ratio for i in range(3))


def _luma(value: str) -> float:
    r, g, b = _rgb(value)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


# --------------------------------------------------------------------------
# 下地
# --------------------------------------------------------------------------
SURFACES = {
    "yoichi": {
        "label": "夜市",
        "dark": True,
        "INK": "#1b1f27", "SLATE": "#242a35", "SLATE_HI": "#2e3542",
        "LINE": "#39414f", "TEXT": "#f2f4f8", "TEXT_SUB": "#9aa4b5",
        "SWITCH_OFF": "#39414f",
    },
    "sumibi": {
        "label": "炭火",
        "dark": True,
        "INK": "#1d1c1b", "SLATE": "#272524", "SLATE_HI": "#333130",
        "LINE": "#433f3d", "TEXT": "#f1eeea", "TEXT_SUB": "#a8a19a",
        "SWITCH_OFF": "#433f3d",
    },
    "hakua": {
        "label": "白亜",
        "dark": False,
        "INK": "#eef1f6", "SLATE": "#ffffff", "SLATE_HI": "#e3e8f0",
        "LINE": "#c8d0dd", "TEXT": "#1b2230", "TEXT_SUB": "#5c6675",
        "SWITCH_OFF": "#b7c0cf",
    },
}

SURFACE_ORDER = ("yoichi", "sumibi", "hakua")

# --------------------------------------------------------------------------
# さし色
# --------------------------------------------------------------------------
ACCENTS = {
    "kohaku": ("琥珀", "#f6b13c"),
    "sora": ("空", "#6aa9ff"),
    "wakakusa": ("若草", "#5fce9b"),
    "fuji": ("藤", "#c89bf0"),
    "sango": ("珊瑚", "#ef8f6b"),
    "beni": ("紅", "#e8636e"),
    "tsuyukusa": ("露草", "#7b8cff"),
    "yamabuki": ("山吹", "#ffd34d"),
    "aotake": ("青竹", "#4fc4c4"),
}

ACCENT_ORDER = ("kohaku", "sora", "wakakusa", "fuji", "sango",
                "beni", "tsuyukusa", "yamabuki", "aotake")

# グループ 5 つの色分けに使うさし色
GROUP_SOURCE = ("kohaku", "sora", "wakakusa", "fuji", "sango")


# --------------------------------------------------------------------------
def _build(surface_key: str, accent_key: str) -> dict:
    surface = SURFACES[surface_key]
    accent_label, accent = ACCENTS[accent_key]
    dark = surface["dark"]

    palette = {k: v for k, v in surface.items()
               if k not in ("label", "dark")}
    palette["key"] = "%s-%s" % (surface_key, accent_key)
    palette["label"] = (surface["label"], accent_label)   # 表示時に訳す
    palette["dark"] = dark
    palette["ACCENT"] = accent
    # 選択中の背景。下地に近づけて、文字が読める濃さで止める
    palette["ACCENT_DIM"] = _blend(accent, palette["INK"], 0.55 if dark else 0.25)
    # さし色の上に載せる文字。明るいさし色なら黒、暗ければ白
    palette["ON_ACCENT"] = "#16191f" if _luma(accent) > 0.55 else "#ffffff"

    if dark:
        palette["GOOD"] = "#5fce9b"
        palette["WARN"] = "#ef6b6b"
        palette["COOL"] = "#6aa9ff"
    else:
        palette["GOOD"] = "#1f8f63"
        palette["WARN"] = "#cf3b46"
        palette["COOL"] = "#2f6fd0"

    tints = {}
    for slot, name in zip("abcde", GROUP_SOURCE):
        base = ACCENTS[name][1]
        tints[slot] = base if dark else _blend(base, "#000000", 0.28)
    palette["GROUP_TINTS"] = tints
    return palette


PALETTES = {}
for _s in SURFACE_ORDER:
    for _a in ACCENT_ORDER:
        _p = _build(_s, _a)
        PALETTES[_p["key"]] = _p

DEFAULT_KEY = "yoichi-kohaku"


def catalog() -> dict:
    """{キー: 表示名} を並び順どおりに返す。"""
    return {key: "%s・%s" % (tr(PALETTES[key]["label"][0]),
                            tr(PALETTES[key]["label"][1]))
            for key in PALETTES}


def get(key: str) -> dict:
    return PALETTES.get(key) or PALETTES[DEFAULT_KEY]
