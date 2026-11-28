from typing import cast
from unittest.mock import Mock

import pytest

from filament_force.filament_force import FilamentForce
from filament_force.force_signal import Sample
from filament_force.free_air import FreeAirDiagnostic


def make_monitor(monkeypatch: pytest.MonkeyPatch, *, shift: float = 0.0,
                 missing: bool = False, motion: bool = False) -> FilamentForce:
    m = FilamentForce.__new__(FilamentForce)
    m._diag = FreeAirDiagnostic(reference=1000.0)
    m.diagnostic_limit = 2000.0
    m.oh_shit_force = 4000.0
    m.diagnostic_max_sample_gap_s = 0.05
    m.baseline_max_span_g = 100.0
    m._resume_capture = None
    m._estimated_print_time = lambda t: t
    monkeypatch.setattr(m, "_diagnostic_ready", lambda _g: True)
    monkeypatch.setattr(m, "_extruder_pos", lambda _t: 20.0)
    th = Mock()
    th.get_last_move_time.side_effect = [1.0, 2.0 if motion else 1.0]
    printer = Mock()
    printer.lookup_object.return_value = th
    reactor = Mock()
    reactor.monotonic.return_value = 10.0
    def collect(_deadline: float) -> None:
        capture = m._resume_capture
        assert capture is not None
        if not missing:
            for i in range(81):
                capture.note(Sample(10.0 + i * .01, 1000.0 + shift))
    reactor.pause.side_effect = collect
    monkeypatch.setattr(m, "reactor", reactor, raising=False)
    monkeypatch.setattr(m, "printer", printer, raising=False)
    monkeypatch.setattr(m, "gcode", Mock(), raising=False)
    return m


def test_qualify_fresh_stationary_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    m = make_monitor(monkeypatch, shift=15.0)
    assert m._qualify_resume_baseline(0) == 1015.0
    assert m._resume_capture is None
    cast(Mock, m.gcode).run_script_from_command.assert_called_once_with("M400")


@pytest.mark.parametrize("shift,missing,motion", [(150., False, False), (0., True, False), (0., False, True)])
def test_refuse_unqualified_resume(monkeypatch: pytest.MonkeyPatch, shift: float,
                                   missing: bool, motion: bool) -> None:
    m = make_monitor(monkeypatch, shift=shift, missing=missing, motion=motion)
    with pytest.raises(RuntimeError):
        m._qualify_resume_baseline(0)
    assert m._resume_capture is None
