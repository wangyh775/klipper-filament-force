"""Regressions for Kalico [load_cell_probe] force-stream resolution."""
from filament_force.filament_force import _resolve_load_cell


class _ForceStream:
    def add_client(self, callback: object) -> None:
        pass


class _KalicoProbe:
    """Outer add_client receives tap events; inner receives force samples."""
    def __init__(self) -> None:
        self._load_cell = _ForceStream()

    def add_client(self, callback: object) -> None:
        pass


def test_kalico_probe_prefers_inner_force_stream() -> None:
    probe = _KalicoProbe()
    assert _resolve_load_cell(probe) is probe._load_cell


def test_direct_load_cell_still_supported() -> None:
    cell = _ForceStream()
    assert _resolve_load_cell(cell) is cell


def test_probe_getter_supported() -> None:
    cell = _ForceStream()

    class Probe:
        def get_load_cell(self) -> object:
            return cell

        def add_client(self, callback: object) -> None:
            pass

    assert _resolve_load_cell(Probe()) is cell
