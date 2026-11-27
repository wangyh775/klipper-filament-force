<p align="center">
  <img src="docs/media/logo.png" width="240" alt="filament force">
</p>

# filament_force

Pauses the print on filament runout or a jam, using the toolhead load cell.

Needs `[load_cell_probe]` or `[load_cell]` (Kalico or Klipper).

## Install

```sh
cd ~
git clone https://github.com/charliemayall/klipper-filament-force.git
cd klipper-filament-force
./install.sh [~/klipper]
```

Pass a Kalico tree if that is not `~/klipper`. The script can copy
`filament_force.cfg` into `printer_data/config`. Then add:

```ini
[include filament_force.cfg]
```

Restart Klipper.

Moonraker update manager:

```ini
[update_manager filament_force]
type: git_repo
path: ~/klipper-filament-force
origin: https://github.com/charliemayall/klipper-filament-force.git
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

The file is written atomically (temporary file + fsync + replace). Saves are
periodic, including during long prints, and on Klipper shutdown. Only healthy
statistical windows are stored; live force, tare/reference lock, pending trips,
and anomaly streaks are never restored.

After restart, each restored speed bin and the runout history is held out of
scoring until three consecutive windows fall within a conservative validation
band. A mismatch discards only that restored history and returns it to learning.
A missing, malformed, incompatible, or unsupported-version file is not used;
the plugin logs the reason and starts fresh. The independent absolute
`oh_shit_force` interlock remains active regardless of model availability.

**Model profiles are operator-managed.** Set a distinct `model_profile` for
each materially different setup, for example
`PEEK-400C-nozzle04-loadcellA`. Change it whenever material, nozzle diameter,
hotend temperature range, load-cell mounting/calibration, or other
force-affecting hardware/process conditions change. The plugin cannot infer
filament chemistry from G-code automatically.

Use `FILAMENT_FORCE_QUERY` to inspect `model_persistence`,
`model_state`, and `pending_validation`. Set `model_persistence: False` in
the config and restart to disable persistence. `FILAMENT_FORCE_RESET
[TOOL=n]` clears that tool's learned history and the next save updates the
store accordingly. Back up the JSON file before manual edits.

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

The first-layer Z correction is **disabled by default**. Enable it only after
reviewing the hardware and testing with supervised, low-risk prints. It is a
bounded recovery attempt for a *learned-band HIGH force event*, **not**
a reliable classifier of nozzle-too-close versus genuine filament clogging.
Absolute `oh_shit_force` trips and filament runout continue to pause.

Configuration under `[filament_force]`:

```ini
first_layer_z_enabled: True
first_layer_z_step: 0.02
first_layer_z_max_adjustments: 3
first_layer_z_cooldown_s: 10.0
first_layer_z_max_height: 0.60
first_layer_z_max_force: 2000.0
```

**First-layer detection is fail-closed.** The slicer must explicitly report
layer 1 using `SET_PRINT_STATS_INFO CURRENT_LAYER=1`; the printer must be
actively printing, Z homed, and its reported G-code Z height between 0 and
`first_layer_z_max_height`. Missing or ambiguous layer information means
the original jam-pause behavior remains in effect. Do not use layer 0 as a
synonym for the first layer. Check slicer start/layer-change G-code first.

Upon a confirmed *statistical* HIGH trip (three bad extrusion windows by
default), and only if its measured force is below
`first_layer_z_max_force` and the independent `oh_shit_force`, the module
sends `SET_GCODE_OFFSET Z_ADJUST=+step` without an immediate extra Z move.
It counts the adjustment, enforces cooldown, and checks again through normal
force windows. If safety gates fail or adjustments are exhausted, original
jam pause behavior applies. The total correction is reversed when the
print-completion, cancellation, error, or new-file reset event fires,
using `SET_GCODE_OFFSET Z_ADJUST=-total` without moving the axes.

Verify with `FILAMENT_FORCE_QUERY`:
`first_layer_z=on adjustments=1/3 total=0.020mm`. Corresponding
`printer.filament_force` fields are available through Moonraker:
`first_layer_z_enabled`, `first_layer_z_adjustments`,
`first_layer_z_total_mm`, `first_layer_z_max_adjustments`.

**Limitations:** No vision or independent nozzle/contact classification;
the filter is based on a force anomaly. A real jam during layer 1 may
temporarily receive a Z increase before the ordinary jam safeguard fires.
The existing hard-force interlock is never bypassed. G-code offsets are
session-scoped and rely on successful terminal callbacks for automatic
undo; if the firmware crashes mid-job, inspect/reset the offset before
printing again. Validate the sign on your machine's motion configuration.

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
