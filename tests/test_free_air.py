"""Pure regression tests for the free-air diagnostic."""
import pytest

from filament_force.free_air import Diagnosis, FreeAirDiagnostic
from filament_force.force_signal import Sample


def setup() -> FreeAirDiagnostic:
    d = FreeAirDiagnostic()
    d.begin(200.0)
    d.capture(1.0)
    for i in range(10):
        d.note(Sample(1.0+i*0.05, 1000.0))
    assert d.set_reference(1.0, 1.5, 20.0)
    return d


def pulse(d: FreeAirDiagnostic, level: float) -> None:
    d.capture(2.0)
    for i in range(21):
        d.note(Sample(2.0+i*0.05, 1000.0+level))
    assert d.record_pulse(2.0, 3.0)


def test_normal_free_air_requires_all_pulses_and_calibration() -> None:
    d = setup()
    for _ in range(3):
        pulse(d, 70.0)
    assert d.finish(expected_pulses=3, low_g=50, high_g=100) is Diagnosis.FLOW_COMPATIBLE
    assert d.finish(expected_pulses=3, low_g=0, high_g=0) is Diagnosis.INCONCLUSIVE


def test_high_and_low_and_mixed() -> None:
    for levels, result in (
        ([150.0]*3, Diagnosis.RESTRICTION_SUSPECTED),
        ([10.0]*3, Diagnosis.LOW_FORCE),
        ([70.0, 150.0, 70.0], Diagnosis.INCONCLUSIVE),
    ):
        d = setup()
        for value in levels:
            pulse(d, value)
        assert d.finish(expected_pulses=3, low_g=50, high_g=100) is result


def test_force_limit_is_latched_across_capture() -> None:
    d = setup()
    d.capture(2.0)
    d.note(Sample(2.1, 1200.0))
    assert d.limit_hit
    d.capture(3.0)
    assert d.finish(expected_pulses=3, low_g=50, high_g=100) is Diagnosis.FORCE_LIMIT


def test_missing_or_stale_samples_never_classify() -> None:
    d = setup()
    d.capture(2.0)
    for i in range(20):
        d.note(Sample(1.0+i*0.01, 1070.0))
    assert not d.record_pulse(2.0, 3.0)
    assert d.finish(expected_pulses=3, low_g=50, high_g=100) is Diagnosis.INCONCLUSIVE


def test_unstable_baseline_rejected() -> None:
    d = FreeAirDiagnostic()
    d.begin(200.0)
    d.capture(1.0)
    for i in range(10):
        d.note(Sample(1.0+i*0.05, 1000.0+i*20))
    assert not d.set_reference(1.0, 1.5, 20.0)


def test_abort_never_reports_healthy() -> None:
    d = setup()
    pulse(d, 70.0)
    d.abort()
    assert not d.active
    assert d.result is Diagnosis.INCONCLUSIVE


def test_internal_gap_cannot_be_hidden_by_endpoint_coverage() -> None:
    d = setup()
    d.capture(2.0)
    for t in (2.2, 2.21, 2.22, 2.23, 2.77, 2.78, 2.79, 2.8):
        d.note(Sample(t, 1070.0))
    assert not d.record_pulse(2.0, 3.0)


def test_duplicate_pulse_timestamps_rejected() -> None:
    d = setup()
    d.capture(2.0)
    for i in range(21):
        d.note(Sample(2.0 + i * .05, 1070.0))
        d.note(Sample(2.0 + i * .05, 1070.0))
    assert not d.record_pulse(2.0, 3.0)


@pytest.mark.xfail(strict=True, reason="D-F03: missing pulse onset/tail still allows healthy classification")
def test_d_fault_missing_pulse_edges_cannot_authorize_recovery() -> None:
    d = setup()
    for _ in range(3):
        d.capture(2.0)
        # Only middle 60% delivered; onset/tail could hide an overload.
        for i in range(21):
            d.note(Sample(2.2 + i * .03, 1070.0))
        if not d.record_pulse(2.0, 3.0):
            break
    assert d.finish(expected_pulses=3, low_g=50, high_g=100) is not Diagnosis.FLOW_COMPATIBLE


def test_d_fault_single_peak_over_limit_overrides_healthy_means() -> None:
    d = setup()
    for _ in range(3):
        pulse(d, 70.0)
    d.note(Sample(3.1, 1250.0))
    assert d.finish(expected_pulses=3, low_g=50, high_g=100) is Diagnosis.FORCE_LIMIT
