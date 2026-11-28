"""Bounded force-stream health and idle baseline helpers."""
from dataclasses import dataclass
from math import isfinite

from .force_signal import Sample


@dataclass
class SampleHealth:
    last_mcu: float | None = None
    last_host: float | None = None

    def note(self, timestamp: float, now: float, *,
             estimated: float | None = None, max_age_s: float = 1.0) -> bool:
        if not isfinite(timestamp) or not isfinite(now):
            return False
        # Host monotonic is NOT the MCU print-time clock. The caller maps it
        # with MCU.estimated_print_time before testing buffered sample age.
        if estimated is not None and (not isfinite(estimated)
                or not -0.1 <= estimated - timestamp <= max_age_s):
            return False
        if self.last_mcu is not None and timestamp <= self.last_mcu:
            return False
        self.last_mcu, self.last_host = timestamp, now
        return True

    def age(self, now: float) -> float | None:
        return None if self.last_host is None else max(0.0, now - self.last_host)

    def stale(self, now: float, started: float, timeout: float) -> bool:
        return now - max(started, self.last_host if self.last_host is not None else started) >= timeout


@dataclass
class StableBaseline:
    started: float | None = None
    last: float | None = None
    low: float = 0.0
    high: float = 0.0
    total: float = 0.0
    count: int = 0

    def reset(self) -> None:
        self.started = self.last = None
        self.count = 0
        self.total = 0.0

    def note(self, sample: Sample, duration: float, span: float) -> float | None:
        if not isfinite(sample.force) or not isfinite(sample.timestamp):
            self.reset()
            return None
        if self.last is not None and not 0 < sample.timestamp - self.last <= 0.1:
            self.reset()
        if self.count and max(self.high, sample.force) - min(self.low, sample.force) > span:
            self.reset()
        if self.started is None:
            self.started = sample.timestamp
            self.low = self.high = sample.force
        self.last = sample.timestamp
        self.low = min(self.low, sample.force)
        self.high = max(self.high, sample.force)
        self.total += sample.force
        self.count += 1
        if self.count >= 5 and sample.timestamp - self.started >= duration:
            ref = self.total / self.count
            return ref if isfinite(ref) else None
        return None
