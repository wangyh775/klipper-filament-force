# 用户手册

简体中文 | [English](USER_GUIDE.md) · [首页](../README.zh-CN.md)

> 依据 main 提交 25b359b。自动诊断、恢复、Z 补偿均须显式启用，尚未完成实机验收。

## 调试顺序

1. 检查称重标定、稳定基准、硬件安全载荷和独立联锁；监督健康打印，学习实际速度组。
2. FILAMENT_FORCE_QUERY 查看 enabled（空闲可能未布防）、模型状态、待验证、各组窗口数量、保存错误。
3. JAM 后检查打印与暂停状态，安全停靠后才在已标定安全上限条件下诊断。高阻力需排故后人工恢复，不要通过清模型掩盖异常。
4. 自动动作启用前分别验证诊断运动、同温度参考、恢复路径和 Z 方向。

## 命令

| G-code | 用途 |
|---|---|
| `FILAMENT_FORCE_QUERY` | 模型及恢复状态 |
| `FILAMENT_FORCE_SET [ENABLE=0/1]` | 运行时配置 |
| `FILAMENT_FORCE_RESET [TOOL=n]` | 清除历史并保存 |
| `FILAMENT_FORCE_CAL_OH_SHIT [MAX_TEMP=50] [EXTRUDE=8] [SPEED=2] [MARGIN=0.5] [APPLY=1]` | 冷挤出标定，仅监督执行 |
| `FILAMENT_FORCE_TEST_RUNOUT RETRACT=<mm> TEMP=<C>` | 监督断料测试 |
| `FILAMENT_FORCE_CHECK_SPIKE` | 耗材存在主动检查，非实时堵头 |
| `FILAMENT_FORCE_DIAGNOSE CLEARANCE=1 [RECOVER=1]` | 浮空诊断；默认不恢复 |
| `FILAMENT_FORCE_DIAG_READY CLEARANCE=1` | 准备宏内安全授权 |
| `FILAMENT_FORCE_RESUME [VELOCITY=v]` | 故障恢复 |
| `FILAMENT_FORCE_SET_TOOL TOOL=n` | 活动工具 |
| `FILAMENT_FORCE_SUPPRESS ENABLE=0/1` | 换刀抑制 |
| `FILAMENT_FORCE_SUPPRESS_BEGIN / END [TOOL=n]` | 换刀示例宏 |

冷标定主动推压冷喷嘴并绕过温度挤出门控，可能损伤耗材、传感器和送料器；只在已知安全载荷且监督下执行，禁止打印时运行。APPLY=0 仍有运动。SAVE_CONFIG 保存接受的阈值。主动存在检查采用回抽/复进峰值；Jinja 同宏预渲染，结果在后续宏读取。