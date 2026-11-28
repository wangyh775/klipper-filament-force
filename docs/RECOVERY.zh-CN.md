# 诊断与恢复

简体中文 | [English](RECOVERY.md) · [首页](../README.zh-CN.md)

> 依据 main 提交 25b359b。自动诊断、恢复、Z 补偿均须显式启用，尚未完成实机验收。

![图 5. 两种堵头来源共享诊断入口。](media/zh-CN/05-strategies.svg)

*图 5. 两种堵头来源共享诊断入口。*
核心先暂停，再执行弱定义准备宏 `FILAMENT_FORCE_JAM_ACTION`，参数 TOOL、SOURCE、FORCE_G、E_SPEED、TARGET、FIRST_LAYER。设备安全停靠且 M400 后才可执行 `FILAMENT_FORCE_DIAG_READY CLEARANCE=1`。默认不授权。`FILAMENT_FORCE_CONFIRMED_JAM_ACTION` 处理重复浮空高阻力，默认保持暂停并提示；新增 DIAG_MEAN_G、DIAG_PEAK_G、RESULT。断料独立处理。

![图 6. 物理解释，不是出料确证。](media/zh-CN/06-free-air.svg)

*图 6. 物理解释，不是出料确证。*
![图 7. 名义脉冲时序，非实测。](media/zh-CN/07-pulses.svg)

*图 7. 名义脉冲时序，非实测。*
默认速度 3 mm/s，可选匹配模式以配置速度为上限。实际 E 长度 max(配置最小长度, v×0.5 s)，默认 1.5 mm×3。空闲 0.8 s 取中位数，至少五个样本，默认最大跨度 30 gf。名义运动中段 60% 统计基准相对绝对力，检查覆盖。峰值上限 min(diagnostic_force_limit, oh_shit_force)，只能阻止后续脉冲，不能取消队列中运动。全部高力→restriction_suspected；全部低力→low_force；全部在范围内→flow_compatible；混合/缺失/范围无效→inconclusive；超限→force_limit。优先诊断速度组模型，人工备用范围不能授权自动恢复。诊断速度不低于触发速度时可跨可信组；较低速度需同组且 ≥80% 触发速度。不独立学习浮空模型。正常受力不证明出料；跨组假设须实机验证。

![图 8. 有限反馈策略，不是拟合的力—间隙曲线。](media/zh-CN/08-z-feedback.svg)

*图 8. 有限反馈策略，不是拟合的力—间隙曲线。*
恢复需显式启用、同工具/温度、明确层数、可信模型及实测 resume_gcode。非首层不调 Z；首层还要求 first_layer_z_enabled 与原始归零/高度条件。同步调整兼容 PAUSE_STATE 的 base_position、homing_position、last_position，并核对恢复后原点。默认 +0.02 mm，单任务最多 3 次/0.06 mm，间隔 10 s。比较归一化异常：z_before > 0 且窗口口径可比时，改善率 = 1 − z_after/z_before。绝对峰值不可直接比较。首层两个正常窗口或普通三个完成验证；60 s 超时，低力/无改善/预算耗尽暂停。健康观测 60 s 后重置连续次数，不清零累计或 Z 预算。结束时仅在原点未改变时尝试撤销本模块偏移；崩溃后人工确认。

![图 9. 主要状态转换，运动均须满足条件。](media/zh-CN/09-fsm.svg)

*图 9. 主要状态转换，运动均须满足条件。*


## 精确的诊断及恢复条件

第 j 个脉冲均值 m_j = 名义区间中间 60% 样本的 |Fᵢ−F_idle| 平均值；峰值 p_j 为捕获脉冲样本的最大绝对偏差。可用学习参考要求 μ、σ 有限，μ > min_delta_g > 0、σ ≥ 0、high_sigma > 0。诊断下界为 max(min_delta_g, L_low)，须满足 0 < 下界 < H < 安全上限，不截断 H。不满足时人工范围可分类，但不能授权自动恢复。短脉冲与打印滑动窗口统计量不等价，跨组使用是待实机验证的工程假设。基准 0.8 s，名义脉冲至少 0.5 s，每次 M400 后等待 0.3 s；实际运动由规划器决定。

恢复额外要求 band/hard 来源（model_validation 不授权）、已知层数、两个可信速度组及全局参考、同活动挤出机、实际温度与目标温度分别距原正目标不超过 10 ℃、heater.can_extrude、实测恢复模板。VERIFYING 期间再次硬超限可诊断但不能自动恢复。首层还要求所有诊断脉冲均值 ≤ first_layer_z_max_force。非首层采用普通次数预算，首层采用独立单任务 Z 预算。

VERIFYING 统计正常窗口及连续异常窗口。NONE 清除异常计数，异常清除正常计数；缺失/未验证参考清除正常计数，短段跳过。异常达 confirm_windows（默认 3）才判断重试：HIGH 且有预算、首层改善足够可重试；LOW 或改善不足停止验证。独立 60 s 超时即使无有效窗口也可暂停。并非每个 FAILED 都发 recovery_failed，亦须查询 recovery_state、recovery_failure。暂停请求不是硬件急停。
