# Configuration

English | [简体中文](CONFIGURATION.zh-CN.md) · [Home](../README.md)

> Reference: main commit 25b359b. Automatic diagnosis, resume and Z compensation are opt-in and have not been qualified on hardware.

All entries belong to [filament_force]. Defaults below are source defaults, not recommended safety limits. Keep min_learn_windows ≤ history_n. `SET` is runtime only; change CFG and restart for persistence except the calibration SAVE_CONFIG path. A sampling geometry change or history rebuild invalidates learning; supervise the next print. Changing process conditions also needs a separate profile. Runtime changes are rejected in active recovery stages.

| Option | Default | Unit | Range | Runtime SET | Meaning |
|---|---|---|---|---|---|
| `sensor` | `load_cell_probe` | object | — | — | Load-cell object |
| `extruder` | `extruder` | object | — | — | Extruder object |
| `continuous_detection` | `True` | bool | — | ENABLE | Initial detection enable |
| `detection_length` | `7` | mm | >0 | ✓ | Forward E window; model reset |
| `min_e_speed` | `0.5` | mm/s | >0 | ✓ | Minimum eligible speed; reset |
| `rolling_window` | `0.05` | s | >0 | — | Trailing mean |
| `baseline_time` | `0.15` | s | >0 | — | Idle reference interval |
| `min_delta_g` | `15` | gf | >0 | ✓ | Deviation floor |
| `high_sigma` | `4` | — | >0 | ✓ | High bound multiplier |
| `sigma_jam` | `True` | bool | — | ✓ | Enable statistical HIGH |
| `drop_ratio` | `0.35` | — | 0–1 | ✓ | Low relative cap |
| `runout_max_level_g` | `80` | gf | ≥0 | ✓ | Low absolute cap |
| `confirm_windows` | `3` | count | ≥1 | ✓ | Anomaly confirmation |
| `confirm_max_gap_s` | `30` | s | >0 | — | Maximum eligible gap |
| `recover_windows` | `2` | count | ≥1 | ✓ | Healthy recovery streak |
| `history_n` | `16` | count | ≥5 | ✓ | History capacity; rebuild |
| `min_learn_windows` | `5` | count | ≥2 | ✓ | Learning count; rebuild |
| `speed_bins` | `1,2,4,7` | mm/s | positive sorted | ✓ | Bin edges; rebuild |
| `oh_shit_force` | `4000` | gf | >0 | ✓ | Absolute threshold; calibrate |
| `jam_dwell_s` | `0.15` | s | >0 | — | Hard force dwell |
| `poll_interval_ms` | `250` | ms | 50–2000 | — | E position polling |
| `idle_reset_s` | `0.3` | s | >0 | ✓ | Partial window idle reset |
| `min_learn_s` | `1.5` | s | ≥0 | ✓ | First bead duration gate |
| `probe_retract_mm` | `3` | mm | >0 | ✓ | Presence test retract |
| `probe_extra_prime_mm` | `0.2` | mm | ≥0 | ✓ | Extra prime |
| `probe_spike_g` | `50` | gf | >0 | ✓ | Presence threshold |
| `probe_feedrate` | `30` | mm/s | >0 | ✓ | Probe speed |
| `quiet` | `False` | bool | — | ✓ | Suppress routine messages |
| `debug_log` | `False` | bool | — | ✓ | Window logs |
| `model_persistence` | `True` | bool | — | — | Store healthy model |
| `model_file` | `~/printer_data/config/filament_force_model.json` | path | — | — | Model file |
| `model_profile` | `default` | text | — | — | Process profile |
| `model_save_interval` | `60` | s | >0 | — | Periodic save |
| `diagnostic_enabled` | `False` | bool | — | — | Enable free-air test |
| `diagnostic_auto` | `False` | bool | — | — | Auto after clearance |
| `diagnostic_match_speed` | `False` | bool | — | — | Match within configured cap |
| `diagnostic_speed` | `3` | mm/s | 0.5–6 | — | Fixed speed / matching cap |
| `diagnostic_pulse_mm` | `0.5` | mm | 0.5–3 | — | Minimum pulse length |
| `diagnostic_pulses` | `3` | count | 2–3 | — | Pulse count |
| `diagnostic_force_limit` | `0` | gf | ≥0 | — | Must calibrate positive cap |
| `diagnostic_force_min` | `0` | gf | ≥0 | — | Manual lower fallback |
| `diagnostic_force_max` | `0` | gf | ≥0 | — | Manual upper fallback |
| `diagnostic_baseline_span` | `30` | gf | >0 | — | Idle stability cap |
| `auto_resume_enabled` | `False` | bool | — | — | Opt-in resume |
| `auto_resume_max_attempts` | `2` | count | 1–5 | — | Ordinary consecutive budget |
| `auto_resume_reset_s` | `60` | s | >0 | — | Healthy duration to reset |
| `auto_resume_verify_windows` | `3` | count | ≥1 | — | Ordinary healthy windows |
| `recovery_verify_timeout` | `60` | s | >0 | — | Verification timeout |
| `first_layer_z_enabled` | `False` | bool | — | — | Opt-in Z |
| `first_layer_z_step` | `0.02` | mm | (0,0.05] | — | Step |
| `first_layer_z_max_adjustments` | `3` | count | 1–10 | — | Per-job step count |
| `first_layer_z_max_total` | `0.06` | mm | (0,0.2] | — | Per-job gap budget |
| `first_layer_z_cooldown_s` | `10` | s | ≥0 | — | Between adjustments |
| `first_layer_z_max_height` | `0.60` | mm | >0 | — | Original Z gate |
| `first_layer_z_max_force` | `2000` | gf | >0 | — | Diagnostic pulse mean gate |
| `first_layer_verify_windows` | `2` | count | ≥1 | — | Healthy windows |
| `first_layer_min_improvement` | `0.15` | ratio | (0,1] | — | Retry improvement threshold |
| `event_enabled` | `True` | bool | — | — | Event journal |
| `event_window_s` | `30` | s | 1–60 | — | Pre-trip trace span |
| `event_max_points` | `512` | count | 16–2048 | — | Transmission cap |
| `runout_gcode` | `unset` | template | — | — | Runout hook |
| `jam_gcode` | `unset` | template | — | — | Legacy JAM hook |
| `recover_gcode` | `unset` | template | — | — | Recovery preparation |
| `resume_gcode` | `unset` | template | — | — | Explicit tested resume path |

Never duplicate an oh_shit_force written into printer.cfg by SAVE_CONFIG in an included file. `diagnostic_force_limit: 0` prevents diagnosis until calibrated. Do not infer a safe force from defaults. Hook parameters: TOOL, TARGET, REASON, MSG; the two weak macros have additional incident metadata (see RECOVERY).