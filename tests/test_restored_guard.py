"""Regression tests for safe restart validation and cross-model learning."""
from filament_force.force_signal import (
    AnomalyKind, Sample, ToolForceBook, observe_restored,
)
from filament_force.model_store import ModelStore


def learned_book() -> ToolForceBook:
    book = ToolForceBook(2, 8, 3)
    book.bins[0].windows.extend([500.0] * 3)
    book.runout.windows.extend([500.0] * 3)
    return book


def observe(book: ToolForceBook, pending: dict[tuple[int, int], int],
            force: float, *, speed: float = 0.8, short: bool = False) -> AnomalyKind | None:
    return observe_restored(
        book, pending, -1, force, speed, (1.0,),
        short_bead=short, high_sigma=4.0, min_delta_g=15.0,
        confirm_windows=3, recover_windows=2, drop_ratio=0.35,
        runout_max_level_g=80.0, trip_high=True,
    )


def test_restart_jam_does_not_relearn() -> None:
    book = learned_book()
    pending = {(-1, 0): 0, (-1, -1): 0}
    assert observe(book, pending, 1000.0) is None
    assert observe(book, pending, 1000.0) is None
    assert observe(book, pending, 1000.0) is AnomalyKind.HIGH
    assert list(book.bins[0].windows) == [500.0] * 3
    assert list(book.runout.windows) == [500.0] * 3
    assert pending[(-1, 0)] < 0


def test_restart_runout_in_unseen_speed_does_not_learn() -> None:
    book = learned_book()
    pending = {(-1, 0): 0, (-1, -1): 0}
    assert observe(book, pending, 10.0, speed=2.0) is None
    assert observe(book, pending, 10.0, speed=2.0) is None
    assert observe(book, pending, 10.0, speed=2.0) is AnomalyKind.LOW
    assert not book.bins[1].windows
    assert list(book.runout.windows) == [500.0] * 3


def test_short_beads_do_not_validate_or_mutate() -> None:
    book = learned_book()
    pending = {(-1, 0): 0, (-1, -1): 0}
    for _ in range(6):
        assert observe(book, pending, 1000.0, short=True) is None
    assert pending == {(-1, 0): 0, (-1, -1): 0}
    assert book.jam_streak == 0


def test_healthy_windows_validate_both_references_together() -> None:
    book = learned_book()
    pending = {(-1, 0): 0, (-1, -1): 0}
    for _ in range(3):
        assert observe(book, pending, 500.0) is None
    assert not pending
    assert len(book.bins[0].windows) == 3
    assert observe(book, pending, 500.0) is None
    assert len(book.bins[0].windows) == 4


def test_uncertain_force_below_sigma_trip_still_pauses() -> None:
    book = learned_book()
    pending = {(-1, 0): 0, (-1, -1): 0}
    assert observe(book, pending, 600.0) is None
    assert observe(book, pending, 600.0) is None
    assert observe(book, pending, 600.0) is AnomalyKind.HIGH
    assert list(book.bins[0].windows) == [500.0] * 3


def test_normal_low_does_not_train_unlearned_speed_bin() -> None:
    book = learned_book()
    for _ in range(2):
        assert observe(book, {}, 10.0, speed=2.0) is None
    assert observe(book, {}, 10.0, speed=2.0) is AnomalyKind.LOW
    assert not book.bins[1].windows


def test_nonfinite_force_and_timestamp_are_rejected() -> None:
    for invalid in (float("nan"), float("inf"), -float("inf")):
        assert Sample.from_raw([0.0, invalid]) is None
        assert Sample.from_raw([invalid, 0.0]) is None


def test_profiles_are_isolated() -> None:
    a = ModelStore("force.json", profile="PEEK/400")
    b = ModelStore("force.json", profile="PEEK/410")
    assert a.path != b.path
    assert a.path.parent == b.path.parent
    assert a.path == ModelStore("force.json", profile="PEEK/400").path
