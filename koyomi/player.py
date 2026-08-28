"""音の再生。

再生そのものは pygame.mixer に任せる。pygame が無い環境では
Windows 標準の winsound へ、それも無ければ無音へ段階的に落ちる。
"""
from __future__ import annotations

import os
import random
import threading

from .models import SoundPlan, ToneKind
from .tonesmith import resolve as resolve_builtin
from .i18n import tr

AUDIO_SUFFIXES = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".opus")

try:                                   # pragma: no cover - 環境依存
    import pygame
    _HAS_PYGAME = True
except ImportError:                    # pragma: no cover
    pygame = None
    _HAS_PYGAME = False

try:                                   # pragma: no cover - Windows 限定
    import winsound
except ImportError:                    # pragma: no cover
    winsound = None


def pick_from_folder(folder: str) -> str:
    """フォルダ内の音声ファイルから 1 本くじ引きする。"""
    if not folder or not os.path.isdir(folder):
        return ""
    pool = []
    for name in os.listdir(folder):
        if name.lower().endswith(AUDIO_SUFFIXES):
            full = os.path.join(folder, name)
            if os.path.isfile(full):
                pool.append(full)
    return random.choice(pool) if pool else ""


def resolve_source(plan: SoundPlan) -> tuple:
    """(再生するファイルパス, 利用者に伝える注意文) を返す。"""
    if plan.kind == ToneKind.SILENT:
        return "", ""
    if plan.kind == ToneKind.BUILTIN:
        return resolve_builtin(plan.source), ""
    if plan.kind == ToneKind.FILE:
        if plan.source and os.path.isfile(plan.source):
            return plan.source, ""
        return resolve_builtin("kizashi"), tr("指定した音声ファイルが見つからないため、内蔵音で鳴らしています。")
    if plan.kind == ToneKind.FOLDER_PICK:
        hit = pick_from_folder(plan.source)
        if hit:
            return hit, ""
        return resolve_builtin("kizashi"), tr("フォルダに再生できる音声が無いため、内蔵音で鳴らしています。")
    return resolve_builtin("kizashi"), ""


class SoundEngine:
    """1 度に 1 つの音だけを鳴らす、単純な再生係。"""

    def __init__(self):
        self.ready = False
        self._fallback_thread = None
        self._fallback_stop = threading.Event()
        self._current = ""
        self._notice = ""
        if _HAS_PYGAME:
            try:
                pygame.mixer.pre_init(44100, -16, 2, 1024)
                pygame.mixer.init()
                self.ready = True
            except Exception:            # pragma: no cover - 音源デバイス無し等
                self.ready = False

    # ---- 情報 -------------------------------------------------------------
    @property
    def notice(self) -> str:
        return self._notice

    @property
    def current_source(self) -> str:
        return self._current

    def is_playing(self) -> bool:
        if self.ready:
            try:
                return bool(pygame.mixer.music.get_busy())
            except Exception:
                return False
        return bool(self._fallback_thread and self._fallback_thread.is_alive())

    # ---- 再生 -------------------------------------------------------------
    def start(self, plan: SoundPlan) -> str:
        """``plan`` に従って鳴らし始める。注意文があれば返す。"""
        self.stop()
        path, notice = resolve_source(plan)
        self._notice = notice
        self._current = path
        if not path:
            return notice

        volume = max(0, min(100, plan.volume)) / 100.0
        fade_ms = max(0, plan.fade_seconds) * 1000
        loops = -1 if plan.loop else 0

        if self.ready:
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(volume)
                pygame.mixer.music.play(loops=loops, fade_ms=fade_ms)
                return notice
            except Exception:
                self._notice = tr("この音声ファイルは再生できませんでした。内蔵音に切り替えます。")
                try:
                    pygame.mixer.music.load(resolve_builtin("kizashi"))
                    pygame.mixer.music.set_volume(volume)
                    pygame.mixer.music.play(loops=loops, fade_ms=fade_ms)
                    return self._notice
                except Exception:
                    pass
        self._start_fallback(path, loops == -1)
        return self._notice

    def set_volume(self, percent: int) -> None:
        if self.ready:
            try:
                pygame.mixer.music.set_volume(max(0, min(100, percent)) / 100.0)
            except Exception:
                pass

    def stop(self) -> None:
        if self.ready:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except Exception:
                pass
        self._fallback_stop.set()
        if self._fallback_thread and self._fallback_thread.is_alive():
            self._fallback_thread.join(timeout=0.5)
        self._fallback_thread = None
        self._current = ""

    def shutdown(self) -> None:
        self.stop()
        if self.ready:
            try:
                pygame.mixer.quit()
            except Exception:
                pass
            self.ready = False

    # ---- pygame が使えないときの逃げ道 ------------------------------------
    def _start_fallback(self, path: str, loop: bool) -> None:
        if winsound is None or not path.lower().endswith(".wav"):
            self._notice = self._notice or tr("音声を再生できる仕組みが見つかりませんでした。")
            return
        self._fallback_stop = threading.Event()

        def run():
            flags = winsound.SND_FILENAME | winsound.SND_ASYNC
            if loop:
                flags |= winsound.SND_LOOP
            try:
                winsound.PlaySound(path, flags)
            except Exception:
                return
            self._fallback_stop.wait()
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

        self._fallback_thread = threading.Thread(target=run, daemon=True)
        self._fallback_thread.start()
