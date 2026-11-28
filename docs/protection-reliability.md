# Protection reliability / 保护可靠性

A failed PAUSE acknowledgement on an active job now escalates to Klippy shutdown, not a hardware interlock. Diagnostic baseline and middle pulse samples require monotonic timestamps and maximum adjacent/edge gap (diagnostic_max_sample_gap_s=0.05). Verification evidence expires after confirm_max_gap_s; a missing/unvalidated reference clears evidence. Repeated first-layer compensation requires the same speed bin and ±20% incident speed. A queued verification retry checks both generation and VERIFYING state. No changes to Z cleanup or the core statistical algorithm.

活动任务暂停未确认时升级 Klippy shutdown，不代替硬件联锁。诊断基准与脉冲中段须满足严格递增时间戳及相邻/端点最大间隔（diagnostic_max_sample_gap_s=0.05）。恢复验证证据沿用 confirm_max_gap_s，缺失或未验证参考清除证据。首层再次补偿要求同速度组且与故障速度偏差 ≤20%。排队的恢复重试需同时核对任务代次及 VERIFYING 状态。未修改 Z 撤销或核心统计算法。实机验证仍必需。

## Independent watchdog / 独立看门狗

While a print is active and monitoring is enabled, a 250 ms timer checks advancing finite sensor timestamps and an absent force baseline after eligible E motion. The timer is excluded during explicit suppression, calibration, spike test, diagnosis and preparation/resuming. Sensor timeout 2 s, baseline timeout 3 s, normal baseline max span 100 gf and at least five samples, max gap 0.1 s. These defaults require hardware qualification. On fault, pause with pending reason protection; do not authorize automatic recovery. Manual recovery requires fresh samples. A baseline timeout limits rather than removes the initial blind interval. Status includes protection_fault and sensor_last_sample_age_s; recovery_failed carries the reason. Dedicated sensor events and pre-resume baseline qualification remain future work.

监控已启用且打印时，独立 250 ms 定时器检查有效递增采样及有效 E 运动后缺少基准。显式抑制、标定、探测、诊断、准备及恢复动作期间除外。断流默认 2 s、基准超时 3 s、正常基准跨度 100 gf、最少 5 点且最大间隔 0.1 s；须实机验证。故障暂停并锁存 protection 原因，不授权自动恢复；人工恢复须有新鲜样本。超时仅限制盲区，不消除盲区。状态含 protection_fault 和 sensor_last_sample_age_s，复用 recovery_failed 携带原因。独立传感器事件和恢复前基准验证仍待实现。

## Pre-resume reference / 恢复前基准

Automatic recovery now executes M400 after recover_gcode, captures a fresh stationary 0.8 s reference plus 0.25 s delivery allowance, rejects missing/gapped data, motion/context change, a force cap hit or baseline drift beyond baseline_max_span_g. The reference is armed before the underlying resume and retained across re-arming. Resume-macro motion is excluded from statistical learning; the hard-force check can use the qualified reference. Manual recovery remains operator-supervised and the existing baseline watchdog bounds its initial blind interval. A resume macro changing tool preload or coordinate state still requires hardware qualification. baseline_max_span_g participates in the model fingerprint; models from older versions may require supervised relearning.

自动恢复在 recover_gcode 后 M400，采集 0.8 s 静止受力并预留 0.25 s 批次到达时间；数据缺失、采样间隔超限、运动或上下文变化、绝对力超限或相对原诊断基准漂移超出 baseline_max_span_g 均拒绝恢复。恢复前布防并保留已确认基准，恢复宏运动不进入统计学习，硬力保护使用已确认基准。人工恢复仍须监督，基准看门狗限制其初始盲区。改变工具预载的恢复宏仍须实机验证。baseline_max_span_g 纳入模型指纹，旧模型可能需要监督重新学习。
