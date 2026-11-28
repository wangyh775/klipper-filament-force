# Algorithm

English | [简体中文](ALGORITHM.zh-CN.md) · [Home](../README.md)

> Reference: main commit 25b359b. Automatic diagnosis, resume and Z compensation are opt-in and have not been qualified on hardware.

![Fig. 3. Synthetic force windows; the dashed levels are illustrative.](media/en/03-windows.svg)

*Fig. 3. Synthetic force windows; the dashed levels are illustrative.*
## Signal and window

Use calibrated signed readings Fᵢ in gf and an idle reference F₀. For samples j within the trailing rolling interval Tᵣ, Rᵢ = ΣFⱼ / nᵢ. Window level Lₖ = Σ|Rᵢ − F₀| / Nₖ. The code accumulates eligible forward E increments until L_E ≥ detection_length (7 mm default); E is commanded filament displacement, not XY distance or measured flow. Distance-weighted speed v̄ = Σ(vⱼ ΔEⱼ)/ΣΔEⱼ. At constant speed the ideal duration is 7/v̄; actual polling and interruptions affect it. Empty windows are discarded; retraction/unretraction and extended idle are gated; a short first bead after idle skips HIGH, LOW and learning. Overshoot is not carried into the next window.

![Fig. 4. Independent illustrative speed-bin models.](media/en/04-bins.svg)

*Fig. 4. Independent illustrative speed-bin models.*
## Adaptive thresholds

For each tool and speed bin, maintain accepted levels (default 16, learn after 5). Default edges 1,2,4,7 mm/s. With mean μ and standard deviation σ:

- σ_eff = max(σ, min_delta_g, 0.08|μ|)
- H = μ + max(high_sigma × σ_eff, 0.5 min_delta_g)
- L_low = min(drop_ratio × μ, runout_max_level_g) when μ ≥ min_delta_g; otherwise 0.
- z = (Lₖ − μ)/σ_eff. HIGH if Lₖ > H; LOW if Lₖ ≤ L_low and the mean is sufficient. Runout uses a separate global per-tool history.

Default confirmation is 3 eligible anomalous windows; evidence expires after a gap >30 s, not a global 30 s sliding window. Healthy observations reset high streaks; unlearned and skipped windows do not constitute healthy proof. Absolute protection independently checks |Fᵢ−F₀| ≥ oh_shit_force for jam_dwell_s (0.15 s), with arming/reference/forward-E gates. A force trip is not a proven nozzle blockage.

## Persistence

Healthy histories are versioned and saved atomically; restored references score immediately but are validated before learning, with three matching eligible windows. Mismatch retains old data and may pause; never use fault windows as training. Separate profiles for material, nozzle, temperature, PA and load-cell changes. No persisted fault latch or recovery state.


## Learning and validation boundaries

For n stored levels, μ = ΣLᵢ/n and σ = √(Σ(Lᵢ−μ)²/n): population standard deviation, not sample standard deviation. During cold start, eligible data may enter history before either reference can classify it. These data are not independently proven healthy; commission with a supervised known-good print. Once references are learned, reject a window if the bin class is not NONE or the global reference is LOW. HIGH confirmation spans learned bins; LOW uses the global per-tool history. Short, nonfinite or unlearned-HIGH skips are not evidence of healthy printing; a LOW bin classification can nevertheless clear the HIGH streak. A gap greater than confirm_max_gap_s between eligible windows resets evidence.

For restored bin b, require |Lₖ−μ_b| ≤ ε_b and class NONE, where ε_b = max(3σ_b, min_delta_g, 0.15μ_b). For a restored global reference, use known-bin consistency when available, otherwise its own tolerance; the global classification must not be LOW. All relevant matches are required for three consecutive matching windows; persistent mismatches use confirm_windows. Do not reset an unresolved fault or silently train it.

Absolute force is evaluated only when armed, unsuppressed, outside active calibration/diagnosis, baseline locked, forward E seen and no pending recheck. It may also trip during travel after forward E; the host queues a pause callback, not a hardware emergency stop. Independent physical protection is still required. See [recovery](RECOVERY.md).
