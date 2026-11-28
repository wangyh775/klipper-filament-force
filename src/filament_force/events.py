"""Bounded, read-only event telemetry. No I/O on the ADC callback."""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from math import isfinite
from typing import Any
from uuid import uuid4

from .force_signal import Sample


class EventJournal:
    def __init__(self, seconds: float = 30.0, max_points: int = 512):
        self.boot_id = uuid4().hex
        self.seq = 0
        self.seconds = seconds
        self.max_points = max_points
        self.samples: deque[Sample] = deque(maxlen=40000)
        self.windows: deque[dict[str, Any]] = deque(maxlen=32)
        self.events: deque[dict[str, Any]] = deque(maxlen=16)

    def note(self, sample: Sample) -> None:
        if not (isfinite(sample.timestamp) and isfinite(sample.force)):
            return
        if self.samples and sample.timestamp < self.samples[-1].timestamp:
            self.clear_trace()
        self.samples.append(sample)
        cutoff = sample.timestamp - self.seconds
        while self.samples and self.samples[0].timestamp < cutoff:
            self.samples.popleft()

    def clear_trace(self) -> None:
        self.samples.clear()
        self.windows.clear()

    def trace(self, ref: float | None) -> dict[str, Any]:
        rows = list(self.samples)
        n = len(rows)
        # Min/max envelope in chronological order, preserving short peaks.
        if n > self.max_points:
            bins = self.max_points // 2
            selected = []
            for i in range(bins):
                start, end = i * n // bins, (i + 1) * n // bins
                block = rows[start:end]
                lo = min(range(len(block)), key=lambda j: block[j].force)
                hi = max(range(len(block)), key=lambda j: block[j].force)
                selected.extend(block[j] for j in sorted({lo, hi}))
        else:
            selected = rows
        t0 = rows[0].timestamp if rows else None
        return {
            "clock": "mcu_print_time", "start_time": t0,
            "duration_s": rows[-1].timestamp - t0 if t0 is not None else 0.0,
            "sample_count": n, "returned_count": len(selected),
            "downsampled": len(selected) < n,
            "force_ref_g": ref,
            "columns": ["t_s", "force_g"],
            "samples": [[round(s.timestamp - t0, 6), round(s.force, 3)]
                        for s in selected] if t0 is not None else [],
            "windows": deepcopy(list(self.windows)),
        }

    def emit(self, kind: str, **fields: Any) -> dict[str, Any]:
        self.seq += 1
        event = {"schema": 1, "boot_id": self.boot_id, "seq": self.seq,
                 "event_id": f"{self.boot_id}:{self.seq}", "kind": kind, **fields}
        self.events.append(deepcopy(event))
        return deepcopy(event)

    def status(self) -> list[dict[str, Any]]:
        return deepcopy(list(self.events))
