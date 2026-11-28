# Public event protocol (schema 1)

[English](events.md) | [简体中文](events.zh-CN.md)

Filament Force is a standalone Klippy extra. Event production, local pause and recovery do not depend on Moonraker or any event consumer. Three interfaces are available: native Klippy events, the standard Moonraker object status journal, and optional named Moonraker notifications. The optional component only subscribes and broadcasts; it does not execute printer commands, route messages to external services or require an external process.

## Optional native Moonraker notifications

```bash
cd ~/klipper-filament-force
./install.sh ~/klipper --moonraker-dir ~/moonraker
```

Use the actual Klipper/Kalico and Moonraker checkout paths. The installer links a standalone component into moonraker/components, without modifying core source or automatically editing configuration. Add the section below to moonraker.conf and restart Moonraker while the printer is idle. If the component is not wanted, omit the option and section.

```ini
[filament_force_events]
```

```bash
sudo systemctl restart moonraker
```

Connect to the standard /websocket endpoint (normally port 7125), authenticate according to the server policy, and listen for these JSON-RPC notifications. No client-specific registration or subscription is required for the named notifications. The component registers notifications with Moonraker's register_notification API and uses a single internal objects subscription; it preserves the original payload.

| Klippy | Moonraker | Meaning |
|---|---|---|
| `filament_force:jam_detected` | `notify_filament_force_jam_detected` | Suspected jam |
| `filament_force:runout_detected` | `notify_filament_force_runout_detected` | Low force / feed fault |
| `filament_force:diagnosis_result` | `notify_filament_force_diagnosis_result` | Free-air diagnosis result |
| `filament_force:jam_confirmed` | `notify_filament_force_jam_confirmed` | Repeated high resistance |
| `filament_force:z_adjusted` | `notify_filament_force_z_adjusted` | Applied Z correction |
| `filament_force:recovery_started` | `notify_filament_force_recovery_started` | Resume acknowledged |
| `filament_force:recovery_verified` | `notify_filament_force_recovery_verified` | Healthy verification windows |
| `filament_force:recovery_failed` | `notify_filament_force_recovery_failed` | Recovery or protection failed |
| `filament_force:sensor_fault` | `notify_filament_force_sensor_fault` | Sensor or baseline fault |

## Example: jam notification

Synthetic example, not real printer measurements. Both jam_detected and jam_confirmed carry the original incident force window (the latter has window_event_id and diagnosis pulse statistics; window is null if the original snapshot is no longer available).

```json
{
  "jsonrpc": "2.0",
  "method": "notify_filament_force_jam_detected",
  "params": [
    {
      "schema": 1,
      "boot_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "seq": 12,
      "event_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:12",
      "incident_id": null,
      "kind": "jam_detected",
      "host_monotonic_s": 1200,
      "filename": "example.gcode",
      "source": "hard",
      "force_g": 4200,
      "tool": 0,
      "layer": 1,
      "e_speed_mm_s": 2.5,
      "target_c": 400,
      "detection_length_mm": 7,
      "absolute_limit_g": 4000,
      "window": {
        "clock": "mcu_print_time",
        "start_time": 100,
        "duration_s": 0.2,
        "sample_count": 3,
        "returned_count": 3,
        "downsampled": false,
        "force_ref_g": 100,
        "columns": [
          "t_s",
          "force_g"
        ],
        "samples": [
          [
            0,
            520
          ],
          [
            0.1,
            4300
          ],
          [
            0.2,
            4320
          ]
        ],
        "windows": []
      }
    }
  ]
}
```

The window contains calibrated force (gf), not raw ADC counts; samples include possible travel/idle. It is a bounded pre-handler trace, not the exact scoring accumulator or a precise trip cutoff. Min/max bucket downsampling preserves extrema but is lossy. Default 30 s / at most 512 output points, up to 40000 retained samples, 32 recent window summaries. The MCU print-time relative sample timestamps and host monotonic window/event timestamps must not be directly subtracted.

## Status subscription and history

```json
{"jsonrpc":"2.0","method":"printer.objects.subscribe","params":{"objects":{"filament_force":["events"]}},"id":1}
```

The above works with unmodified Moonraker even without the optional component. Use printer.objects.query or GET /printer/objects/query?filament_force=events for a snapshot. Klippy native listeners may register printer.register_event_handler('filament_force:jam_detected', handler), receiving one dictionary. Native listeners must be nonblocking.

```ini
[filament_force]
# ... existing settings
event_enabled: True
event_window_s: 30.0
event_max_points: 512
```

## Delivery semantics

The component broadcasts the retained initial snapshot and subsequent journal updates, deduplicated by boot_id and seq in the current Moonraker process. Reconnect to the same process does not re-broadcast previously seen events; a Moonraker restart may replay the last 16 events. Consumers should deduplicate using event_id and can query retained history after connecting. Initial detection has incident_id=null, later events refer to its event_id. A sequence gap can be logged but discarded data cannot be recovered. This is best-effort broadcast, not a durable queue, per-client ACK or exactly-once transport. The journal is finite and resets with Klippy; disconnects, shutdowns and long outages may lose events. Local protection never waits for notification delivery.

Klipper/Moonraker API integration and actual broadcast latency require testing on the target printer. The supplied automated tests simulate Moonraker's component API; no physical printer motion is involved.
