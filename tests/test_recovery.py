"""Unit regressions for force recovery without a printer."""
from copy import deepcopy

import pytest

from filament_force.force_signal import AnomalyKind
from filament_force.recovery import ForceReference, Recovery, RecoveryState, shifted_pause_state


def reference() -> ForceReference:
    return ForceReference(500.0, 20.0, 4.0, 15.0, 0.35, 80.0)


def test_diagnostic_reuses_learned_band_without_truncating_to_cap() -> None:
    ref = reference()
    assert ref.diagnostic_bounds(1000.0) == (80.0, 660.0)
    assert ref.diagnostic_bounds(600.0) is None
    assert ref.score(1000.0).kind is AnomalyKind.HIGH
    assert ref.score(10.0).kind is AnomalyKind.LOW


def test_recovery_requires_consecutive_healthy_windows() -> None:
    r = Recovery()
    ref = reference()
    r.prepare()
    assert r.state is RecoveryState.PREPARING
    r.start_verification(1.0, 60.0)
    assert r.deadline == 61.0
    assert not r.observe(ref.score(500.0), 2)
    assert not r.observe(ref.score(900.0), 2)
    assert r.healthy == 0 and r.bad == 1
    assert not r.observe(ref.score(510.0), 2)
    assert r.observe(ref.score(500.0), 2)
    assert r.state is RecoveryState.MONITORING


def test_improvement_and_failure() -> None:
    r = Recovery()
    assert not r.improved(5.0, 0.15)
    r.before_z = 10.0
    assert r.improved(8.0, 0.15)
    assert not r.improved(9.0, 0.15)
    r.fail("timeout")
    assert r.state is RecoveryState.FAILED
    assert r.failure == "timeout"


def test_shifted_pause_state_preserves_logical_z_and_e() -> None:
    state = {
        "base_position": [1.0, 2.0, 0.1, 6.0],
        "homing_position": [0.0, 0.0, 0.1, 0.0],
        "last_position": [10.0, 20.0, 0.3, 100.0],
    }
    original = deepcopy(state)
    shifted = shifted_pause_state(state, 0.02)
    assert state == original
    assert shifted["base_position"] == pytest.approx([1.0, 2.0, 0.12, 6.0])
    assert shifted["homing_position"] == pytest.approx([0.0, 0.0, 0.12, 0.0])
    assert shifted["last_position"] == pytest.approx([10.0, 20.0, 0.32, 100.0])


@pytest.mark.parametrize("step", [-0.02, 0.0, 0.1, float("nan")])
def test_invalid_z_step_refused(step: float) -> None:
    with pytest.raises(ValueError):
        shifted_pause_state({}, step)


def test_missing_pause_state_refused() -> None:
    with pytest.raises(ValueError):
        shifted_pause_state(None, 0.02)


def test_verification_expires_both_streaks() -> None:
    r = Recovery()
    ref = reference()
    r.start_verification(0, 60)
    assert not r.observe(ref.score(500), 2, eventtime=1, max_gap_s=30)
    assert not r.observe(ref.score(500), 2, eventtime=32, max_gap_s=30)
    assert r.healthy == 1
    assert r.observe(ref.score(500), 2, eventtime=33, max_gap_s=30)


def test_recovery_budgets_are_independent() -> None:
    r = Recovery()
    r.begin_incident()
    r.record_auto_attempt(first=True)
    r.record_auto_attempt(first=False)
    assert (r.attempts, r.ordinary_attempts, r.incident_attempts) == (2, 1, 2)
    r.manual_attempts += 1
    r.prepare()
    assert (r.attempts, r.ordinary_attempts, r.incident_attempts) == (2, 1, 2)
    r.reset_consecutive_attempts()
    assert (r.attempts, r.ordinary_attempts, r.incident_attempts) == (0, 0, 2)
    r.begin_incident()
    assert r.incident_attempts == 0 and r.manual_attempts == 1
