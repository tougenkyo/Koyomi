"""同梱アラーム音の生成。

音源ファイルを配布物に同梱するのではなく、初回起動時にその場で
合成して WAV を書き出す。標準ライブラリの ``wave`` と ``math`` だけを使う。
"""
from __future__ import annotations

import array
import math
import os
import random
import struct
import wave

from .vault import glyphs_dir, tones_dir

SAMPLE_RATE = 44100
PEAK = 20000

# 表示名 -> 内部キー
TONE_CATALOG = {
    "kizashi": "きざし（やわらかい）",
    "shizuku": "しずく（水滴）",
    "kane": "かね（鐘）",
    "hibiki": "ひびき（二音）",
    "asaichi": "あさいち（強め）",
    "seiren": "せいれん（サイレン）",
}


# --------------------------------------------------------------------------
# 波形の部品
# --------------------------------------------------------------------------
def _blank(seconds: float) -> array.array:
    return array.array("d", [0.0] * int(SAMPLE_RATE * seconds))


def _mix_partial(buf: array.array, start: float, length: float, freq: float,
                 gain: float, decay: float, wobble: float = 0.0) -> None:
    """減衰する正弦波を 1 本、既存バッファに足し込む。"""
    begin = int(start * SAMPLE_RATE)
    span = int(length * SAMPLE_RATE)
    if begin >= len(buf):
        return
    two_pi = 2.0 * math.pi
    for n in range(span):
        idx = begin + n
        if idx >= len(buf):
            break
        t = n / SAMPLE_RATE
        env = math.exp(-decay * t)
        # 立ち上がりを 8ms だけなだらかにしてプチノイズを防ぐ
        if t < 0.008:
            env *= t / 0.008
        f = freq * (1.0 + wobble * math.sin(two_pi * 5.0 * t))
        buf[idx] += gain * env * math.sin(two_pi * f * t)


def _mix_square(buf: array.array, start: float, length: float, freq: float,
                gain: float) -> None:
    """矩形波に近い、はっきりしたビープ。"""
    begin = int(start * SAMPLE_RATE)
    span = int(length * SAMPLE_RATE)
    two_pi = 2.0 * math.pi
    for n in range(span):
        idx = begin + n
        if idx >= len(buf):
            break
        t = n / SAMPLE_RATE
        env = 1.0
        if t < 0.01:
            env = t / 0.01
        elif t > length - 0.02:
            env = max(0.0, (length - t) / 0.02)
        # 奇数倍音を 3 本重ねた擬似矩形波
        s = (math.sin(two_pi * freq * t)
             + math.sin(two_pi * freq * 3 * t) / 3.0
             + math.sin(two_pi * freq * 5 * t) / 5.0)
        buf[idx] += gain * env * s * 0.7


def _sweep(buf: array.array, start: float, length: float, f_lo: float,
           f_hi: float, gain: float) -> None:
    """周波数が上下するサイレン風の音。"""
    begin = int(start * SAMPLE_RATE)
    span = int(length * SAMPLE_RATE)
    phase = 0.0
    two_pi = 2.0 * math.pi
    for n in range(span):
        idx = begin + n
        if idx >= len(buf):
            break
        t = n / SAMPLE_RATE
        ratio = 0.5 - 0.5 * math.cos(two_pi * t / length * 2)
        freq = f_lo + (f_hi - f_lo) * ratio
        phase += two_pi * freq / SAMPLE_RATE
        env = min(1.0, t / 0.05, (length - t) / 0.05)
        buf[idx] += gain * max(0.0, env) * math.sin(phase)


def _write_wave(path: str, buf: array.array) -> None:
    top = max((abs(v) for v in buf), default=1.0) or 1.0
    scale = PEAK / top
    frames = array.array("h", (int(max(-32767, min(32767, v * scale))) for v in buf))
    with wave.open(path, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(frames.tobytes())


# --------------------------------------------------------------------------
# 各音のレシピ
# --------------------------------------------------------------------------
def _make_kizashi() -> array.array:
    """やわらかく上がっていく 4 音のアルペジオ。"""
    buf = _blank(4.0)
    scale = [523.25, 659.25, 783.99, 1046.50]
    for i, base in enumerate(scale):
        at = 0.35 * i
        _mix_partial(buf, at, 2.4, base, 0.55, 2.4)
        _mix_partial(buf, at, 1.6, base * 2, 0.18, 3.6)
    for i, base in enumerate(reversed(scale)):
        at = 2.0 + 0.35 * i
        _mix_partial(buf, at, 2.0, base, 0.45, 2.6)
    return buf


def _make_shizuku() -> array.array:
    """短い水滴のような音を不規則に置く。"""
    buf = _blank(4.0)
    rng = random.Random(20260827)
    at = 0.0
    while at < 3.6:
        freq = rng.choice([880.0, 1174.7, 1318.5, 1567.98])
        _mix_partial(buf, at, 0.7, freq, 0.7, 9.0, wobble=0.004)
        _mix_partial(buf, at, 0.4, freq * 1.5, 0.2, 14.0)
        at += rng.uniform(0.28, 0.55)
    return buf


def _make_kane() -> array.array:
    """倍音を重ねた鐘。2 回打つ。"""
    buf = _blank(5.0)
    partials = [(1.0, 0.60, 1.1), (2.01, 0.30, 1.6), (2.98, 0.18, 2.2),
                (4.12, 0.10, 3.0), (5.43, 0.06, 3.8)]
    for strike in (0.0, 2.4):
        for mult, gain, decay in partials:
            _mix_partial(buf, strike, 2.6, 440.0 * mult, gain, decay, wobble=0.002)
    return buf


def _make_hibiki() -> array.array:
    """高低 2 音を交互に鳴らす、聞き取りやすいパターン。"""
    buf = _blank(4.0)
    at = 0.0
    while at < 3.7:
        _mix_square(buf, at, 0.16, 988.0, 0.5)
        _mix_square(buf, at + 0.22, 0.16, 740.0, 0.5)
        at += 0.62
    return buf


def _make_asaichi() -> array.array:
    """3 連打を繰り返す、強めの目覚まし。"""
    buf = _blank(4.0)
    at = 0.0
    while at < 3.6:
        for k in range(3):
            _mix_square(buf, at + k * 0.13, 0.10, 1180.0, 0.62)
        at += 0.85
    return buf


def _make_seiren() -> array.array:
    """うねるサイレン。"""
    buf = _blank(4.0)
    _sweep(buf, 0.0, 4.0, 620.0, 1180.0, 0.6)
    _sweep(buf, 0.0, 4.0, 310.0, 590.0, 0.2)
    return buf


_RECIPES = {
    "kizashi": _make_kizashi,
    "shizuku": _make_shizuku,
    "kane": _make_kane,
    "hibiki": _make_hibiki,
    "asaichi": _make_asaichi,
    "seiren": _make_seiren,
}


# --------------------------------------------------------------------------
# 外部インターフェース
# --------------------------------------------------------------------------
def tone_path(key: str) -> str:
    return os.path.join(tones_dir(), key + ".wav")


def ensure_tones(force: bool = False) -> dict:
    """未生成の同梱音を書き出し、{キー: ファイルパス} を返す。"""
    made = {}
    for key, recipe in _RECIPES.items():
        path = tone_path(key)
        if force or not os.path.exists(path) or os.path.getsize(path) < 1024:
            _write_wave(path, recipe())
        made[key] = path
    return made


def resolve(key: str) -> str:
    """内蔵音キーからファイルパスを得る。未知のキーは既定音に落とす。"""
    if key not in _RECIPES:
        key = "kizashi"
    path = tone_path(key)
    if not os.path.exists(path):
        _write_wave(path, _RECIPES[key]())
    return path


def _png_bytes(width: int, height: int, shade) -> bytes:
    """``shade(x, y) -> (r, g, b, a)`` から PNG バイト列を組み立てる。"""
    import zlib

    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row += bytes(shade(x, y))
        rows.append(bytes(row))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def _hex_to_rgb(value: str) -> tuple:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _write_glyph(name: str, width: int, height: int, shade) -> str:
    path = os.path.join(glyphs_dir(), name)
    if not os.path.exists(path):
        with open(path, "wb") as fh:
            fh.write(_png_bytes(width, height, shade))
    return path


def ensure_glyphs(arrow_color: str = "#9aa4b5", mark_color: str = "#1b1f27") -> dict:
    """コンボボックスの矢印とチェックマークを描き出す。"""
    ar, ag, ab = _hex_to_rgb(arrow_color)
    mr, mg, mb = _hex_to_rgb(mark_color)
    w, h = 11, 7

    def down(x, y):
        # 上辺が広い三角形
        span = (h - 1 - y) * (w / 2.0) / (h - 1)
        return (ar, ag, ab, 255) if abs(x - (w - 1) / 2.0) <= span else (0, 0, 0, 0)

    def up(x, y):
        span = y * (w / 2.0) / (h - 1)
        return (ar, ag, ab, 255) if abs(x - (w - 1) / 2.0) <= span else (0, 0, 0, 0)

    def tick(x, y):
        # 「レ」の字。2 本の線分からの距離で判定する
        def near(x1, y1, x2, y2, thick):
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy) or 1.0
            t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (length * length)))
            return math.hypot(x - (x1 + dx * t), y - (y1 + dy * t)) <= thick
        if near(2.5, 6.5, 4.8, 9.2, 1.3) or near(4.8, 9.2, 9.5, 3.0, 1.3):
            return (mr, mg, mb, 255)
        return (0, 0, 0, 0)

    # 色を変えたら別ファイルになるよう、名前に色を織り込む
    a = arrow_color.lstrip("#")
    m = mark_color.lstrip("#")
    return {
        "down": _write_glyph("arrow_down-%s.png" % a, w, h, down),
        "up": _write_glyph("arrow_up-%s.png" % a, w, h, up),
        "tick": _write_glyph("tick-%s.png" % m, 13, 13, tick),
    }


def app_icon_png(size: int = 256) -> bytes:
    """アプリアイコンを PNG バイト列として組み立てる。

    外部素材を持ち込まずに済むよう、円弧と目盛りだけの図形を
    ここで描いて zlib 圧縮した PNG を直接生成する。
    """
    import zlib

    cx = cy = size / 2.0
    outer = size * 0.40
    inner = size * 0.34
    rows = []
    for y in range(size):
        row = bytearray([0])  # フィルタタイプ 0
        for x in range(size):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            dist = math.hypot(dx, dy)
            r = g = b = 0
            a = 0
            if dist <= outer:
                if dist >= inner:
                    r, g, b, a = 0xF6, 0xB1, 0x3C, 255      # 外周リング
                else:
                    r, g, b, a = 0x1E, 0x24, 0x33, 255      # 文字盤
            # ベルの上に付く小さな石突き
            if abs(dx) < size * 0.045 and -outer - size * 0.10 < dy < -outer + size * 0.02:
                r, g, b, a = 0xF6, 0xB1, 0x3C, 255
            # 針（短針・長針）
            if a and dist < inner * 0.82:
                ang = math.atan2(dy, dx)
                for target, reach, width in ((-math.pi / 2, 0.62, 0.055),
                                             (-math.pi / 6, 0.80, 0.040)):
                    diff = abs(((ang - target + math.pi) % (2 * math.pi)) - math.pi)
                    if diff < width and dist < inner * reach:
                        r, g, b = 0xFF, 0xF3, 0xDE
            if a and dist < size * 0.030:
                r, g, b = 0xF6, 0xB1, 0x3C
            row += bytes((r, g, b, a))
        rows.append(bytes(row))

    raw = b"".join(rows)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def app_icon_ico(sizes=(16, 32, 48, 256)) -> bytes:
    """ショートカット用の ICO を組み立てる。

    Windows のショートカットは PNG を受け付けないので、同じ絵を
    ICO の器に入れ直す。Vista 以降は中身が PNG のままでよい。
    """
    shots = [app_icon_png(n) for n in sizes]
    head = struct.pack("<HHH", 0, 1, len(shots))        # 予約, 種類=アイコン, 枚数
    offset = len(head) + 16 * len(shots)
    entries, body = [], []
    for size, shot in zip(sizes, shots):
        side = 0 if size >= 256 else size                # 256 は 0 と書く決まり
        entries.append(struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32,
                                   len(shot), offset))
        offset += len(shot)
        body.append(shot)
    return head + b"".join(entries) + b"".join(body)


def ensure_ico() -> str:
    path = os.path.normpath(os.path.join(tones_dir(), "..", "appicon.ico"))
    if not os.path.exists(path):
        with open(path, "wb") as fh:
            fh.write(app_icon_ico())
    return path


def ensure_icon() -> str:
    path = os.path.join(tones_dir(), "..", "appicon.png")
    path = os.path.normpath(path)
    if not os.path.exists(path):
        with open(path, "wb") as fh:
            fh.write(app_icon_png(256))
    return path
