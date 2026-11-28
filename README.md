<p align="center">
  <img src="docs/media/logo.png" width="240" alt="filament force">
</p>

# filament_force

[简体中文](README.zh-CN.md) | English

Pauses the print on filament runout or a jam, using the toolhead load cell.

Needs `[load_cell_probe]` or `[load_cell]` (Kalico or Klipper).

## Install

```sh
cd ~
git clone https://github.com/wangyh775/klipper-filament-force.git
cd klipper-filament-force
./install.sh [~/klipper]
```

This is a native host-side Klipper/Kalico extras package, not a separate service.
The installer symlinks `src/filament_force/` into `klippy/extras/filament_force/`;
no MCU firmware rebuild or pip install is required. Pass a Kalico tree if that
is not `~/klipper` (e.g. `./install.sh ~/kalico`). The script can copy
`filament_force.cfg` into `printer_data/config`. Then add:

```ini
[include filament_force.cfg]
```

Restart Klipper when no print is running. The installer preserves an existing CFG;
merge new options manually. To update, run `git pull --ff-only` in the plugin
repository, rerun `./install.sh` with the same firmware path, then restart.
The experimental recovery branch is not the stable main branch.

Moonraker update manager:

```ini
[update_manager filament_force]
type: git_repo
path: ~/klipper-filament-force
origin: https://github.com/wangyh775/klipper-filament-force.git
primary_branch: main
managed_services: klipper
is_system_service: False
post_update_script: install.sh
```

## First use

1. Load filament.
2. `FILAMENT_FORCE_CAL_OH_SHIT` - cools the hotend, then pushes into the
   cold nozzle to set the jam stop. Do not run this during a print.
3. `SAVE_CONFIG` - writes `oh_shit_force` into `printer.cfg`. If that
   option is in `filament_force.cfg`, delete it or SAVE_CONFIG will refuse.
4. Optional: `FILAMENT_FORCE_TEST_RUNOUT RETRACT=30 TEMP=220` should report
   a runout in the console.

Detection is on. `FILAMENT_FORCE_SET ENABLE=0` turns it off.

On a trip: fix the filament, then `RESUME`. If nothing was wrong:
`FILAMENT_FORCE_RESET` then `RESUME`.

## Persistent force model

Healthy per-tool speed-bin windows and the runout history are persisted to a
versioned JSON file. Persistence is enabled by default:

```ini
model_persistence: True
model_file: ~/printer_data/config/filament_force_model.json
model_profile: default
model_save_interval: 60.0
```

The file is written atomically (temporary file + fsync + replace). In addition
to periodic saves, the model is saved when a speed bin or the runout reference
first learns, when a print ends, and on Klipper shutdown. Disk writes run in a
single worker. `RESTART` and `FIRMWARE_RESTART` wait for the latest snapshot after
the reactor stops, before loading the model again. After an abrupt power loss,
only completed saves can be recovered. Only healthy statistical windows are
stored; live force, tare/reference lock, pending trips, and anomaly streaks
are never restored.

After restart, both restored references remain active for detection while
learning is frozen. Three consecutive eligible matching windows validate a
reference. Short beads neither validate nor learn. A mismatch retains the
old samples, marks the reference uncertain and pauses after the configured
confirmation count if the mismatch persists. The operator must inspect the
cause before explicitly resetting a genuinely obsolete model. Unlearned
partial histories are discarded at restart. A new speed bin with only a global
reference may conservatively pause if its force differs substantially.
A missing, malformed, incompatible, or unsupported-version file is not used;
the plugin logs the reason and starts fresh. The independent absolute
`oh_shit_force` interlock remains active regardless of model availability.

**Model profiles are operator-managed.** Set a distinct `model_profile` for
each materially different setup, for example
`PEEK-400C-nozzle04-loadcellA`. Change it whenever material, nozzle diameter,
hotend temperature range, load-cell mounting/calibration, or other
force-affecting hardware/process conditions change. The plugin cannot infer
filament chemistry from G-code automatically. Non-default profiles use
separate hashed filenames alongside model_file. Earlier files with the
incomplete sampling fingerprint are intentionally incompatible; supervise
the first learning print after upgrading.

Run `FILAMENT_FORCE_QUERY` in the Mainsail or Fluidd console to see:

- `enabled`, `armed`, and `suppress` for configured enablement, whether
  the detector is armed, and whether monitoring is temporarily suppressed.
  The sensor and `sigma_jam` status and the absolute-force limit are also shown.
  The detector can be enabled but unarmed while idle. During motion, force
  scoring still requires the relevant tare, extrusion, and model conditions.
- `learned` and the window count for each extruder speed bin and the runout
  reference. Only the speed bins used in a print accumulate windows.
- `model_state` and `pending_validation` for the startup load result and
  the number of restored references awaiting validation.
- `model_save` and `saved_at` for the latest disk checkpoint, including
  `pending` and `failed` states. The timestamp is UTC. `model_file`
  is the absolute path for the active profile, including any profile suffix.
  `model_save_error` shows the latest write failure while it is unresolved.

The console also reports startup state, newly learned references, successful
checkpoints, and save failures. Routine periodic saves update query status
without repeating console messages. `quiet: True` suppresses routine notices;
save failures are still reported. Moonraker exposes the same persistence
information on the `filament_force` printer object.

Set `model_persistence: False` in the config and restart to disable persistence. `FILAMENT_FORCE_RESET
[TOOL=n]` clears that tool's learned history and queues an immediate durable
snapshot, acknowledging success only after the write finishes. A write
failure or timeout is reported; do not assume reset survived power loss.
Back up the JSON file before manual edits.

## Unified JAM actions and free-air diagnosis (experimental)

Both learned-band and hard-force JAM trips now pause before invoking the
same preparation strategy. A restored-model mismatch may also be diagnosed,
but cannot auto-resume until the model is trusted. Runout still pauses
independently. See [recovery design](docs/diagnostic-recovery.md).

- `FILAMENT_FORCE_JAM_ACTION`: pre-diagnosis preparation. The core pauses
  and waits first. Override this macro to park safely and collect waste.
  It receives TOOL, FORCE_G, TARGET, FIRST_LAYER, SOURCE and E_SPEED.
  The default adds no movement. If a legacy override calls PAUSE itself,
  remove that redundant call and validate its park path.
- `FILAMENT_FORCE_CONFIRMED_JAM_ACTION`: repeatably high free-air resistance.
  Receives the same incident metadata and DIAG_MEAN_G, DIAG_PEAK_G, RESULT.
  Defaults to a message while paused; never resume from this strategy.

Enable `diagnostic_enabled: True` and configure a measured safe
`diagnostic_force_limit` (grams) below hardware limits. Manually park and run:

```gcode
FILAMENT_FORCE_DIAGNOSE CLEARANCE=1
```

For optional automatic diagnosis set `diagnostic_auto: True` and have the
preparation macro issue `FILAMENT_FORCE_DIAG_READY CLEARANCE=1` only after
a verified safe park and M400. Do not add an unconditional clearance
acknowledgment. The default macro deliberately cannot authorize motion.

Diagnosis reuses the learned printing speed bin's band, or manually
configured min/max if no usable band exists. The normal-model path is
required for automatic recovery. By default the configured E-axis speed is
3 mm/s (`diagnostic_speed`, range 0.5–6 mm/s). Optional
`diagnostic_match_speed: True` matches the incident speed up to that configured
ceiling. The minimum pulse length is configurable; actual pulse length is
max(configured length, speed × 0.5 s), at most 3 mm; 2–3 pulses.
At 3 mm/s the default pulse is 1.5 mm (4.5 mm over three pulses). A speed mismatch greater than 20%
or a different bin still forbids auto-resume; fixed 3 mm/s may therefore
require manual recovery for slow first-layer trips. Enable optional matching
when this is needed, or validate a suitable configured speed. High resistance
may still be reported at a lower test speed. A force cap stops further pulses, not an
already queued move. Low, mixed, missing data or force-cap results stay
paused. Healthy force is not proof of actual extrusion.

Automatic recovery is separately opt-in (`auto_resume_enabled: True`),
requires a tested explicit `resume_gcode` calling the underlying resume
path, a known layer, a validated matching reference, and the same tool
and temperature. The manual command remains diagnostic-only unless
`RECOVER=1` is explicitly passed. The first-layer gate is separately
controlled by `first_layer_z_enabled`. Non-first-layer recovery does
not adjust Z. Limit automatic attempts; verify subsequent extrusion
windows without updating the normal model.

Monitor `recovery_state`, `recovery_attempts`, `recovery_healthy_windows`,
`recovery_failure`, `recovery_last_z_score`, and existing diagnostic
fields via Moonraker or `FILAMENT_FORCE_QUERY`. No unattended use until
the specific printer's pause/park/resume, load-cell response, clearance
and offset direction have been validated.

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

## Experimental first-layer Z correction (opt-in)

With diagnostic and automatic recovery enabled, a normal matched
free-air diagnosis on explicit slicer layer 1 (and homed valid Z)
can authorize one positive gap increment. Default 0.02 mm, at most
three steps and 0.06 mm total. The plugin shifts a compatible Kalico
`PAUSE_STATE` Z coordinate, base position and homing origin together,
rather than issuing an offset which the subsequent RESUME would undo.
This depends on the Kalico saved-state implementation and a tested
resume template that restores PAUSE_STATE; do not enable with an
incompatible custom resume path. Check the offset sign and bed mesh
on the actual machine. The plugin checks the restored origin after
resume and pauses on mismatch.

The next valid printing windows are compared to the unchanged learned
reference. Default: two healthy windows for first-layer correction,
three for ordinary resume, with a 60 s verification timeout. A repeated
HIGH can permit another diagnosis only with remaining budget and
(for first layer) at least 15% reduction in normalized high-force
deviation; a hard-force peak is not directly comparable to a window
mean, so a hard-trip recovery cannot infer a repeat-adjustment improvement.
A failed verification stays paused. No automatic PA changes.

A job owns only its applied Z increments. Terminal callbacks attempt
to subtract the owned correction only when the observed origin still
matches and no new job has started; otherwise a manual-check message
is issued. Confirm the offset after a cancelled or failed print. A
firmware crash cannot guarantee cleanup. This is experimental and not
yet validated on hardware.

## Spike check

Continuous scoring watches forward extrusion. The spike check is separate:
a one-shot retract/deretract that asks whether filament is still in the
melt zone. It never pauses the print.

The sequence is retract 3 mm, sample Force1, then deretract 3.2 mm (the
retract plus 0.2 mm extra prime) while tracking the load cell. Filament in
the melt zone resists that push, so the force jumps. An empty hotend does
not.

The probe scores `max(|peak - Force1|, |Force2 - Force1|)`. Peak is the
largest excursion during the deretract; Force2 is the sample at the end.
If that delta is at least `probe_spike_g` (default 50 g), filament is
present. The result is `printer.filament_force.last_probe_spike` (1 or 0)
and `last_probe_delta_g`.

Call it when you need a yes/no on filament in the melt zone, not while
the print is extruding. After a tool pickup is the usual spot: the docked
tool may be empty, and a purge into a dry hotend is a mess. Run it after
`FILAMENT_FORCE_SUPPRESS_END` (pickup finished), before the purge. Same
idea before a manual load, or a resume that purges.

The nozzle needs to be at print temperature; this moves the extruder.
Jinja in the same macro is expanded before any G-code runs, so read the
result from a follow-up macro:

```gcode
FILAMENT_FORCE_CHECK_SPIKE
```

Then, in a later macro (not the same template):

```gcode
{% if printer.filament_force.last_probe_spike|int == 0 %}
    {action_respond_info("No filament spike - abort purge")}
{% endif %}
```

Override the motion with `SPIKE_G=`, `RETRACT=`, `EXTRA_PRIME=`,
`FEEDRATE=` on the command, or `FILAMENT_FORCE_SET PROBE_SPIKE_G=` /
`PROBE_RETRACT_MM=` / `PROBE_EXTRA_PRIME_MM=` / `PROBE_FEEDRATE=`.
Skipped with `probe_busy` if a probe, trip, or cal is already running.

## Commands

- `FILAMENT_FORCE_SET ENABLE=0|1` - turn detection on or off
- `FILAMENT_FORCE_CAL_OH_SHIT` - set the jam stop from a cold extrude; `SAVE_CONFIG` to keep it
- `FILAMENT_FORCE_TEST_RUNOUT RETRACT=<mm> TEMP=<c>` - should report a runout
- `FILAMENT_FORCE_CHECK_SPIKE` - one-shot presence check
- `FILAMENT_FORCE_DIAGNOSE CLEARANCE=1 [RECOVER=1]` - supervised free-air diagnosis
- `FILAMENT_FORCE_DIAG_READY CLEARANCE=1` - preparation macro acknowledgment
- `FILAMENT_FORCE_QUERY` - current state
- `FILAMENT_FORCE_SET_TOOL TOOL=n`
- `FILAMENT_FORCE_RESET [TOOL=n]` - clear history after a false trip
- `FILAMENT_FORCE_RESUME [VELOCITY=v]`
- `FILAMENT_FORCE_SUPPRESS ENABLE=0|1`
- `FILAMENT_FORCE_SUPPRESS_BEGIN` - call before park or pickup
- `FILAMENT_FORCE_SUPPRESS_END [TOOL=n]` - call after pickup, or after a park with no TOOL

## Development

```sh
uv sync
uv run pytest
uv run ty check src tests
```
