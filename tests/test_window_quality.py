from filament_force.force_signal import EWindowAccumulator, Sample


def test_sparse_window_not_qualified() -> None:
    w = EWindowAccumulator(7.0, .05)
    w.add_forward_e(1.0, eventtime=0.0)
    w.add_force(Sample(1.0, 500.0))
    result = w.add_forward_e(6.0, eventtime=3.0)
    assert result is not None
    assert not result.qualified(min_samples=5, max_gap_s=.05, edge_allowance_s=1.25)


def test_contiguous_window_quality_and_gap() -> None:
    for gap in (False, True):
        w = EWindowAccumulator(7.0, .05)
        w.add_forward_e(1.0, eventtime=0.0)
        for i in range(301):
            if gap and 100 <= i <= 150:
                continue
            w.add_force(Sample(i * .01, 500.0))
        result = w.add_forward_e(6.0, eventtime=3.0)
        assert result is not None
        assert result.qualified(min_samples=5, max_gap_s=.05, edge_allowance_s=1.25) is not gap
