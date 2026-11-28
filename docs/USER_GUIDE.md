# User guide

English | [简体中文](USER_GUIDE.zh-CN.md) · [Home](../README.md)

> Reference: main commit 25b359b. Automatic diagnosis, resume and Z compensation are opt-in and have not been qualified on hardware.

## Commissioning

1. Verify load-cell calibration, stable baseline, hardware force capacity and independent safety interlocks. Use a known healthy supervised print to learn each relevant speed bin.
2. Check FILAMENT_FORCE_QUERY: enabled can be true while idle/unarmed. Inspect model_state, pending validation, bin window counts and save errors.
3. On JAM, inspect the print and pause state; park safely, then run diagnostic command only after clearance and a calibrated cap. Repair a persistent restriction before manual resume. Do not clear a model just to silence a fault.
4. Qualify diagnostic motion, same-temperature bounds, resume path and Z sign separately before enabling automatic actions.

## Commands

| G-code | Purpose |
|---|---|
| `FILAMENT_FORCE_QUERY` | Model and recovery status |
| `FILAMENT_FORCE_SET [ENABLE=0/1]` | Runtime options; see configuration |
| `FILAMENT_FORCE_RESET [TOOL=n]` | Clear history; checkpoint |
| `FILAMENT_FORCE_CAL_OH_SHIT [MAX_TEMP=50] [EXTRUDE=8] [SPEED=2] [MARGIN=0.5] [APPLY=1]` | Cold push calibration: supervised only |
| `FILAMENT_FORCE_TEST_RUNOUT RETRACT=<mm> TEMP=<C>` | Supervised runout test |
| `FILAMENT_FORCE_CHECK_SPIKE` | Presence check; not continuous jam detection |
| `FILAMENT_FORCE_DIAGNOSE CLEARANCE=1 [RECOVER=1]` | Free-air test; default no auto resume |
| `FILAMENT_FORCE_DIAG_READY CLEARANCE=1` | Safe-park acknowledgment within preparation |
| `FILAMENT_FORCE_RESUME [VELOCITY=v]` | Fault recovery |
| `FILAMENT_FORCE_SET_TOOL TOOL=n` | Active tool |
| `FILAMENT_FORCE_SUPPRESS ENABLE=0/1` | Suppress during tool change |
| `FILAMENT_FORCE_SUPPRESS_BEGIN / END [TOOL=n]` | Example toolchange macros |

Cold calibration intentionally pushes against a cold nozzle and bypasses thermal extrusion gating; it can damage filament, load cell or drive. Use only with known safe loads and supervision, never during printing. Do not treat APPLY=0 as motion-free. SAVE_CONFIG persists an accepted threshold. Active presence check uses retract/deretract peak; evaluate result in a later Jinja macro, not the same pre-rendered template.