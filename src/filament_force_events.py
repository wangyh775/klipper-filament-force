"""Optional Moonraker component: register and broadcast Filament Force events.

This file runs in Moonraker, not Klippy. It has no consumer dependencies.
"""
from collections import OrderedDict
from copy import deepcopy
import logging
from typing import Any

KINDS = (
    "jam_detected", "runout_detected", "diagnosis_result", "jam_confirmed",
    "z_adjusted", "recovery_started", "recovery_verified", "recovery_failed",
    "sensor_fault",
)
OBJECT = "filament_force"
SECTION = "filament_force_events"


class FilamentForceEvents:
    def __init__(self, config: Any) -> None:
        self.server = config.get_server()
        self.klippy = self.server.lookup_component("klippy_apis")
        # Bounded per-boot watermarks. Keep across Klippy reconnects to the
        # same Moonraker process; no disk, ACKs or consumer-specific routing.
        self._seen: OrderedDict[str, int] = OrderedDict()
        self._generation = 0
        self._subscribed = False
        for kind in KINDS:
            self.server.register_notification(
                f"{SECTION}:{kind}", f"filament_force_{kind}")
        self.server.register_event_handler("server:klippy_ready", self._ready)
        self.server.register_event_handler("server:klippy_disconnect", self._disconnect)

    def _disconnect(self) -> None:
        self._generation += 1
        self._subscribed = False

    async def _ready(self) -> None:
        if self._subscribed:
            return
        generation = self._generation
        try:
            objects = await self.klippy.get_object_list(default=[])
            if generation != self._generation or OBJECT not in objects:
                return
            def on_status(status: dict[str, Any], eventtime: float) -> None:
                if generation == self._generation:
                    self._status(status, eventtime)
            snapshot = await self.klippy.subscribe_objects(
                {OBJECT: ["events"]}, callback=on_status, default=None)
            if generation != self._generation or snapshot is None:
                return
            self._subscribed = True
            self._status(snapshot, 0.0)
        except Exception:
            logging.exception("filament_force_events: unable to subscribe; "
                              "local printer protection is independent")

    def _status(self, status: dict[str, Any], eventtime: float) -> None:
        del eventtime
        obj = status.get(OBJECT)
        if not isinstance(obj, dict):
            return
        events = obj.get("events")
        if not isinstance(events, list):
            return
        valid = []
        for event in events[-16:]:
            if not isinstance(event, dict):
                continue
            boot, seq, kind = (event.get(k) for k in ("boot_id", "seq", "kind"))
            if (type(event.get("schema")) is not int or event["schema"] != 1
                    or not isinstance(boot, str) or len(boot) != 32
                    or any(c not in "0123456789abcdef" for c in boot)
                    or type(seq) is not int or not 0 < seq < 2**63
                    or not isinstance(kind, str) or kind not in KINDS
                    or event.get("event_id") != f"{boot}:{seq}"):
                continue
            valid.append(event)
        for event in sorted(valid, key=lambda e: (e["boot_id"], e["seq"])):
            boot, seq = event["boot_id"], event["seq"]
            previous = self._seen.get(boot, 0)
            if seq <= previous:
                continue
            if previous and seq > previous + 1:
                logging.warning("filament_force_events: journal gap boot=%s seq=%s..%s",
                                boot, previous + 1, seq - 1)
            # Preserve the entire schema-1 payload, including nested force
            # samples, and let Moonraker enforce its client auth policy.
            self.server.send_event(f"{SECTION}:{event['kind']}", deepcopy(event))
            self._seen[boot] = seq
            self._seen.move_to_end(boot)
            if len(self._seen) > 8:
                self._seen.popitem(last=False)


def load_component(config: Any) -> FilamentForceEvents:
    return FilamentForceEvents(config)
