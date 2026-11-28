"""Regression tests for the optional learned-band jam action."""

from contextlib import nullcontext
from unittest.mock import Mock, call

import pytest

from filament_force.filament_force import FilamentForce
from filament_force.first_layer import FirstLayerZControl
from filament_force.force_signal import EWindowAccumulator, TripKind
from filament_force.pause import MonitorActions, MonitorTemplate
from filament_force.recovery import Recovery, RecoveryState


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
    result._recovery = Recovery()
    result._last_e_speed = 1.5
    result._live_e_speed = 0.0
    result._live_e_at = None
    result.diagnostic_enabled = False
    result.diagnostic_auto = False
    result._window = EWindowAccumulator(detection_length=8.0, rolling_window_s=0.1)
    return result


def configure_action(monitor: FilamentForce, name: str | None = None) -> None:
    config = Mock()
    section = Mock()
    section.get_name.return_value = name
    config.get_prefix_sections.return_value = [section] if name else []
    monitor._register_jam_action(config)


def test_both_weak_actions_are_registered(
    monitor: FilamentForce, gcode: Mock
) -> None:
    configure_action(monitor)
    assert gcode.register_command.call_args_list == [
        call("FILAMENT_FORCE_JAM_ACTION", monitor._default_jam_action),
        call("FILAMENT_FORCE_CONFIRMED_JAM_ACTION", monitor._default_confirmed_jam_action),
    ]
    monitor._default_jam_action(Mock())
    gcode.run_script_from_command.assert_called_once_with("PAUSE\nM400")


def test_custom_action_overrides_only_its_own_hook(
    monitor: FilamentForce, gcode: Mock
) -> None:
    configure_action(monitor, "gcode_macro filament_force_jam_action")
    gcode.register_command.assert_called_once_with(
        "FILAMENT_FORCE_CONFIRMED_JAM_ACTION", monitor._default_confirmed_jam_action
    )
    gcode.reset_mock()
    configure_action(monitor, "gcode_macro filament_force_confirmed_jam_action")
    gcode.register_command.assert_called_once_with(
        "FILAMENT_FORCE_JAM_ACTION", monitor._default_jam_action
    )


@pytest.mark.parametrize("source", ["band", "hard", "model_validation"])
def test_both_detectors_pause_then_invoke_preparation(
    monitor: FilamentForce, gcode: Mock, stats: Mock, legacy_hook: Mock,
    source: str,
) -> None:
    configure_action(monitor, "gcode_macro FILAMENT_FORCE_JAM_ACTION")

    def run(script: str) -> None:
        if script == "PAUSE\nM400":
            stats.get_status.return_value = {"state": "paused"}

    gcode.run_script_from_command.side_effect = run
    monitor._trip(TripKind.JAM, "700g", source=source, force_g=700.0)
    assert monitor.actions.pending_recheck
    assert monitor.actions.pending_tool == 0
    assert monitor.actions.pending_target == 400.0
    assert monitor.actions.pending_reason == "jam"
    assert monitor._recovery.state is RecoveryState.WAITING_DIAGNOSIS
    assert gcode.run_script_from_command.call_args_list == [
        call("PAUSE\nM400"),
        call("FILAMENT_FORCE_JAM_ACTION TOOL=0 FORCE_G=700.000 TARGET=400.00 FIRST_LAYER=1"
             f" SOURCE={source} E_SPEED={0.0 if source == 'hard' else 1.5:.3f}"),
        call("M400"),
    ]
    assert legacy_hook.call_args.args[0] is MonitorTemplate.JAM
    assert not monitor._recovery.clearance
    assert not monitor._triggering


def test_failing_custom_action_keeps_pause(
    monitor: FilamentForce, gcode: Mock, stats: Mock
) -> None:
    configure_action(monitor, "gcode_macro FILAMENT_FORCE_JAM_ACTION")

    def run(script: str) -> None:
        if script.startswith("FILAMENT_FORCE_JAM_ACTION"):
            raise RuntimeError("macro failed")
        stats.get_status.return_value = {"state": "paused"}

    gcode.run_script_from_command.side_effect = run
    monitor._trip(TripKind.JAM, "700g", source="band", force_g=700.0)
    assert monitor._recovery.state is RecoveryState.FAILED
    assert monitor.actions.pending_recheck
    assert stats.get_status.return_value["state"] == "paused"


def test_runout_retains_independent_pause(
    monitor: FilamentForce, gcode: Mock
) -> None:
    configure_action(monitor, "gcode_macro FILAMENT_FORCE_JAM_ACTION")
    monitor._trip(TripKind.RUNOUT, "fault", source="band")
    assert gcode.run_script_from_command.call_args_list == [
        call("PAUSE\nM400"),
    ]
    assert monitor.actions.pending_recheck


def test_no_pause_ack_blocks_preparation(
    monitor: FilamentForce, gcode: Mock
) -> None:
    configure_action(monitor)
    monitor._trip(TripKind.JAM, "fault", source="band")
    assert monitor._recovery.state is RecoveryState.FAILED
    assert gcode.run_script_from_command.call_args_list == [call("PAUSE\nM400")]
    monitor.printer.invoke_shutdown.assert_called_once()


def test_pause_exception_escalates_to_shutdown(monitor: FilamentForce, gcode: Mock) -> None:
    gcode.run_script_from_command.side_effect = RuntimeError("pause failed")
    monitor._trip(TripKind.JAM, "fault", source="hard")
    monitor.printer.invoke_shutdown.assert_called_once()
    assert monitor._recovery.state is RecoveryState.FAILED
