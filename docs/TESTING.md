# Testing

English | [简体中文](TESTING.zh-CN.md) · [Home](../README.md)

> Reference: main commit 25b359b. Automatic diagnosis, resume and Z compensation are opt-in and have not been qualified on hardware.

## Automated checks

```sh
uv sync
uv run pytest
uv run ty check src tests
```

Existing tests cover pure force windows, restored references, model persistence, free-air pulses, action registration, pause acknowledgement, recovery helpers and event journal. Passing unit tests is not proof of real motion safety. No full live printer-to-Hermes acceptance claimed.

## Hardware acceptance (record actual measurements)

| Test | Pass criterion |
|---|---|
| Baseline and healthy printing | No false trips under representative speed/PA/temperature; validated models |
| Statistical / hard detection | Both pause; capture source and trace without exceeding hardware limits (use safe simulated input where possible) |
| Manual diagnosis | Verified park, safe cap, correct nominal E speed and pulse length; low/mixed/limit stays paused |
| Non-first recovery | Normal diagnosis; correct resume path; healthy windows and bounded retry |
| First-layer correction | Positive gap confirmed physically; PAUSE_STATE restoration, cumulative limit and cleanup |
| Failure/cancel/restart | No stale callback or unintended resume; check owned offset |
| Remote bridge | One source event per ID in SQLite; matching payload; lifecycle events separate; reconnect and Hermes delivery |

Run tests in stages, keep automatic features disabled until relevant checks pass. Never intentionally overload a high-temperature system for a test. Record firmware SHA, plugin SHA, configuration, material, temperatures, force cap and outcomes. Outstanding: queued motion cancellation, full ADC archive, hardware acceptance.