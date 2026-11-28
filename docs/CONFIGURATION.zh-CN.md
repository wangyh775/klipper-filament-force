# 配置参考

简体中文 | [English](CONFIGURATION.md) · [首页](../README.zh-CN.md)

> 依据 main 提交 25b359b。自动诊断、恢复、Z 补偿均须显式启用，尚未完成实机验收。

均属于 [filament_force]。下表为源码默认值，不代表设备安全推荐值。min_learn_windows 应 ≤ history_n。SET 为运行时设置；持久化请改 CFG 重启（标定 SAVE_CONFIG 例外）。采样结构或历史重建会使旧学习失效；监督下一次打印。工艺变化也须新 profile。恢复关键阶段拒绝运行时修改。

| 参数 | 默认值 | 单位 | 范围 | 动态 SET | 含义 |
|---|---|---|---|---|---|
| `sensor` | `load_cell_probe` | object | — | — | 称重对象 |
| `extruder` | `extruder` | object | — | — | 挤出机对象 |
| `continuous_detection` | `True` | bool | — | ENABLE | 初始检测开关 |
| `detection_length` | `7` | mm | >0 | ✓ | E 轴窗口；重建模型 |
| `min_e_speed` | `0.5` | mm/s | >0 | ✓ | 最小有效速度；重建 |
| `rolling_window` | `0.05` | s | >0 | — | 滑动平均 |
| `baseline_time` | `0.15` | s | >0 | — | 空闲基准时长 |
| `min_delta_g` | `15` | gf | >0 | ✓ | 标准差下限 |
| `high_sigma` | `4` | — | >0 | ✓ | 高力系数 |
| `sigma_jam` | `True` | bool | — | ✓ | 统计高力开关 |
| `drop_ratio` | `0.35` | — | 0–1 | ✓ | 低力比例 |
| `runout_max_level_g` | `80` | gf | ≥0 | ✓ | 低力绝对上限 |
| `confirm_windows` | `3` | count | ≥1 | ✓ | 异常确认 |
| `confirm_max_gap_s` | `30` | s | >0 | — | 确认最大间隔 |
| `recover_windows` | `2` | count | ≥1 | ✓ | 健康恢复计数 |
| `history_n` | `16` | count | ≥5 | ✓ | 历史容量；重建 |
| `min_learn_windows` | `5` | count | ≥2 | ✓ | 学习数量；重建 |
| `speed_bins` | `1,2,4,7` | mm/s | positive sorted | ✓ | 速度组边界；重建 |
| `oh_shit_force` | `4000` | gf | >0 | ✓ | 绝对阈值；标定 |
| `jam_dwell_s` | `0.15` | s | >0 | — | 超限持续时间 |
| `poll_interval_ms` | `250` | ms | 50–2000 | — | E 轮询周期 |
| `idle_reset_s` | `0.3` | s | >0 | ✓ | 空闲窗口重置 |
| `min_learn_s` | `1.5` | s | ≥0 | ✓ | 首段时长门控 |
| `probe_retract_mm` | `3` | mm | >0 | ✓ | 存在检查回抽 |
| `probe_extra_prime_mm` | `0.2` | mm | ≥0 | ✓ | 额外复进 |
| `probe_spike_g` | `50` | gf | >0 | ✓ | 存在阈值 |
| `probe_feedrate` | `30` | mm/s | >0 | ✓ | 主动探测速度 |
| `quiet` | `False` | bool | — | ✓ | 减少常规信息 |
| `debug_log` | `False` | bool | — | ✓ | 窗口日志 |
| `model_persistence` | `True` | bool | — | — | 模型持久化 |
| `model_file` | `~/printer_data/config/filament_force_model.json` | path | — | — | 模型文件 |
| `model_profile` | `default` | text | — | — | 工艺标识 |
| `model_save_interval` | `60` | s | >0 | — | 周期保存 |
| `diagnostic_enabled` | `False` | bool | — | — | 启用浮空诊断 |
| `diagnostic_auto` | `False` | bool | — | — | 授权后自动诊断 |
| `diagnostic_match_speed` | `False` | bool | — | — | 匹配速度 |
| `diagnostic_speed` | `3` | mm/s | 0.5–6 | — | 固定速度/匹配上限 |
| `diagnostic_pulse_mm` | `0.5` | mm | 0.5–3 | — | 最短脉冲长度 |
| `diagnostic_pulses` | `3` | count | 2–3 | — | 脉冲数 |
| `diagnostic_force_limit` | `0` | gf | ≥0 | — | 须标定正上限 |
| `diagnostic_force_min` | `0` | gf | ≥0 | — | 人工备用下限 |
| `diagnostic_force_max` | `0` | gf | ≥0 | — | 人工备用上限 |
| `diagnostic_baseline_span` | `30` | gf | >0 | — | 空闲稳定性 |
| `auto_resume_enabled` | `False` | bool | — | — | 自动恢复开关 |
| `auto_resume_max_attempts` | `2` | count | 1–5 | — | 普通连续次数 |
| `auto_resume_reset_s` | `60` | s | >0 | — | 健康时长重置 |
| `auto_resume_verify_windows` | `3` | count | ≥1 | — | 普通验证窗口 |
| `recovery_verify_timeout` | `60` | s | >0 | — | 验证超时 |
| `first_layer_z_enabled` | `False` | bool | — | — | 首层补偿开关 |
| `first_layer_z_step` | `0.02` | mm | (0,0.05] | — | 单次补偿 |
| `first_layer_z_max_adjustments` | `3` | count | 1–10 | — | 单任务次数 |
| `first_layer_z_max_total` | `0.06` | mm | (0,0.2] | — | 单任务累计 |
| `first_layer_z_cooldown_s` | `10` | s | ≥0 | — | 补偿间隔 |
| `first_layer_z_max_height` | `0.60` | mm | >0 | — | 原始 Z 高度门控 |
| `first_layer_z_max_force` | `2000` | gf | >0 | — | 诊断均值门控 |
| `first_layer_verify_windows` | `2` | count | ≥1 | — | 首层正常窗口 |
| `first_layer_min_improvement` | `0.15` | ratio | (0,1] | — | 重试改善率 |
| `event_enabled` | `True` | bool | — | — | 事件开关 |
| `event_window_s` | `30` | s | 1–60 | — | 触发前轨迹 |
| `event_max_points` | `512` | count | 16–2048 | — | 传输点数上限 |
| `runout_gcode` | `unset` | template | — | — | 断料钩子 |
| `jam_gcode` | `unset` | template | — | — | 旧版堵头钩子 |
| `recover_gcode` | `unset` | template | — | — | 恢复准备 |
| `resume_gcode` | `unset` | template | — | — | 显式实测恢复路径 |

不要在 include 中重复定义 SAVE_CONFIG 写入 printer.cfg 的 oh_shit_force。diagnostic_force_limit 为 0 时拒绝诊断，必须标定；不要把默认值当作安全载荷。旧模板参数 TOOL、TARGET、REASON、MSG；双弱定义宏有额外事件元数据，见 RECOVERY。