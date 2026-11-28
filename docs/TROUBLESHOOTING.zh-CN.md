# 故障排查

简体中文 | [English](TROUBLESHOOTING.md) · [首页](../README.zh-CN.md)

> 依据 main 提交 25b359b。自动诊断、恢复、Z 补偿均须显式启用，尚未完成实机验收。

| 现象 | 检查与处理 |
|---|---|
| 未布防 | 打印状态、检测开关、抑制、传感器及空闲基准 |
| 多次误判 | last_trip_source、受力窗口；排查 PA、加速度、流量和惯性；监督对照后再调阈值 |
| 模型缺失/不确定 | profile、路径权限、指纹、写入错误、健康窗口；勿为消警而重置 |
| 拒绝诊断 | 暂停任务、同工具/温度、诊断力上限、安全授权、单次诊断 |
| 浮空正常却不恢复 | 自动开关、层数、可信组、速度门控、resume_gcode、预算 |
| Z 未生效 | 层信息、原始归零/高度、PAUSE_STATE 与恢复宏、偏移方向及限值 |
| 远程事件缺失 | 查询 filament_force.events；Monitor 订阅开关；仅 16 条重连保留 |
| 轨迹过短 | 实际传感器流、40000 点内存上限及窗口清除；不是完整 ADC 导出 |

调阈值前收集 FILAMENT_FORCE_QUERY、klippy.log、配置。调试日志 FILAMENT_FORCE_SET DEBUG_LOG=1。不要为排查关闭绝对保护。