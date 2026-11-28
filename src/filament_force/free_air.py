"""Supervised, bounded free-air extrusion diagnosis; no model training.

Copyright (C) 2026 filament_force contributors
Distributed under the GNU GPLv3 license.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from math import isfinite
from enum import Enum

from .force_signal import Sample


class Diagnosis(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    FLOW_COMPATIBLE = "flow_compatible"
    RESTRICTION_SUSPECTED = "restriction_suspected"
    LOW_FORCE = "low_force"
    FORCE_LIMIT = "force_limit"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class Pulse:
    mean_g: float
    peak_g: float
    n: int


@dataclass
class FreeAirDiagnostic:
    active: bool = False
    result: Diagnosis = Diagnosis.IDLE
    samples: list[Sample] = field(default_factory=list)
    pulses: list[Pulse] = field(default_factory=list)
    reference: float | None = None
    limit_g: float = 0.0
    limit_hit: bool = False
    extruded_mm: float = 0.0
    capture_from: float | None = None
    max_sample_gap_s: float = 0.05

    def begin(self, limit_g: float) -> None:
        self.active = True
        self.result = Diagnosis.RUNNING
        self.samples.clear()
        self.pulses.clear()
        self.reference = None
        self.limit_g = limit_g
        self.limit_hit = False
        self.extruded_mm = 0.0
        self.capture_from = None

    def note(self, sample: Sample) -> None:
        if not self.active or not isfinite(sample.force) or not isfinite(sample.timestamp):
            return
        if self.capture_from is None or sample.timestamp < self.capture_from:
            return
        if self.reference is not None and abs(sample.force - self.reference) >= self.limit_g:
            self.limit_hit = True
        # Bound memory in case a move is delayed or the ADC runs very fast.
        if len(self.samples) < 20000:
            self.samples.append(sample)

    def capture(self, start: float) -> None:
        self.samples.clear()
        self.capture_from = start

    def _coverage(self, samples: list[Sample], start: float, end: float) -> bool:
        if len(samples) < 5 or end <= start:
            return False
        times = [s.timestamp for s in samples]
        gap = self.max_sample_gap_s
        return (times[0] - start <= gap + 1e-9
                and end - times[-1] <= gap + 1e-9
                and all(0 < b - a <= gap + 1e-9 for a, b in zip(times, times[1:])))

    def set_reference(self, start: float, end: float, max_span_g: float) -> bool:
        selected = [s for s in self.samples if start <= s.timestamp <= end]
        values = [s.force for s in selected]
        if not self._coverage(selected, start, end) or max(values) - min(values) > max_span_g:
            return False
        self.reference = median(values)
        self.samples.clear()
        self.capture_from = None
        return True

    def record_pulse(self, start: float, end: float) -> bool:
        if self.reference is None or end <= start:
            return False
        # Score the middle 60% of the actual nominal extrusion interval.
        # Peak interlock also includes onset and trailing samples.
        a = start + 0.2 * (end - start)
        b = end - 0.2 * (end - start)
        middle = [s for s in self.samples if a <= s.timestamp <= b]
        if not self._coverage(middle, a, b):
            return False
        times = [s.timestamp for s in middle]
        if min(times) > a + (b-a)*0.25 or max(times) < b - (b-a)*0.25:
            return False
        levels = [abs(s.force - self.reference) for s in middle]
        peak = max(abs(s.force - self.reference) for s in self.samples)
        self.pulses.append(Pulse(sum(levels)/len(levels), peak, len(levels)))
        return True

    def finish(self, *, expected_pulses: int, low_g: float, high_g: float) -> Diagnosis:
        self.active = False
        self.capture_from = None
        if self.limit_hit:
            self.result = Diagnosis.FORCE_LIMIT
        elif len(self.pulses) != expected_pulses or not (0 < low_g < high_g < self.limit_g):
            self.result = Diagnosis.INCONCLUSIVE
        elif all(p.mean_g > high_g for p in self.pulses):
            self.result = Diagnosis.RESTRICTION_SUSPECTED
        elif all(p.mean_g < low_g for p in self.pulses):
            self.result = Diagnosis.LOW_FORCE
        elif all(low_g <= p.mean_g <= high_g for p in self.pulses):
            self.result = Diagnosis.FLOW_COMPATIBLE
        else:
            self.result = Diagnosis.INCONCLUSIVE
        return self.result

    def abort(self) -> None:
        self.active = False
        self.capture_from = None
        self.result = Diagnosis.FORCE_LIMIT if self.limit_hit else Diagnosis.INCONCLUSIVE
