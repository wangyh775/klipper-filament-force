"""Regression tests for the optional learned-band jam action."""

from contextlib import nullcontext
from typing import cast
from unittest.mock import Mock, call

import pytest

from filament_force.filament_force import FilamentForce, OhShitCal
from filament_force.first_layer import FirstLayerZControl
from filament_force.free_air import FreeAirDiagnostic
from filament_force.force_signal import EWindowAccumulator, TripKind
from filament_force.pause import MonitorActions, MonitorTemplate
from filament_force.pause_context import PauseContext
from filament_force.recovery import Recovery, RecoveryState
from filament_force.protection import SampleHealth
from filament_force.z_ownership import ZOwnership


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
    result._protection_queued_at = None
    result._protection_escalated = False
    result._diagnostic_stop_queued = False
    result.diagnostic_shutdown_on_limit = True
    result._recovery = Recovery()
    result._pause_context = PauseContext()
    result._z_ownership = ZOwnership()
    result._last_e_speed = 1.5
    result._live_e_speed = 0.0
    result._live_e_at = None
    result.diagnostic_max_sample_gap_s = 0.05
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
        call("FILAMENT_FORCE_PAUSE_ACTION", monitor._default_fault_pause_action),
        call("FILAMENT_FORCE_RESUME_ACTION", monitor._default_fault_resume_action),
    ]
    monitor._default_jam_action(Mock())
    gcode.run_script_from_command.assert_called_once_with("PAUSE\nM400")


def test_custom_action_overrides_only_its_own_hook(
    monitor: FilamentForce, gcode: Mock
) -> None:
    configure_action(monitor, "gcode_macro filament_force_jam_action")
    gcode.register_command.assert_any_call(
        "FILAMENT_FORCE_CONFIRMED_JAM_ACTION", monitor._default_confirmed_jam_action
    )
    assert gcode.register_command.call_count == 3
    gcode.reset_mock()
    configure_action(monitor, "gcode_macro filament_force_confirmed_jam_action")
    gcode.register_command.assert_any_call(
        "FILAMENT_FORCE_JAM_ACTION", monitor._default_jam_action
    )
    assert gcode.register_command.call_count == 3


@pytest.mark.parametrize("source", ["band", "hard", "model_validation"])
def test_both_detectors_pause_then_invoke_preparation(
    monitor: FilamentForce, gcode: Mock, stats: Mock, legacy_hook: Mock,
    source: str,
) -> None:
    configure_action(monitor, "gcode_macro FILAMENT_FORCE_JAM_ACTION")

    def run(script: str) -> None:
        if script == "FILAMENT_FORCE_PAUSE_ACTION REASON=jam\nM400":
            stats.get_status.return_value = {"state": "paused"}

    gcode.run_script_from_command.side_effect = run
    monitor._trip(TripKind.JAM, "700g", source=source, force_g=700.0)
    assert monitor.actions.pending_recheck
    assert monitor.actions.pending_tool == 0
    assert monitor.actions.pending_target == 400.0
    assert monitor.actions.pending_reason == "jam"
    assert monitor._recovery.state is RecoveryState.WAITING_DIAGNOSIS
    assert gcode.run_script_from_command.call_args_list == [
        call("FILAMENT_FORCE_PAUSE_ACTION REASON=jam\nM400"),
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
        call("FILAMENT_FORCE_PAUSE_ACTION REASON=runout\nM400"),
    ]
    assert monitor.actions.pending_recheck


def test_no_pause_ack_blocks_preparation(
    monitor: FilamentForce, gcode: Mock
) -> None:
    configure_action(monitor)
    monitor._trip(TripKind.JAM, "fault", source="band")
    assert monitor._recovery.state is RecoveryState.FAILED
    assert gcode.run_script_from_command.call_args_list == [call("FILAMENT_FORCE_PAUSE_ACTION REASON=jam\nM400")]
    cast(Mock, monitor.printer).invoke_shutdown.assert_called_once()


def test_pause_exception_escalates_to_shutdown(monitor: FilamentForce, gcode: Mock) -> None:
    gcode.run_script_from_command.side_effect = RuntimeError("pause failed")
    monitor._trip(TripKind.JAM, "fault", source="hard")
    cast(Mock, monitor.printer).invoke_shutdown.assert_called_once()
    assert monitor._recovery.state is RecoveryState.FAILED


def test_watchdog_stops_print_when_stream_is_stale(
    monitor: FilamentForce, gcode: Mock, stats: Mock,
) -> None:
    monitor.enabled = True
    monitor._sample_health = SampleHealth()
    monitor.sensor_timeout_s = 2.0
    monitor._watchdog_started = 0.0
    monitor._protection_queued = False
    monitor._force_ref_locked = False
    monitor._baseline_wait_since = None
    monitor._diag = FreeAirDiagnostic()
    monitor._cal = OhShitCal()
    monitor._spike.active = False
    reactor = cast(Mock, monitor.reactor)
    monitor._protection_watchdog(1.9)
    reactor.register_callback.assert_not_called()
    monitor._protection_watchdog(2.0)
    callback = reactor.register_callback.call_args.args[0]
    monitor._protection_watchdog(2.25)
    reactor.register_callback.assert_called_once()

    # The simulated G-code script contains an actual newline.
    gcode.run_script_from_command.side_effect = lambda _script: stats.get_status.configure_mock(
        return_value={"state": "paused"}
    )
    callback(2.25)
    assert monitor.actions.pending_reason == "protection"
    assert monitor._recovery.state is RecoveryState.FAILED
    assert monitor._protection_fault == "load cell stream stale"
    assert not monitor._protection_queued
    cast(Mock, monitor.printer).invoke_shutdown.assert_not_called()


def test_stale_watchdog_callback_cannot_pause_new_job(
    monitor: FilamentForce, gcode: Mock,
) -> None:
    monitor.enabled = True
    monitor._protection_queued = True
    monitor._diag_generation = 2
    monitor._stop_unprotected(1, "load cell stream stale")
    assert not monitor._protection_queued
    gcode.run_script_from_command.assert_not_called()


def test_z_cleanup_checks_observed_origin(
    monitor: FilamentForce, gcode: Mock, stats: Mock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stats.get_status.return_value = {"state": "complete"}
    owned = monitor._z_ownership
    owned.stage(.1, .12, .02)
    owned.commit(.12)
    owned.finish_job()
    origin = Mock(side_effect=[.12, .1])
    monkeypatch.setattr(monitor, "_current_z_origin", origin)
    monitor._undo_recovery_z(monitor._diag_generation)
    gcode.run_script_from_command.assert_called_once_with("SET_GCODE_OFFSET Z_ADJUST=-0.020000 MOVE=0")
    assert not owned.cleanup_pending and owned.applied_mm == 0


def test_z_cleanup_refuses_new_print_without_losing_record(
    monitor: FilamentForce, gcode: Mock,
) -> None:
    owned = monitor._z_ownership
    owned.stage(.1, .12, .02)
    owned.commit(.12)
    owned.finish_job()
    monitor._undo_recovery_z(monitor._diag_generation)
    gcode.run_script_from_command.assert_not_called()
    assert owned.cleanup_pending and owned.uncertain and owned.applied_mm == .02


def test_z_cleanup_callback_does_not_touch_new_generation(
    monitor: FilamentForce, gcode: Mock,
) -> None:
    owned = monitor._z_ownership
    owned.stage(.1, .12, .02)
    owned.commit(.12)
    owned.finish_job()
    monitor._undo_recovery_z(monitor._diag_generation - 1)
    gcode.run_script_from_command.assert_not_called()
    assert owned.cleanup_pending and not owned.uncertain


def test_manual_recovery_preparation_failure_keeps_pending_reason(
    monitor: FilamentForce, gcode: Mock, stats: Mock, legacy_hook: Mock,
) -> None:
    stats.get_status.return_value = {"state": "paused"}
    monitor._diag = FreeAirDiagnostic()
    monitor.actions.set_pending(tool=0, target=400, reason="jam")
    monitor._pause_context.request("jam", None)
    monitor._pause_context.acknowledge()
    monitor._recovery.fail("jam")
    monitor._recovery.record_auto_attempt(first=False)
    legacy_hook.side_effect = RuntimeError("recover macro failed")
    command = Mock()
    command.get.return_value = None
    command.error.side_effect = lambda message: RuntimeError(message)
    with pytest.raises(RuntimeError, match="manual recovery failed"):
        monitor.cmd_FILAMENT_FORCE_RESUME(command)
    assert monitor.actions.pending_recheck and monitor.actions.pending_reason == "jam"
    assert monitor._recovery.state is RecoveryState.FAILED
    assert monitor._recovery.manual_attempts == 1
    assert monitor._recovery.attempts == 1
    gcode.run_script_from_command.assert_not_called()


def test_failure_transition_publishes_once(monitor: FilamentForce, monkeypatch: pytest.MonkeyPatch) -> None:
    publish = Mock()
    monkeypatch.setattr(monitor, "_publish_event", publish)
    monitor._recovery.prepare()
    monitor._fail_recovery("timeout")
    monitor._fail_recovery("timeout")
    publish.assert_called_once_with("recovery_failed", reason="timeout", previous_state="preparing")
    monitor._recovery.prepare()
    monitor._fail_recovery("timeout")
    assert publish.call_count == 2


def test_watchdog_sensor_event_links_failure(monitor: FilamentForce, gcode: Mock,
                                             stats: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    from filament_force.events import EventJournal

    monitor.enabled = True
    monitor.event_enabled = True
    monitor.sensor_name = "load_cell_probe"
    monitor._sample_health = SampleHealth()
    monitor._event_journal = EventJournal()
    monitor._incident_id = None
    monitor._incident_filename = ""
    monitor._force_ref_locked = False
    monitor._protection_queued = True
    cast(Mock, monitor.reactor).monotonic.return_value = 3.0
    gcode.run_script_from_command.side_effect = lambda _script: stats.get_status.configure_mock(
        return_value={"state": "paused"}
    )
    monitor._stop_unprotected(monitor._diag_generation, "load cell stream stale")
    events = monitor._event_journal.status()
    assert [e["kind"] for e in events] == ["sensor_fault", "recovery_failed", "pause"]
    assert events[0]["window"]["samples"] == []
    assert events[1]["incident_id"] == events[0]["event_id"]
    assert monitor.actions.pending_reason == "protection"


def test_d_fault_z_cleanup_command_exception_retains_ownership(
    monitor: FilamentForce, gcode: Mock, stats: Mock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stats.get_status.return_value = {"state": "complete"}
    owned = monitor._z_ownership
    owned.stage(.1, .12, .02)
    owned.commit(.12)
    owned.finish_job()
    monkeypatch.setattr(monitor, "_current_z_origin", lambda: .12)
    gcode.run_script_from_command.side_effect = RuntimeError("injected offset failure")
    monitor._undo_recovery_z(monitor._diag_generation)
    assert owned.applied_mm == .02 and owned.cleanup_pending and owned.uncertain


def test_d_fault_observer_exception_does_not_prevent_fault_pause(
    monitor: FilamentForce, gcode: Mock, stats: Mock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from filament_force.events import EventJournal

    monitor.event_enabled = True
    monitor._event_journal = EventJournal()
    monitor._incident_id = None
    monitor._incident_filename = ""
    cast(Mock, monitor.reactor).monotonic.return_value = 3.0
    cast(Mock, monitor.printer).send_event.side_effect = RuntimeError("listener crash")
    monitor._publish_event("recovery_failed", reason="injected")
    callback = cast(Mock, monitor.reactor).register_callback.call_args.args[0]
    callback(3.0)
    gcode.run_script_from_command.side_effect = lambda _script: stats.get_status.configure_mock(
        return_value={"state": "paused"}
    )
    assert monitor._ensure_fault_pause("injected")
    assert monitor._event_journal.status()[0]["reason"] == "injected"


def test_d_fault_resume_macro_continues_print_after_sensor_stops(monitor: FilamentForce) -> None:
    monitor.enabled = True
    monitor._sample_health = SampleHealth(last_mcu=1.0, last_host=0.0)
    monitor.sensor_timeout_s = 2.0
    monitor._watchdog_started = 0.0
    monitor._protection_queued = False
    monitor._force_ref_locked = True
    monitor._baseline_wait_since = None
    monitor._diag = FreeAirDiagnostic()
    monitor._cal = OhShitCal()
    monitor._spike.active = False
    monitor._recovery.state = RecoveryState.RESUMING
    monitor._protection_watchdog(3.0)
    assert cast(Mock, monitor.reactor).register_callback.called


def test_d_fault_native_listener_cannot_mutate_retained_event(
    monitor: FilamentForce,
) -> None:
    from filament_force.events import EventJournal

    monitor.event_enabled = True
    monitor._event_journal = EventJournal()
    monitor._incident_id = None
    monitor._incident_filename = ""
    cast(Mock, monitor.reactor).monotonic.return_value = 3.0

    def mutate(_name: str, payload: dict[str, object]) -> None:
        payload["kind"] = "corrupted"

    cast(Mock, monitor.printer).send_event.side_effect = mutate
    monitor._publish_event("recovery_failed", reason="injected")
    cast(Mock, monitor.reactor).register_callback.call_args.args[0](3.0)
    assert monitor._event_journal.status()[0]["kind"] == "recovery_failed"


def test_protection_escalates_if_pause_callback_cannot_acquire_mutex(monitor: FilamentForce) -> None:
    monitor.enabled = True
    monitor._sample_health = SampleHealth(last_mcu=1.0, last_host=0.0)
    monitor.sensor_timeout_s = 2.0
    monitor._watchdog_started = 0.0
    monitor._protection_queued = False
    monitor._force_ref_locked = True
    monitor._baseline_wait_since = None
    monitor._recovery.state = RecoveryState.RESUMING
    monitor._protection_watchdog(3.0)
    monitor._protection_watchdog(4.9)
    cast(Mock, monitor.printer).invoke_shutdown.assert_not_called()
    monitor._protection_watchdog(5.0)
    monitor._protection_watchdog(6.0)
    cast(Mock, monitor.printer).invoke_shutdown.assert_called_once()


def test_diagnostic_shutdown_is_latched_and_mutex_free(monitor: FilamentForce) -> None:
    d = FreeAirDiagnostic(limit_hit=True)
    monitor._queue_diagnostic_shutdown(d)
    monitor._queue_diagnostic_shutdown(d)
    reactor = cast(Mock, monitor.reactor)
    reactor.register_callback.assert_called_once()
    reactor.register_callback.call_args.args[0](1.0)
    cast(Mock, monitor.printer).invoke_shutdown.assert_called_once()


def test_custom_fault_macros_registered_independently(monitor: FilamentForce, gcode: Mock) -> None:
    configure_action(monitor, "gcode_macro FILAMENT_FORCE_PAUSE_ACTION")
    commands = [c.args[0] for c in gcode.register_command.call_args_list]
    assert "FILAMENT_FORCE_PAUSE_ACTION" not in commands
    assert "FILAMENT_FORCE_RESUME_ACTION" in commands
    gcode.reset_mock()
    configure_action(monitor, "gcode_macro FILAMENT_FORCE_RESUME_ACTION")
    commands = [c.args[0] for c in gcode.register_command.call_args_list]
    assert "FILAMENT_FORCE_RESUME_ACTION" not in commands
    assert "FILAMENT_FORCE_PAUSE_ACTION" in commands
    assert monitor._custom_resume_action


def test_ordinary_pause_not_claimed(monitor: FilamentForce, gcode: Mock, stats: Mock) -> None:
    stats.get_status.return_value = {"state": "paused"}
    assert monitor._ensure_fault_pause("jam")
    assert not monitor._pause_context.owned
    gcode.run_script_from_command.assert_not_called()


def test_owned_pause_resume_share_identifier(monitor: FilamentForce, gcode: Mock,
                                             stats: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    publish = Mock()
    monkeypatch.setattr(monitor, "_publish_event", publish)
    monitor.actions.set_pending(reason="jam")
    monitor._incident_id = "incident"
    gcode.run_script_from_command.side_effect = lambda _s: stats.get_status.configure_mock(
        return_value={"state": "paused"})
    assert monitor._ensure_fault_pause("jam")
    assert monitor._ensure_fault_pause("jam")
    assert publish.call_count == 1
    pause_id = monitor._pause_context.pause_id
    gcode.run_script_from_command.side_effect = lambda _s: stats.get_status.configure_mock(
        return_value={"state": "printing"})
    monitor._execute_fault_resume("30", "manual")
    monitor._acknowledge_fault_resume("manual")
    assert publish.call_args.args == ("resume",)
    assert publish.call_args.kwargs["pause_id"] == pause_id
    assert publish.call_args.kwargs["pause_incident_id"] == "incident"
    assert publish.call_args.kwargs["resume_mode"] == "manual"
    assert not monitor._pause_context.owned
    gcode.run_script_from_command.assert_called_with(
        "FILAMENT_FORCE_RESUME_ACTION MODE=manual REASON=jam VELOCITY=30")


def test_fault_resume_without_pending_does_not_resume_normal_pause(
    monitor: FilamentForce, gcode: Mock, stats: Mock,
) -> None:
    stats.get_status.return_value = {"state": "paused"}
    monitor._diag = FreeAirDiagnostic()
    command = Mock()
    command.get.return_value = None
    monitor.cmd_FILAMENT_FORCE_RESUME(command)
    gcode.run_script_from_command.assert_not_called()


def test_weak_defaults_reuse_native_commands(monitor: FilamentForce, gcode: Mock) -> None:
    monitor.actions.has_template = {}
    monitor._default_fault_pause_action(Mock())
    command = Mock()
    command.get.return_value = "25"
    monitor._default_fault_resume_action(command)
    assert gcode.run_script_from_command.call_args_list == [call("PAUSE"), call("RESUME VELOCITY=25")]
