import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, Mock

from filament_force_events import FilamentForceEvents, KINDS
from filament_force.events import EventJournal
from filament_force.force_signal import Sample


def fixture():
    config = Mock()
    server = config.get_server.return_value
    api = server.lookup_component.return_value
    api.get_object_list = AsyncMock(return_value=["filament_force"])
    api.subscribe_objects = AsyncMock(return_value={"filament_force": {"events": []}})
    bridge = FilamentForceEvents(config)
    return bridge, server, api


def test_register_all_native_moonraker_notifications() -> None:
    bridge, server, api = fixture()
    assert server.register_notification.call_count == len(KINDS)
    server.register_notification.assert_any_call(
        "filament_force_events:jam_detected", "filament_force_jam_detected")
    asyncio.run(bridge._ready())
    assert api.subscribe_objects.call_args.args[0] == {"filament_force": ["events"]}
    api.subscribe_objects.assert_awaited_once()


def test_jam_broadcast_retains_full_window_and_deduplicates() -> None:
    bridge, server, _ = fixture()
    journal = EventJournal()
    journal.note(Sample(1., 500.))
    journal.note(Sample(1.01, 4300.))
    window = journal.trace(200.)
    event = journal.emit("jam_detected", window=window)
    confirmed = journal.emit("jam_confirmed", incident_id=event["event_id"],
                             window=journal.incident_window(event["event_id"]))
    snapshot = {"filament_force": {"events": [confirmed, event]}}
    bridge._status(snapshot, 1.)
    bridge._status(snapshot, 2.)
    assert server.send_event.call_count == 2
    calls = server.send_event.call_args_list
    assert calls[0].args == ("filament_force_events:jam_detected", event)
    assert calls[1].args == ("filament_force_events:jam_confirmed", confirmed)
    assert calls[0].args[1]["window"] == window
    assert calls[1].args[1]["window"] == window
    snapshot["filament_force"]["events"][1]["window"]["samples"][0][1] = 0
    assert calls[0].args[1]["window"]["samples"][0][1] == 500.


def test_reconnect_same_boot_and_new_boot() -> None:
    bridge, server, api = fixture()
    journal = EventJournal()
    journal.emit("jam_detected", window=journal.trace(None))
    api.subscribe_objects.return_value = {"filament_force": {"events": journal.status()}}
    asyncio.run(bridge._ready())
    callback = api.subscribe_objects.call_args.kwargs["callback"]
    bridge._disconnect()
    journal.emit("recovery_failed", reason="test")
    callback({"filament_force": {"events": journal.status()}}, 1.)
    assert server.send_event.call_count == 1
    api.subscribe_objects.return_value = {"filament_force": {"events": journal.status()}}
    asyncio.run(bridge._ready())
    assert server.send_event.call_count == 2
    bridge._disconnect()
    new = EventJournal()
    new.emit("jam_detected", window=new.trace(None))
    api.subscribe_objects.return_value = {"filament_force": {"events": new.status()}}
    asyncio.run(bridge._ready())
    assert server.send_event.call_count == 3


def test_missing_extra_or_malformed_event_is_harmless() -> None:
    bridge, server, api = fixture()
    api.get_object_list.return_value = []
    asyncio.run(bridge._ready())
    api.subscribe_objects.assert_not_awaited()
    journal = EventJournal()
    event = journal.emit("jam_detected", window=journal.trace(None))
    malformed = deepcopy(event)
    malformed["seq"] = True
    bridge._status({"filament_force": {"events": [None, malformed]}}, 0.)
    server.send_event.assert_not_called()
