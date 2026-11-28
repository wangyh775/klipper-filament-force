"""Conservative, opt-in first-layer Z lift gate for force-band jam trips.

This is a bounded recovery attempt, not a classifier capable of reliably
distinguishing a nozzle too close to the bed from a true filament jam.
The independent absolute-force interlock always retains priority.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class FirstLayerZControl:
    enabled: bool = False
    step_mm: float = 0.02
    max_adjustments: int = 3
    cooldown_s: float = 10.0
    max_height_mm: float = 0.60
    max_force_g: float = 2000.0
    move_speed: float = 2.0

    adjustments: int = 0
    applied_mm: float = 0.0
    last_adjusted_at: float | None = None

    def may_adjust(
        self,
        *,
        source: str,
        printing: bool,
        layer: object,
        z_mm: float | None,
        z_homed: bool,
        force_g: float,
        now: float,
    ) -> bool:
        """Fail closed if the print layer, position, or force is uncertain."""
        if not self.enabled or source != "band" or not printing or not z_homed:
            return False
        if type(layer) is not int or layer != 1:
            return False
        if z_mm is None or not math.isfinite(z_mm):
            return False
        if z_mm < 0 or z_mm > self.max_height_mm:
            return False
        if not math.isfinite(force_g) or not (0 < force_g <= self.max_force_g):
            return False
        if self.adjustments >= self.max_adjustments:
            return False
        if self.last_adjusted_at is not None:
            if now - self.last_adjusted_at < self.cooldown_s:
                return False
        return True

    def record_adjustment(self, now: float) -> None:
        """Commit only after the Z-adjust G-code succeeded."""
        self.adjustments += 1
        self.applied_mm = round(self.applied_mm + self.step_mm, 6)
        self.last_adjusted_at = now

    def reset(self) -> None:
        self.adjustments = 0
        self.applied_mm = 0.0
        self.last_adjusted_at = None
