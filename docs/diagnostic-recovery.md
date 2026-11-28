# Unified jam diagnosis and bounded recovery

## Design contract (experimental)

Keep the existing per-speed-bin force model, statistical confirmation and independent hard-force threshold. No new rebound detector, periodicity algorithm, free-air training model or automatic PA tuning.

Both statistical HIGH and absolute-force trips (and persistent model-validation mismatch) enter the same JAM workflow. A hard trip is urgent evidence of overload, not proof of a nozzle obstruction. Stop the print before diagnosing. Runout retains its existing independent pause path.

Two weak G-code strategies:
- `FILAMENT_FORCE_JAM_ACTION`: pre-diagnosis pause/park/clearance preparation. Preserve the existing name and parameters; add SOURCE and E_SPEED. Default pauses and waits for movement, without inventing a park location. Core enforces pause even if an overridden macro omits it.
- `FILAMENT_FORCE_CONFIRMED_JAM_ACTION`: after repeatable high free-air resistance (or a diagnostic force cap), leave the job paused and report by default. Custom actions may notify or perform independently validated cleanup; must not resume the job directly.

The first strategy must return with the nozzle clear of the bed and print, all axes safely positioned, and waste safely collected. For unattended diagnosis it must explicitly signal clearance using `FILAMENT_FORCE_DIAG_READY CLEARANCE=1` after M400. The default does not grant clearance. Manual `FILAMENT_FORCE_DIAGNOSE CLEARANCE=1` remains available.

## State machine

MONITORING → PREPARING → WAITING_DIAGNOSIS → DIAGNOSING → CONFIRMED_JAM / WAITING_RECOVERY / FAILED.

With opt-in automatic recovery, WAITING_RECOVERY → RESUMING → VERIFYING → MONITORING or FAILED. No diagnostic or recovery samples train the normal model. Reset transient recovery state on cancellation, completion, new job, or shutdown. Preserve hard-force protection during printing and diagnostic peak limiting during each bounded pulse. Only one diagnostic per incident. Cap and count automatic retries per job; re-arm only after consecutive healthy windows. Unknown layer, unlearned speed, unstable baseline, missing samples, temperature change, or invalid recovery conditions never authorize automatic resumption.

## Diagnosis

Reuse the existing short forward extrusion pulses and the learned printing speed-bin reference, frozen at incident start; select the diagnostic speed near the triggering speed within the tested pulse-duration/speed limits. The diagnostic mean is not exactly the print-window statistic: a healthy-looking force is evidence against a gross restriction, not proof of normal flow. If no matching learned reference exists, require explicit calibrated manual bounds or remain inconclusive. Never train on fault-test data. A force cap stops subsequent pulses, not an in-flight move.

## Recovery

Layer 1: small positive Z gap increments (default 0.02 mm), maximum three and 0.06 mm total, cooldown and explicit homing/layer checks. After each successful resume compare the normalized excess force against the frozen reference. Stop when the required healthy windows arrive; retry only when there is a demonstrable improvement (initial experimental target 15%) and remaining budget. If there is no improvement, or a hard limit or low-force event during verification, remain paused.

Non-first layer: no Z correction; allow bounded automatic resume after a normal diagnostic, and verify subsequent windows. PA transients, acceleration and flow capability can cause apparent jams; do not automatically change these settings. Automatic resumption is opt-in. A custom resume integration is required where stock PAUSE/RESUME state restoration would overwrite Z offsets. Never guess a printer's safe park, clearance, motion path, offset sign or extrusion-flow evidence.

## Validation

Test both original trip sources, both strategy hooks, missing clearance, no learned model, high/low/mixed/no-sample diagnosis, capped attempts, verification timeout, cancel/restart, stale callbacks and preservation of learned histories. First-layer offsets must be applied in a verified resume path and removed without overwriting unrelated user adjustments. Hardware qualification is required before enabling unattended actions. Keep defaults conservative. This design describes the intended behavior; see implementation status in README and PR before enabling options.
