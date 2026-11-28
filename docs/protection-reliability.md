# Protection reliability / 保护可靠性

A failed PAUSE acknowledgement on an active job now escalates to Klippy shutdown, not a hardware interlock. Diagnostic baseline and middle pulse samples require monotonic timestamps and maximum adjacent/edge gap (diagnostic_max_sample_gap_s=0.05). Verification evidence expires after confirm_max_gap_s; a missing/unvalidated reference clears evidence. Repeated first-layer compensation requires the same speed bin and ±20% incident speed. A queued verification retry checks both generation and VERIFYING state. No changes to Z cleanup or the core statistical algorithm.

活动任务暂停未确认时升级 Klippy shutdown，不代替硬件联锁。诊断基准与脉冲中段须满足严格递增时间戳及相邻/端点最大间隔（diagnostic_max_sample_gap_s=0.05）。恢复验证证据沿用 confirm_max_gap_s，缺失或未验证参考清除证据。首层再次补偿要求同速度组且与故障速度偏差 ≤20%。排队的恢复重试需同时核对任务代次及 VERIFYING 状态。未修改 Z 撤销或核心统计算法。实机验证仍必需。

## Independent watchdog / 独立看门狗

While a print is active and monitoring is enabled, a 250 ms timer checks advancing finite sensor timestamps and an absent force baseline after eligible E motion. The timer is excluded during explicit suppression, calibration, spike test, diagnosis and preparation/resuming. Sensor timeout 2 s, baseline timeout 3 s, normal baseline max span 100 gf and at least five samples, max gap 0.1 s. These defaults require hardware qualification. On fault, pause with pending reason protection; do not authorize automatic recovery. Manual recovery requires fresh samples. A baseline timeout limits rather than removes the initial blind interval. Status includes protection_fault and sensor_last_sample_age_s; recovery_failed carries the reason. See the subsequent pre-resume reference and event protocol documentation for the implemented extensions.

监控已启用且打印时，独立 250 ms 定时器检查有效递增采样及有效 E 运动后缺少基准。显式抑制、标定、探测、诊断、准备及恢复动作期间除外。断流默认 2 s、基准超时 3 s、正常基准跨度 100 gf、最少 5 点且最大间隔 0.1 s；须实机验证。故障暂停并锁存 protection 原因，不授权自动恢复；人工恢复须有新鲜样本。超时仅限制盲区，不消除盲区。状态含 protection_fault 和 sensor_last_sample_age_s，复用 recovery_failed 携带原因。后续实现见恢复前基准及事件协议文档。

## Pre-resume reference / 恢复前基准

Automatic recovery now executes M400 after recover_gcode, captures a fresh stationary 0.8 s reference plus 0.25 s delivery allowance, rejects missing/gapped data, motion/context change, a force cap hit or baseline drift beyond baseline_max_span_g. The reference is armed before the underlying resume and retained across re-arming. Resume-macro motion is excluded from statistical learning; the hard-force check can use the qualified reference. Manual recovery remains operator-supervised and the existing baseline watchdog bounds its initial blind interval. A resume macro changing tool preload or coordinate state still requires hardware qualification. baseline_max_span_g participates in the model fingerprint; models from older versions may require supervised relearning.

自动恢复在 recover_gcode 后 M400，采集 0.8 s 静止受力并预留 0.25 s 批次到达时间；数据缺失、采样间隔超限、运动或上下文变化、绝对力超限或相对原诊断基准漂移超出 baseline_max_span_g 均拒绝恢复。恢复前布防并保留已确认基准，恢复宏运动不进入统计学习，硬力保护使用已确认基准。人工恢复仍须监督，基准看门狗限制其初始盲区。改变工具预载的恢复宏仍须实机验证。baseline_max_span_g 纳入模型指纹，旧模型可能需要监督重新学习。

## Recovery budgets / 恢复预算

Automatic attempts are counted before the recovery preparation, even if baseline qualification or resume fails. Consecutive automatic attempts (legacy recovery_attempts), consecutive ordinary attempts (recovery_ordinary_attempts), current retry-chain attempts (recovery_incident_attempts), per-job automatic total (recovery_total_attempts) and manual attempts (recovery_manual_attempts) are independent. First-layer Z remains separately bounded. auto_resume_max_attempts limits consecutive non-first-layer attempts; new auto_resume_job_max_attempts (default 10, range 1–100) caps all automatic attempts for a job. A stable observed print resets consecutive counters, not totals; a new fault outside verification starts a new incident count. Manual recovery does not reset automatic budgets; failed manual recovery retains the fault latch and reasserts pause. All counters reset on job reset.

自动恢复在准备前计数（基准验证失败、恢复失败亦计数）。连续自动、非首层连续、当前重试链、单任务自动累计、人工次数独立；首层 Z 另有预算。auto_resume_max_attempts 限制非首层连续自动恢复，auto_resume_job_max_attempts（默认 10，范围 1–100）限制单任务全部自动尝试。稳定打印仅清零连续次数，新故障（非 VERIFYING 重试）重置单故障链计数。人工恢复不清除自动预算；失败保留锁存并重新确保暂停。任务重置清除计数。

## Z ownership / Z 补偿所有权

A correction is staged before changing PAUSE_STATE, committed only when its expected Z origin is observed, and rolled back only when the old origin and saved-state identity are confirmed. Job reset moves owned offsets into pending cleanup without deleting the record. Idle cleanup uses MOVE=0 only if the origin still matches; it verifies the resulting origin before clearing ownership. An ambiguous operation, an in-flight reset, a new job or a mismatched origin retains the record and blocks automatic recovery; the protection watchdog pauses a new print with unresolved ownership. Cancel an affected job, inspect and physically reconcile the offset, then at idle issue FILAMENT_FORCE_Z_ACK CONFIRM=1. ACK does not move or modify coordinates. z_ownership status exposes applied_mm, staged_step_mm, origin_mm, before_mm, expected_mm, cleanup_pending and uncertain. The ledger is process-local, not crash-persistent; check Z after firmware restart/shutdown. No automatic offset rollback across restart is claimed.

修改 PAUSE_STATE 前记录意图，只有实际原点吻合才提交；仅旧原点与保存状态身份均吻合才回滚。任务重置进入待撤销而非删除记录。空闲且原点吻合才 MOVE=0 撤销，并复核原点后清除所有权。歧义、事务进行中重置、新任务或原点失配保留记录并阻止自动恢复；新任务存在未处理所有权时看门狗暂停。取消受影响任务、人工检查及处理实际偏移后，空闲执行 FILAMENT_FORCE_Z_ACK CONFIRM=1；此命令不移动、不修改坐标。z_ownership 提供累计、暂存、原点、期望值与不确定标志。记录仅在进程内，崩溃/重启不持久化，须人工确认 Z，不宣称跨重启自动撤销。
