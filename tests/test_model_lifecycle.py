"""Regression tests for the force model's save and restart lifecycle."""

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from filament_force.filament_force import FilamentForce
from filament_force.first_layer import FirstLayerZControl
from filament_force.force_signal import ToolForceBook
from filament_force.free_air import FreeAirDiagnostic
from filament_force.model_store import ModelStore


@pytest.fixture
def make_monitor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[[], FilamentForce]]:
    writers: list[ThreadPoolExecutor] = []

    def create() -> FilamentForce:
        monitor = FilamentForce.__new__(FilamentForce)
        monitor.model_persistence = True
        monitor.model_store = ModelStore(str(tmp_path / "force-model.json"))
        monitor._model_writer = ThreadPoolExecutor(max_workers=1)
        writers.append(monitor._model_writer)
        monitor._model_future = None
        monitor._model_dirty = False
        monitor._model_load_state = "missing"
        monitor._restored_bins = {}
        monitor.books = {}
        monitor.speed_bin_edges = (1.0,)
        monitor.history_n = 8
        monitor.min_learn_windows = 3
        monitor.first_layer = FirstLayerZControl()
        monitor._diag = FreeAirDiagnostic()
        monitor._diag_generation = 0
        monkeypatch.setattr(monitor, "_model_fingerprint", lambda: {"profile": "PEEK"})
        return monitor

    yield create
    for writer in writers:
        writer.shutdown(wait=True)


def learn(monitor: FilamentForce) -> ToolForceBook:
    book = ToolForceBook(2, monitor.history_n, monitor.min_learn_windows)
    book.bins[0].windows.extend([100.0, 101.0, 102.0])
    book.runout.windows.extend([100.0, 101.0, 102.0])
    monitor.books[-1] = book
    monitor._model_dirty = True
    return book


def test_disconnect_saves_model_before_next_instance_loads(
    make_monitor: Callable[[], FilamentForce],
) -> None:
    monitor = make_monitor()
    learn(monitor)

    monitor._handle_model_disconnect()

    restarted = make_monitor()
    restarted._load_model_store()
    assert restarted._model_load_state == "loaded"
    assert list(restarted.books[-1].bins[0].windows) == [100.0, 101.0, 102.0]
    assert list(restarted.books[-1].runout.windows) == [100.0, 101.0, 102.0]
    assert restarted._restored_bins == {(-1, 0): 0, (-1, -1): 0}


def test_job_end_queues_checkpoint_behind_inflight_save(
    make_monitor: Callable[[], FilamentForce], monkeypatch: pytest.MonkeyPatch
) -> None:
    monitor = make_monitor()
    book = learn(monitor)
    first_started = Event()
    release_first = Event()
    original_save = monitor.model_store.save_payload

    def save(payload: dict[str, object]) -> None:
        if not first_started.is_set():
            first_started.set()
            assert release_first.wait(5)
        original_save(payload)

    monkeypatch.setattr(monitor.model_store, "save_payload", save)
    monitor._save_model_store()
    first = monitor._model_future
    try:
        assert first_started.wait(5)
        assert first is not None
        book.bins[0].windows.append(103.0)
        monitor._model_dirty = True

        monitor._handle_job_reset()

        latest = monitor._model_future
        assert latest is not None and latest is not first
        assert not first.done()
    finally:
        release_first.set()
    latest.result(timeout=5)

    restarted = make_monitor()
    restarted._load_model_store()
    assert list(restarted.books[-1].bins[0].windows) == [100.0, 101.0, 102.0, 103.0]


def test_disconnect_retries_failed_background_save(
    make_monitor: Callable[[], FilamentForce], monkeypatch: pytest.MonkeyPatch
) -> None:
    monitor = make_monitor()
    learn(monitor)
    original_save = monitor.model_store.save_payload
    attempts = 0

    def fail_once(payload: dict[str, object]) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("transient save failure")
        original_save(payload)

    monkeypatch.setattr(monitor.model_store, "save_payload", fail_once)
    monitor._save_model_store()

    monitor._handle_model_disconnect()

    restarted = make_monitor()
    restarted._load_model_store()
    assert attempts == 2
    assert restarted._model_load_state == "loaded"
    assert restarted.books[-1].bins[0].learned
