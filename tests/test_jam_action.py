"""Regression tests for the optional learned-band jam action."""

from contextlib import nullcontext
from unittest.mock import Mock, call

import pytest

from filament_force.filament_force import FilamentForce
from filament_force.first_layer import FirstLayerZControl
from filament_force.force_signal import EWindowAccumulator, TripKind
from filament_force.pause import MonitorActions, MonitorTemplate


@pytest.fixture
def gcode() -> Mock:
    gcode = Mock()
    gcode.get_mutex.return_value = nullcontext()
    return gcode


@pytest.fixture
def stats() -> Mock:
    stats = Mock()
    stats.get_status.return_value = {"state": "printing", "info": {"current_layer": 1}}
    return stats


@pytest.fixture
def legacy_hook() -> Mock:
    return Mock()


@pytest.fixture
def monitor(
    monkeypatch: pytest.MonkeyPatch, gcode: Mock, stats: Mock, legacy_hook: Mock
) -> FilamentForce:
    result = FilamentForce.__new__(FilamentForce)
    reactor = Mock()
    printer = Mock()
    printer.lookup_object.side_effect = lambda name, default=None: {
        "print_stats": stats,
    }.get(name, default)

    actions = MonitorActions.__new__(MonitorActions)
    actions.clear_pending()
    monkeypatch.setattr(actions, "printer", printer, raising=False)
    monkeypatch.setattr(actions, "reactor", reactor, raising=False)
    monkeypatch.setattr(actions, "gcode", gcode, raising=False)
    monkeypatch.setattr(actions, "extruder_target", lambda: 400.0)
    monkeypatch.setattr(actions, "run_template_if_set", legacy_hook)
    monkeypatch.setattr(result, "_first_layer_z_position", lambda: (0.2, True))
    monkeypatch.setattr(result, "gcode", gcode, raising=False)
    monkeypatch.setattr(result, "reactor", reactor, raising=False)
    monkeypatch.setattr(result, "printer", printer, raising=False)
    monkeypatch.setattr(result, "_spike", Mock(), raising=False)
    result.actions = actions
    result.first_layer = FirstLayerZControl()
    result.active_tool = 0
    result._triggering = result._test_runout = result.suppress = False
    result._armed = True
    result._diag_generation = 0
    result._window = EWindowAccumulator(detection_length=8.0, rolling_window_s=0.1)
    return result


def configure_action(monitor: FilamentForce, name: str | None = None) -> None:
    config = Mock()
    section = Mock()
    section.get_name.return_value = name
    config.get_prefix_sections.return_value = [section] if name else []
    monitor._register_jam_action(config)


def test_builtin_action_is_registered_and_uses_pause(
    monitor: FilamentForce, gcode: Mock
) -> None:
    configure_action(monitor)
    gcode.register_command.assert_called_once_with(
        "FILAMENT_FORCE_JAM_ACTION", monitor._default_jam_action
    )
    monitor._default_jam_action(Mock())
    gcode.run_script_from_command.assert_called_once_with("PAUSE\nM400")


def test_custom_action_overrides_builtin_and_monitor_can_retry(
    monitor: FilamentForce,
    gcode: Mock,
    legacy_hook: Mock,
) -> None:
    configure_action(monitor, "gcode_macro filament_force_jam_action")
    gcode.register_command.assert_not_called()
    for _ in range(2):
        monitor._trip(TripKind.JAM, "700g", source="band", force_g=700.0)
        assert not monitor.actions.pending_recheck
        assert not monitor._triggering

    assert (
        gcode.run_script_from_command.call_args_list
        == [
            call(
                "FILAMENT_FORCE_JAM_ACTION TOOL=0 FORCE_G=700.000 TARGET=400.00 FIRST_LAYER=1"
            )
        ]
        * 2
    )
    assert legacy_hook.call_args.args[0] is MonitorTemplate.JAM


def test_custom_pause_preserves_fault_context(
    monitor: FilamentForce, gcode: Mock, stats: Mock
) -> None:
    configure_action(monitor, "gcode_macro FILAMENT_FORCE_JAM_ACTION")

    def run(_script: str) -> None:
        stats.get_status.return_value = {"state": "paused"}

    gcode.run_script_from_command.side_effect = run
    monitor._trip(TripKind.JAM, "700g", source="band", force_g=700.0)

    assert monitor.actions.pending_recheck
    assert monitor.actions.pending_tool == 0
    assert monitor.actions.pending_target == 400.0
    assert monitor.actions.pending_reason == "jam"


def test_failing_custom_action_falls_back_to_pause(
    monitor: FilamentForce, gcode: Mock, stats: Mock
) -> None:
    configure_action(monitor, "gcode_macro FILAMENT_FORCE_JAM_ACTION")

    def run(script: str) -> None:
        if script.startswith("FILAMENT_FORCE_JAM_ACTION"):
            raise RuntimeError("macro failed")
        stats.get_status.return_value = {"state": "paused"}

    gcode.run_script_from_command.side_effect = run
    monitor._trip(TripKind.JAM, "700g", source="band", force_g=700.0)

    assert gcode.run_script_from_command.call_args_list[-1] == call("PAUSE\nM400")
    assert monitor.actions.pending_recheck


@pytest.mark.parametrize(
    ("kind", "source"),
    [
        (TripKind.JAM, "hard"),
        (TripKind.JAM, "model_validation"),
        (TripKind.RUNOUT, "band"),
    ],
)
def test_protective_trips_keep_normal_pause(
    monitor: FilamentForce, gcode: Mock, kind: TripKind, source: str
) -> None:
    configure_action(monitor, "gcode_macro FILAMENT_FORCE_JAM_ACTION")
    monitor._trip(kind, "fault", source=source)

    assert gcode.run_script_from_command.call_args_list == [
        call("PAUSE"),
        call("M400"),
    ]
    assert monitor.actions.pending_recheck
