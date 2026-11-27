"""Tests for versioned, validated force-model persistence."""
import json
from typing import cast

from filament_force.force_signal import ToolForceBook
from filament_force.model_store import ModelStore, decode, snapshot


PROFILE: dict[str, object] = {"profile": "PEEK-400C-0.4", "speed_bins": [1.0, 2.0, 4.0, 7.0]}


def make_book() -> ToolForceBook:
    book = ToolForceBook(n_bins=5, history_n=8, min_learn_windows=3)
    for index, hist in enumerate(book.bins):
        hist.windows.extend([100.0 + index, 102.0 + index, 101.0 + index])
    book.runout.windows.extend([100.0, 102.0, 101.0])
    book.jam_streak = 2
    book.jam_suspect = True
    return book


def test_snapshot_round_trip_keeps_only_healthy_windows() -> None:
    book = make_book()
    payload = snapshot({-1: book}, PROFILE)
    loaded = decode(
        payload, PROFILE, n_bins=5, history_n=8, min_learn_windows=3
    )
    assert loaded.state == "loaded"
    restored = loaded.books[-1]
    assert list(restored.bins[0].windows) == [100.0, 102.0, 101.0]
    assert list(restored.runout.windows) == [100.0, 102.0, 101.0]
    assert restored.jam_streak == 0
    assert restored.jam_suspect is False


def test_fingerprint_mismatch_rejects_model() -> None:
    payload = snapshot({-1: make_book()}, PROFILE)
    changed = {**PROFILE, "profile": "PEEK-410C-0.4"}
    result = decode(
        payload, changed, n_bins=5, history_n=8, min_learn_windows=3
    )
    assert result.state == "incompatible"
    assert result.books == {}


def test_malformed_or_nonfinite_samples_rejected() -> None:
    payload = snapshot({-1: make_book()}, PROFILE)
    tools = cast(dict[str, object], payload["tools"])
    tool = cast(dict[str, object], tools["-1"])
    bins = cast(list[list[float]], tool["bins"])
    bins[0][0] = float("nan")
    result = decode(
        payload, PROFILE, n_bins=5, history_n=8, min_learn_windows=3
    )
    assert result.state == "invalid"


def test_atomic_store_round_trip_and_clear(tmp_path) -> None:
    path = tmp_path / "force-model.json"
    store = ModelStore(str(path))
    store.save({-1: make_book()}, PROFILE)
    assert path.exists()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    loaded = store.load(
        PROFILE, n_bins=5, history_n=8, min_learn_windows=3
    )
    assert loaded.state == "loaded"
    store.clear()
    assert not path.exists()


def test_wrong_speed_bin_count_is_rejected() -> None:
    payload = snapshot({-1: make_book()}, PROFILE)
    result = decode(
        payload, PROFILE, n_bins=4, history_n=8, min_learn_windows=3
    )
    assert result.state == "incompatible"
