from filament_force.force_signal import Sample
from filament_force.protection import SampleHealth, StableBaseline


def test_duplicate_or_regressed_samples_do_not_refresh_watchdog() -> None:
    health = SampleHealth()
    assert health.note(10.0, 1.0)
    assert not health.note(10.0, 2.0)
    assert not health.note(9.0, 2.5)
    assert health.stale(3.0, 0.0, 2.0)
    assert health.note(10.1, 3.1)
    assert not health.stale(3.1, 0.0, 2.0)


def test_baseline_rejects_large_span_and_gap() -> None:
    baseline = StableBaseline()
    for i in range(8):
        assert baseline.note(Sample(i * .03, 1000.0 + 200 * (i % 2)), .15, 100.0) is None
    baseline.reset()
    for i in range(5):
        assert baseline.note(Sample(i * .02, 1000.0), .15, 100.0) is None
    assert baseline.note(Sample(.5, 1000.0), .15, 100.0) is None
    result = None
    for i in range(1, 6):
        result = baseline.note(Sample(.5 + i * .04, 1000.0), .15, 100.0)
    assert result == 1000.0


def test_watchdog_initial_grace() -> None:
    health = SampleHealth()
    assert not health.stale(1.99, 0.0, 2.0)
    assert health.stale(2.0, 0.0, 2.0)
