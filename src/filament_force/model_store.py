"""Versioned, atomic persistence of healthy filament-force windows.

Never persist a tare, live force, fault streak, or pending pause. Files are
untrusted: reject incompatible parameters and malformed data before restoring.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .force_signal import ToolForceBook

SCHEMA_VERSION = 1
MAX_TOOLS = 32
MAX_FORCE_G = 100000.0


@dataclass
class ModelLoadResult:
    state: str
    books: dict[int, ToolForceBook]
    reason: str = ""


def _samples(value: object, limit: int) -> list[float]:
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError("invalid sample list or history length")
    out: list[float] = []
    for number in value:
        if type(number) not in (float, int):
            raise ValueError("model sample must be numeric")
        sample = float(number)
        if not math.isfinite(sample) or not 0 <= sample <= MAX_FORCE_G:
            raise ValueError("nonfinite or out-of-range model sample")
        out.append(sample)
    return out


def snapshot(
    books: Mapping[int, ToolForceBook], fingerprint: dict[str, object]
) -> dict[str, object]:
    tools: dict[str, object] = {}
    for key, book in sorted(books.items()):
        # Save only the healthy model samples, never transient trip state.
        tools[str(key)] = {
            "bins": [list(hist.windows) for hist in book.bins],
            "runout": list(book.runout.windows),
        }
    return {
        "version": SCHEMA_VERSION,
        "fingerprint": fingerprint,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "tools": tools,
    }


def decode(
    data: object,
    fingerprint: dict[str, object],
    *,
    n_bins: int,
    history_n: int,
    min_learn_windows: int,
) -> ModelLoadResult:
    if not isinstance(data, dict) or type(data.get("version")) is not int:
        return ModelLoadResult("invalid", {}, "missing schema version")
    if data["version"] != SCHEMA_VERSION:
        return ModelLoadResult("incompatible", {}, "schema version changed")
    if data.get("fingerprint") != fingerprint:
        return ModelLoadResult("incompatible", {}, "model profile or configuration changed")
    tools = data.get("tools")
    if not isinstance(tools, dict) or len(tools) > MAX_TOOLS:
        return ModelLoadResult("invalid", {}, "invalid tool model collection")
    result: dict[int, ToolForceBook] = {}
    try:
        for name, payload in tools.items():
            if not isinstance(name, str) or not isinstance(payload, dict):
                raise ValueError("invalid tool entry")
            if name.startswith("+") or str(int(name)) != name:
                raise ValueError("invalid tool identifier")
            tool = int(name)
            if tool < -1 or tool > 1024:
                raise ValueError("tool out of range")
            entries = payload.get("bins")
            if not isinstance(entries, list) or len(entries) != n_bins:
                raise ValueError("wrong number of speed bins")
            book = ToolForceBook(n_bins, history_n, min_learn_windows)
            for hist, samples in zip(book.bins, entries):
                hist.windows.extend(_samples(samples, history_n))
            book.runout.windows.extend(_samples(payload.get("runout"), history_n))
            result[tool] = book
    except (ValueError, TypeError, OverflowError) as exc:
        return ModelLoadResult("invalid", {}, str(exc))
    return ModelLoadResult("loaded", result)


class ModelStore:
    def __init__(self, filename: str) -> None:
        self.path = Path(os.path.expanduser(filename))

    def load(
        self,
        fingerprint: dict[str, object],
        *,
        n_bins: int,
        history_n: int,
        min_learn_windows: int,
    ) -> ModelLoadResult:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return ModelLoadResult("missing", {})
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            return ModelLoadResult("invalid", {}, str(exc))
        return decode(
            data, fingerprint, n_bins=n_bins, history_n=history_n,
            min_learn_windows=min_learn_windows,
        )

    def save(
        self, books: Mapping[int, ToolForceBook], fingerprint: dict[str, object]
    ) -> None:
        payload = snapshot(books, fingerprint)
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        fd, tempname = tempfile.mkstemp(prefix=".filament_force_", suffix=".tmp", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, allow_nan=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tempname, self.path)
        finally:
            if os.path.exists(tempname):
                os.unlink(tempname)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
