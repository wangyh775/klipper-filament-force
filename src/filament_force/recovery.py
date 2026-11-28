"""Pure recovery state and frozen force-model helpers (no Klipper imports)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .force_signal import AnomalyKind, BandResult, score_level


class RecoveryState(str, Enum):
    MONITORING = "monitoring"
    PREPARING = "preparing"
    WAITING_DIAGNOSIS = "waiting_diagnosis"
    DIAGNOSING = "diagnosing"
    CONFIRMED_JAM = "confirmed_jam"
    WAITING_RECOVERY = "waiting_recovery"
    RESUMING = "resuming"
    VERIFYING = "verifying"
    FAILED = "failed"


@dataclass(frozen=True)
class ForceReference:
    mean: float
    stdev: float
    high_sigma: float
    min_delta_g: float
    drop_ratio: float
    runout_max_level_g: float

    def score(self, force: float) -> BandResult:
        return score_level(
            force, self.mean, self.stdev, high_sigma=self.high_sigma,
            min_delta_g=self.min_delta_g, drop_ratio=self.drop_ratio,
            runout_max_level_g=self.runout_max_level_g,
        )

    def usable(self) -> bool:
        return (
            all(isfinite(x) for x in (self.mean, self.stdev, self.high_sigma,
                                      self.min_delta_g))
            and self.mean > self.min_delta_g > 0
            and self.stdev >= 0 and self.high_sigma > 0
        )

    def diagnostic_bounds(self, limit: float) -> tuple[float, float] | None:
        if not self.usable():
            return None
        band = self.score(self.mean)
        # A low force is not evidence of healthy flow. Do not clamp the
        # learned high band to the hardware cap and call it a healthy band.
        low = max(self.min_delta_g, band.low_bound)
        if not 0 < low < band.high_bound < limit:
            return None
        return low, band.high_bound


@dataclass
class Recovery:
    state: RecoveryState = RecoveryState.MONITORING
    attempts: int = 0
    healthy: int = 0
    deadline: float = 0.0
    before_z: float | None = None
    last_z: float | None = None
    clearance: bool = False
    failure: str = ""

    def prepare(self) -> None:
        self.state = RecoveryState.PREPARING
        self.clearance = False
        self.healthy = 0
        self.failure = ""

    def fail(self, reason: str) -> None:
        self.state = RecoveryState.FAILED
        self.failure = reason
        self.clearance = False

    def start_verification(self, now: float, timeout: float) -> None:
        self.state = RecoveryState.VERIFYING
        self.healthy = 0
        self.deadline = now + timeout
        self.last_z = None

    def observe(self, band: BandResult, needed: int) -> bool:
        self.last_z = band.z_score
        if band.kind is AnomalyKind.NONE:
            self.healthy += 1
        else:
            self.healthy = 0
        if self.healthy >= needed:
            self.state = RecoveryState.MONITORING
            self.clearance = False
            self.before_z = None
            return True
        return False

    def improved(self, current_z: float, fraction: float) -> bool:
        return (
            self.before_z is not None and self.before_z > 0
            and isfinite(current_z)
            and current_z <= self.before_z * (1.0 - fraction)
        )
