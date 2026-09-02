"""雪花演算法 ID 產生器（64 位元）。

格式：1 bit 符號 + 41 bit 時間戳（毫秒）+ 10 bit 機器 ID + 12 bit 序列號。
產生的 ID 為無符號 64 位元整數，作為 people_count_hourly 的主鍵。
"""

from __future__ import annotations

import threading
import time

# 自訂紀元（2023-01-01 00:00:00 UTC），用於縮短時間戳位數
_EPOCH = 1672531200000

_WORKER_ID_BITS = 10
_SEQUENCE_BITS = 12

_MAX_WORKER_ID = (1 << _WORKER_ID_BITS) - 1
_MAX_SEQUENCE = (1 << _SEQUENCE_BITS) - 1

_WORKER_SHIFT = _SEQUENCE_BITS
_TIMESTAMP_SHIFT = _WORKER_ID_BITS + _SEQUENCE_BITS


class Snowflake:
    """執行緒安全的雪花 ID 產生器。"""

    def __init__(self, worker_id: int = 1, epoch: int = _EPOCH):
        if not (0 <= worker_id <= _MAX_WORKER_ID):
            raise ValueError(f"worker_id must be in [0, {_MAX_WORKER_ID}]")
        self._worker_id = worker_id
        self._epoch = epoch
        self._sequence = 0
        self._last_ts = -1
        self._lock = threading.Lock()

    def _current_millis(self) -> int:
        return int(time.time() * 1000)

    def _wait_next_millis(self, last_ts: int) -> int:
        ts = self._current_millis()
        while ts <= last_ts:
            ts = self._current_millis()
        return ts

    def next_id(self) -> int:
        with self._lock:
            ts = self._current_millis()
            if ts < self._last_ts:
                # 時鐘回撥，等待追上最後時間戳
                ts = self._wait_next_millis(self._last_ts)
            if ts == self._last_ts:
                self._sequence = (self._sequence + 1) & _MAX_SEQUENCE
                if self._sequence == 0:
                    ts = self._wait_next_millis(self._last_ts)
            else:
                self._sequence = 0
            self._last_ts = ts
            return (
                ((ts - self._epoch) << _TIMESTAMP_SHIFT)
                | (self._worker_id << _WORKER_SHIFT)
                | self._sequence
            )


# 模組級單例，供全專案共用
_default_snowflake = Snowflake()


def next_id() -> int:
    """產生下一個雪花 ID。"""
    return _default_snowflake.next_id()


def init_snowflake(worker_id: int) -> None:
    """以指定的 worker_id 重建模組級單例。

    多實例部署時，於應用啟動（lifespan）依設定（SNOWFLAKE_WORKER_ID）呼叫，
    確保各實例使用不同的 worker_id，避免產生重複 ID。
    """
    global _default_snowflake
    _default_snowflake = Snowflake(worker_id=worker_id)
