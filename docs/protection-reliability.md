# Protection reliability / 保护可靠性

A failed PAUSE acknowledgement on an active job now escalates to Klippy shutdown, not a hardware interlock. Diagnostic baseline and middle pulse samples require monotonic timestamps and maximum adjacent/edge gap (diagnostic_max_sample_gap_s=0.05). Verification evidence expires after confirm_max_gap_s; a missing/unvalidated reference clears evidence. Repeated first-layer compensation requires the same speed bin and ±20% incident speed. A queued verification retry checks both generation and VERIFYING state. No changes to Z cleanup or the core statistical algorithm.

活动任务暂停未确认时升级 Klippy shutdown，不代替硬件联锁。诊断基准与脉冲中段须满足严格递增时间戳及相邻/端点最大间隔（diagnostic_max_sample_gap_s=0.05）。恢复验证证据沿用 confirm_max_gap_s，缺失或未验证参考清除证据。首层再次补偿要求同速度组且与故障速度偏差 ≤20%。排队的恢复重试需同时核对任务代次及 VERIFYING 状态。未修改 Z 撤销或核心统计算法。实机验证仍必需。
