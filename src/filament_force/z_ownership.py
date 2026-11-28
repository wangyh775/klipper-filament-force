"""In-memory transactional ownership of first-layer Z corrections.

Never infer cleanup safety from a counter alone. The coordinate origin must
match the last confirmed correction and the job must be idle.
"""
from dataclasses import dataclass
from math import isfinite


def same_origin(a: float | None, b: float | None) -> bool:
    return (a is not None and b is not None and isfinite(a) and isfinite(b)
            and abs(a - b) <= 1e-6)


@dataclass
class ZOwnership:
    applied_mm: float = 0.0
    origin: float | None = None
    staged_step: float = 0.0
    before: float | None = None
    expected: float | None = None
    cleanup_pending: bool = False
    uncertain: bool = False

    def stage(self, actual: float | None, expected: float, step: float) -> None:
        if (self.cleanup_pending or self.staged_step or not isfinite(step)
                or not 0 < step <= 0.05 or not same_origin(actual, expected - step)
                or (self.applied_mm and not same_origin(actual, self.origin))):
            raise ValueError("unsafe Z ownership transaction")
        self.staged_step, self.before, self.expected = step, actual, expected

    def matches_expected(self, actual: float | None) -> bool:
        return bool(self.staged_step and same_origin(actual, self.expected))

    def matches_before(self, actual: float | None) -> bool:
        return bool(self.staged_step and same_origin(actual, self.before))

    def _clear_stage(self) -> None:
        self.staged_step = 0.0
        self.before = self.expected = None

    def commit(self, actual: float | None) -> None:
        if not self.matches_expected(actual):
            raise ValueError("corrected Z origin not acknowledged")
        self.applied_mm = round(self.applied_mm + self.staged_step, 6)
        self.origin = actual
        self._clear_stage()

    def rollback(self, actual: float | None) -> None:
        if not self.matches_before(actual):
            raise ValueError("cannot acknowledge unapplied Z correction")
        self._clear_stage()

    def finish_job(self) -> bool:
        if self.staged_step:
            self.mark_uncertain()
        if self.applied_mm:
            self.cleanup_pending = True
        return self.cleanup_pending

    def mark_uncertain(self) -> None:
        self.cleanup_pending = self.uncertain = True

    def cleanup_target(self, actual: float | None) -> float:
        if (not self.cleanup_pending or self.uncertain or self.staged_step
                or not self.applied_mm or actual is None
                or not same_origin(actual, self.origin)):
            raise ValueError("cannot safely undo Z correction")
        return actual - self.applied_mm

    def confirm_cleanup(self, actual: float | None, target: float) -> None:
        if not same_origin(actual, target):
            self.mark_uncertain()
            raise ValueError("Z undo was not acknowledged")
        self.clear()

    def clear(self) -> None:
        self.applied_mm = 0.0
        self.origin = None
        self._clear_stage()
        self.cleanup_pending = self.uncertain = False

    def status(self) -> dict[str, object]:
        return {
            "applied_mm": self.applied_mm, "origin_mm": self.origin,
            "staged_step_mm": self.staged_step, "before_mm": self.before,
            "expected_mm": self.expected, "cleanup_pending": self.cleanup_pending,
            "uncertain": self.uncertain,
        }
