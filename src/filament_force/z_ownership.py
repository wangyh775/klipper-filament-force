"""Transactional ownership of first-layer Z corrections.

Never infer cleanup safety from a counter alone. The coordinate origin must
match the last confirmed correction and the job must be idle.
"""
import json
from dataclasses import dataclass, field
from math import isfinite

from .model_store import ModelStore


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
    _store: ModelStore | None = field(default=None, repr=False)
    persistence_error: str = ""

    @classmethod
    def load(cls, filename: str) -> "ZOwnership":
        # Deliberately independent of material/model profile.
        owned = cls(_store=ModelStore(filename))
        assert owned._store is not None
        try:
            with owned._store.path.open(encoding="utf-8") as stream:
                data = json.load(stream)
            if type(data.get("schema")) is not int or data["schema"] != 1:
                raise ValueError("invalid Z ledger schema")
            def number(key: str, nullable: bool = False) -> float | None:
                value = data[key]
                if nullable and value is None:
                    return None
                if type(value) not in (int, float) or not isfinite(value):
                    raise ValueError("invalid Z ledger value")
                return float(value)
            applied, staged = number("applied_mm"), number("staged_step_mm")
            if applied is None or staged is None or not 0 <= applied <= .2 or not 0 <= staged <= .05:
                raise ValueError("invalid Z ledger budget")
            owned.applied_mm, owned.staged_step = applied, staged
            owned.origin = number("origin_mm", True)
            owned.before = number("before_mm", True)
            owned.expected = number("expected_mm", True)
            for key in ("cleanup_pending", "uncertain"):
                if type(data[key]) is not bool:
                    raise ValueError("invalid Z ledger flag")
            # Any nonempty previous-process record is for manual reconciliation
            # only. Never apply an old coordinate delta automatically.
            if applied or staged or data["cleanup_pending"] or data["uncertain"]:
                owned.mark_uncertain()
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            owned.mark_uncertain()
            owned.persistence_error = type(exc).__name__
        return owned

    def checkpoint(self) -> None:
        if self._store is None:
            return
        try:
            self._store.save_payload({"schema": 1, **self.status()})
            self.persistence_error = ""
        except Exception as exc:
            self.mark_uncertain()
            self.persistence_error = type(exc).__name__
            raise

    def stage(self, actual: float | None, expected: float, step: float) -> None:
        if (self.cleanup_pending or self.staged_step or not isfinite(step)
                or not 0 < step <= 0.05 or not same_origin(actual, expected - step)
                or (self.applied_mm and not same_origin(actual, self.origin))):
            raise ValueError("unsafe Z ownership transaction")
        self.staged_step, self.before, self.expected = step, actual, expected
        self.checkpoint()

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
        self.checkpoint()

    def rollback(self, actual: float | None) -> None:
        if not self.matches_before(actual):
            raise ValueError("cannot acknowledge unapplied Z correction")
        self._clear_stage()
        self.checkpoint()

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
        self.checkpoint()

    def status(self) -> dict[str, object]:
        return {
            "applied_mm": self.applied_mm, "origin_mm": self.origin,
            "staged_step_mm": self.staged_step, "before_mm": self.before,
            "expected_mm": self.expected, "cleanup_pending": self.cleanup_pending,
            "uncertain": self.uncertain,
            "persistence_error": self.persistence_error,
        }
