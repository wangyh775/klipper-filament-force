# Troubleshooting

English | [简体中文](TROUBLESHOOTING.zh-CN.md) · [Home](../README.md)

> Reference: main commit 25b359b. Automatic diagnosis, resume and Z compensation are opt-in and have not been qualified on hardware.

| Symptom | Check / action |
|---|---|
| Not armed | Print state, continuous enable, suppression, sensor and idle reference |
| Repeated false JAM | Query last_trip_source; compare force windows; PA, acceleration, flow and inertial load; supervised A/B tests before increasing threshold |
| Model missing/uncertain | Profile, path permissions, fingerprint, save error, valid healthy windows; never reset merely to suppress alarm |
| Diagnosis refused | paused job, known tool/temperature, diagnostic limit, safe clearance, one attempt per incident |
| Flow-compatible but no resume | opt-in, known layer, trusted bins, speed gate, explicit resume_gcode, budget |
| Z not applied | layer info, original homing/height, PAUSE_STATE and resume macro, offset direction and caps |
| Missing remote event | query filament_force.events; Monitor subscription enabled; reconnect retention only 16 events |
| Force trace short | actual sensor stream, 40,000-point memory cap, window resets; not full ADC export |

Collect FILAMENT_FORCE_QUERY, klippy.log and configuration before changing thresholds. Debug logs: FILAMENT_FORCE_SET DEBUG_LOG=1. Do not disable hard protection to investigate.

A cold-start or reset history is not independently healthy. Preserve existing data until the fault is understood; see [commissioning](USER_GUIDE.md#advanced-calibration-and-false-alarms).
