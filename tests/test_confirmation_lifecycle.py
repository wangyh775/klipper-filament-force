"""Confirmation evidence must not survive long gaps or job resets."""
from filament_force.force_signal import AnomalyKind, ToolForceBook, observe_restored


def make_book() -> ToolForceBook:
    book = ToolForceBook(2, 8, 3)
    book.bins[0].windows.extend([500.0] * 3)
    book.runout.windows.extend([500.0] * 3)
    return book


def score(book: ToolForceBook, pending: dict[tuple[int, int], int],
          time: float, *, short: bool = False) -> AnomalyKind | None:
    return observe_restored(
        book, pending, -1, 1000.0, 0.8, (1.0,),
        short_bead=short, high_sigma=4.0, min_delta_g=15.0,
        confirm_windows=3, recover_windows=2, drop_ratio=0.35,
        runout_max_level_g=80.0, trip_high=True,
        eventtime=time, max_gap_s=30.0,
    )


def test_stale_jam_streak_does_not_trip_on_one_new_window() -> None:
    book = make_book()
    assert score(book, {}, 1.0) is None
    assert score(book, {}, 10.0) is None
    assert score(book, {}, 25.0, short=True) is None
    assert score(book, {}, 41.0) is None
    assert book.jam_streak == 1
    assert score(book, {}, 50.0) is None
    assert score(book, {}, 59.0) is AnomalyKind.HIGH
    assert list(book.bins[0].windows) == [500.0] * 3


def test_stale_restore_mismatch_expires_without_relearning() -> None:
    book = make_book()
    pending = {(-1, 0): 0, (-1, -1): 0}
    assert score(book, pending, 1.0) is None
    assert score(book, pending, 10.0) is None
    assert pending[(-1, 0)] == -2
    assert score(book, pending, 41.0) is None
    assert pending[(-1, 0)] == -1
    assert score(book, pending, 50.0) is None
    assert score(book, pending, 59.0) is AnomalyKind.HIGH
    assert list(book.bins[0].windows) == [500.0] * 3


def test_clear_streaks_preserves_model() -> None:
    book = make_book()
    assert score(book, {}, 1.0) is None
    assert score(book, {}, 10.0) is None
    book.clear_streaks()
    assert book.last_confirmation_time is None
    assert score(book, {}, 11.0) is None
    assert book.jam_streak == 1
    assert list(book.bins[0].windows) == [500.0] * 3
