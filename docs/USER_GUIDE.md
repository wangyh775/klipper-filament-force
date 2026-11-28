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

## Advanced calibration and false alarms

Cold calibration is optional, not a commissioning requirement. It disables normal cold-extrusion gating and bypasses regular absolute-force detection during the calibration routine. APPLY=0 still moves the extruder. The calculated threshold is peak × MARGIN and is accepted only if both peak and suggestion exceed the current threshold; it cannot lower the threshold. Do not run it on an unqualified drive, load cell or high-temperature hotend. Prefer an independently established safe force limit; validate on a supervised healthy print. If a fault looks false, preserve logs and model, inspect PA/flow/temperature/feed path and diagnose. Use RESET only for a confirmed invalid reference after resolving mechanical causes, and relearn supervised. Do not automatically RESET then RESUME.

## Deployment profiles

Merge only the relevant options into the existing section; do not duplicate [filament_force]. These are staged profiles, not universal safe settings.

| Profile | diagnostic_enabled | diagnostic_auto | auto_resume_enabled | first_layer_z_enabled |
|---|---|---|---|---|
| Basic | False | False | False | False |
| Manual diagnosis | True | False | False | False |
| Non-first-layer automatic recovery | True | True | True | False |
| Full feedback | True | True | True | True |

For profiles 2–4 set a measured positive diagnostic_force_limit below device capability and qualify 3 mm/s pulse flow (or configure a tested speed). Profile 2: PAUSE, verified park, then FILAMENT_FORCE_DIAGNOSE CLEARANCE=1; expect a diagnostic result while paused. Profile 3: qualify the machine-specific preparation hook, which must call M400 then FILAMENT_FORCE_DIAG_READY CLEARANCE=1 only after physically safe park. Configure nonempty resume_gcode which calls the actual underlying resume path. Profile 4 additionally validates PAUSE_STATE, positive gap direction, axis limits, current_layer=1 and offset cleanup. Qualify recovery with supervised prints before enabling unattended actions. With first_layer_z_enabled=False, a layer-1 diagnosis remains paused, not ordinary auto-resume.

Illustrative template interface (comments are deliberate placeholders, not a runnable motion solution):

```ini
[filament_force]
diagnostic_enabled: True
diagnostic_auto: True
auto_resume_enabled: True
# diagnostic_force_limit: set measured positive limit
# resume_gcode: configure the verified underlying resume macro
first_layer_z_enabled: False
```

The preparation and resume macros are machine-specific. Inspect PAUSE/RESUME rename_existing, any retract/prime and park path; test without an active print first. Never call FILAMENT_FORCE_RESUME recursively from resume_gcode. The latter receives params.VELOCITY (empty when omitted). Do not add clearance acknowledgment unconditionally.

## Existing toolchanger and manual resume integration

## Toolchanger

Call two hooks from your park and pickup macros. The extra does not patch
them.

- `FILAMENT_FORCE_SUPPRESS_BEGIN` before park or pickup motion (stops scoring)
- `FILAMENT_FORCE_SUPPRESS_END TOOL={t}` after a successful pickup (records the tool, scoring on)
- `FILAMENT_FORCE_SUPPRESS_END` with no `TOOL` after a park that leaves the head empty

A single-tool printer can ignore this.

### INDX

In `CHANGE_TOOL`, inside `{% if act != t %}`, before `PARK_TOOL` /
`_PICKUP_TOOL`:

```gcode
FILAMENT_FORCE_SUPPRESS_BEGIN
```

Last line of `_RECORD_TOOLCHANGE`:

```gcode
FILAMENT_FORCE_SUPPRESS_END TOOL={t}
```

Standalone `PARK_TOOL` (calibration, `TC_CYCLE_ALL`) also needs a begin and
an end. Put `FILAMENT_FORCE_SUPPRESS_BEGIN` at the start of `PARK_TOOL` (nested begin from
`CHANGE_TOOL` is fine). Do not put `FILAMENT_FORCE_SUPPRESS_END` inside `PARK_TOOL` -
`CHANGE_TOOL` would then score the pickup latch. After those standalone
parks:

```gcode
PARK_TOOL
FILAMENT_FORCE_SUPPRESS_END
```

## Resume

If your `RESUME` wrapper does extra work:

```gcode
{% if printer.filament_force.pending_recheck|int == 1 %}
    FILAMENT_FORCE_RESUME
{% endif %}
```

