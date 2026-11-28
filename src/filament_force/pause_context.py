"""Fault pause ownership. Ordinary PAUSE/RESUME remain native commands."""
from dataclasses import dataclass
from uuid import uuid4


@dataclass
class PauseContext:
    pause_id: str | None = None
    reason: str = ""
    incident_id: str | None = None
    phase: str = "none"
    resume_mode: str | None = None

    @property
    def owned(self) -> bool:
        return self.phase == "paused"

    def request(self, reason: str, incident_id: str | None) -> None:
        self.pause_id = uuid4().hex
        self.reason = reason
        self.incident_id = incident_id
        self.phase = "requested"
        self.resume_mode = None

    def acknowledge(self) -> None:
        if self.phase != "requested":
            raise RuntimeError("fault pause not requested")
        self.phase = "paused"

    def resume(self, mode: str) -> None:
        if not self.owned or mode not in ("manual", "automatic"):
            raise RuntimeError("fault pause not owned")
        self.phase = "resumed"
        self.resume_mode = mode

    def status(self) -> dict[str, object]:
        return {
            "pause_id": self.pause_id,
            "pause_owner": "filament_force" if self.pause_id else None,
            "pause_reason": self.reason or None,
            "pause_incident_id": self.incident_id,
            "pause_phase": self.phase,
            "pause_requested": self.phase != "none",
            "pause_acknowledged": self.phase in ("paused", "resumed"),
            "resume_acknowledged": self.phase == "resumed",
            "resume_mode": self.resume_mode,
        }
