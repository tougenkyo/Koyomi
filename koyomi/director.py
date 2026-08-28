"""時刻の見張りとスヌーズ状態の管理。

1 秒ごとに全アラームの次回時刻を見比べ、時が来たら ``due`` シグナルを出す。
実際に画面を出したり音を鳴らしたりするのは UI 側の役目で、
ここは「いつ鳴らすべきか」だけを受け持つ。
"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QObject, QTimer, Signal

from . import planner
from .models import Cycle, SnoozeOrigin, WakeItem


class SnoozeState:
    """スヌーズ中のアラーム 1 件分の記録。"""

    def __init__(self, uid: str, rounds: int, due_at: dt.datetime,
                 minutes: int, first_rang_at: dt.datetime):
        self.uid = uid
        self.rounds = rounds
        self.due_at = due_at
        self.minutes = minutes
        self.first_rang_at = first_rang_at


class RingDirector(QObject):
    """アラームの発火タイミングを司る。"""

    due = Signal(object, int)        # (WakeItem, スヌーズ回数 0=初回)
    tick = Signal()                  # 毎秒。一覧の相対時刻表示の更新用
    missed = Signal(list)            # 起動時に見つかった取りこぼし

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self._snoozes: dict = {}         # uid -> SnoozeState
        self._suspended: set = set()     # 鳴動中／画面表示中で二重発火させたくない uid
        self._last_check = dt.datetime.now()
        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._on_tick)

    # ---- 起動と停止 -------------------------------------------------------
    def start(self) -> None:
        self._last_check = dt.datetime.now()
        self._clock.start()

    def stop(self) -> None:
        self._clock.stop()

    # ---- 取りこぼしの補完 -------------------------------------------------
    def sweep_missed(self) -> list:
        """前回終了時から今までに鳴るはずだったアラームを拾う。"""
        window = max(0, self.vault.prefs.catch_up_window_minutes)
        if not window:
            return []
        now = dt.datetime.now()
        floor = now - dt.timedelta(minutes=window)
        start = floor
        if self.vault.last_seen:
            try:
                seen = dt.datetime.fromisoformat(self.vault.last_seen)
                start = max(floor, seen)
            except ValueError:
                pass
        found = []
        for item in self.vault.items:
            if not item.active:
                continue
            hits = planner.times_in_range(item, self.vault.almanac, start, now)
            if hits:
                found.append((item, hits[-1]))
        if found:
            self.missed.emit(found)
        return found

    def remember_now(self) -> None:
        self.vault.last_seen = dt.datetime.now().isoformat(timespec="seconds")

    # ---- スヌーズ ---------------------------------------------------------
    def snooze_state(self, uid: str):
        return self._snoozes.get(uid)

    def is_snoozing(self, uid: str) -> bool:
        return uid in self._snoozes

    def begin_snooze(self, item: WakeItem, rang_at: dt.datetime,
                     minutes: int | None = None) -> SnoozeState:
        """スヌーズを 1 段進める。"""
        prev = self._snoozes.get(item.uid)
        rounds = (prev.rounds if prev else 0) + 1
        span = minutes if minutes is not None else item.snooze.minutes
        span = max(1, min(1439, span))
        base = rang_at if item.snooze.origin == SnoozeOrigin.RING_START else dt.datetime.now()
        state = SnoozeState(
            uid=item.uid,
            rounds=rounds,
            due_at=base + dt.timedelta(minutes=span),
            minutes=span,
            first_rang_at=prev.first_rang_at if prev else rang_at,
        )
        self._snoozes[item.uid] = state
        self._suspended.discard(item.uid)
        return state

    def change_snooze_interval(self, uid: str, minutes: int) -> bool:
        state = self._snoozes.get(uid)
        if not state:
            return False
        span = max(1, min(1439, minutes))
        state.due_at = dt.datetime.now() + dt.timedelta(minutes=span)
        state.minutes = span
        return True

    def cancel_snooze(self, uid: str) -> None:
        self._snoozes.pop(uid, None)
        self._suspended.discard(uid)

    def snooze_rounds_left(self, item: WakeItem) -> int:
        """あと何回スヌーズできるか。無制限なら -1。"""
        if item.snooze.max_rounds <= 0:
            return -1
        state = self._snoozes.get(item.uid)
        used = state.rounds if state else 0
        return max(0, item.snooze.max_rounds - used)

    # ---- 鳴動中フラグ -----------------------------------------------------
    def hold(self, uid: str) -> None:
        self._suspended.add(uid)

    def release(self, uid: str) -> None:
        self._suspended.discard(uid)

    def is_held(self, uid: str) -> bool:
        return uid in self._suspended

    # ---- 発火後の後始末 ---------------------------------------------------
    def settle_after_stop(self, item: WakeItem) -> None:
        """停止操作を受けたあとの、繰り返し種別に応じた処理。"""
        self.cancel_snooze(item.uid)
        self.release(item.uid)
        item.last_fired_at = dt.datetime.now().isoformat(timespec="seconds")
        if item.skip_once:
            item.skip_once = False
        if item.repeat.cycle in (Cycle.SINGLE, Cycle.ON_DATE):
            item.active = False

    def consume_skip(self, item: WakeItem) -> None:
        """スキップ指定の日を通過したのでフラグを下ろす。"""
        item.skip_once = False

    # ---- 毎秒の判定 -------------------------------------------------------
    def _on_tick(self) -> None:
        now = dt.datetime.now()
        # 端末のスリープ復帰などで時計が飛んだ場合も、間の分を取りこぼさない
        gap_start = min(self._last_check, now)
        self._last_check = now

        # スヌーズの再発火が最優先
        for uid, state in list(self._snoozes.items()):
            if state.due_at <= now:
                item = self.vault.find(uid)
                if item is None:
                    self._snoozes.pop(uid, None)
                    continue
                if uid in self._suspended:
                    continue
                self._suspended.add(uid)
                self.due.emit(item, state.rounds)

        for item in self.vault.items:
            if not item.active or item.uid in self._suspended:
                continue
            if item.uid in self._snoozes:
                continue
            hits = planner.times_in_range(item, self.vault.almanac, gap_start, now)
            if not hits:
                continue
            if item.skip_once:
                self.consume_skip(item)
                item.last_fired_at = now.isoformat(timespec="seconds")
                continue
            self._suspended.add(item.uid)
            self.due.emit(item, 0)

        self.tick.emit()
