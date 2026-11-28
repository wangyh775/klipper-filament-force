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

## 高级标定与误判处理

冷标定为可选高级功能，不是装机必做步骤。标定过程绕过低温挤出限制，且不走普通绝对力检测；APPLY=0 仍运动。建议值=峰值×MARGIN，只有峰值和建议值均高于当前阈值才接受，不能降低阈值。未验证送料器、称重和高温热端承载能力时不执行。优先独立确定安全力限制，再监督正常打印。疑似误判先保留日志、模型，检查 PA、流量、温度及送料路径并诊断；仅在机械故障排除且参考确实失效时 RESET 并监督重新学习。禁止把 RESET 后直接 RESUME 当作常规处理。

## 分阶段启用方案

仅合入已有 [filament_force]，勿重复节。下表是分阶段方案，不是通用安全参数。

| 方案 | diagnostic_enabled | diagnostic_auto | auto_resume_enabled | first_layer_z_enabled |
|---|---|---|---|---|
| 基础监控 | False | False | False | False |
| 人工诊断 | True | False | False | False |
| 非首层自动恢复 | True | True | True | False |
| 完整反馈 | True | True | True | True |

方案 2–4 须设置低于设备允许载荷、实测为正的 diagnostic_force_limit，并验证 3 mm/s 的流量（或设定已验证速度）。方案 2：暂停、安全停靠后执行 FILAMENT_FORCE_DIAGNOSE CLEARANCE=1，预期输出结果且保持暂停。方案 3：验证设备专用准备宏，仅在实际安全浮空后 M400 再调用 FILAMENT_FORCE_DIAG_READY CLEARANCE=1；配置非空 resume_gcode 调用真实底层恢复路径。方案 4：额外验证 PAUSE_STATE、正向间隙、轴限位、current_layer=1 及偏移清理。无人值守前须监督实机验证。first_layer_z_enabled=False 时首层诊断仍暂停，不会转入普通自动恢复。

接口示例（注释为有意保留的占位，不是可直接运行的运动方案）：

```ini
[filament_force]
diagnostic_enabled: True
diagnostic_auto: True
auto_resume_enabled: True
# diagnostic_force_limit: 填实测正上限
# resume_gcode: 填已验证的底层恢复宏
first_layer_z_enabled: False
```

准备宏和恢复宏取决于设备。核查 PAUSE/RESUME 的 rename_existing、回抽/复进与停靠路径，先在非打印条件下测试。resume_gcode 禁止递归调用 FILAMENT_FORCE_RESUME；模板收到 params.VELOCITY（未给定为空）。禁止无条件安全授权。

## 换刀与人工恢复接口

换刀前 FILAMENT_FORCE_SUPPRESS_BEGIN，拾取后 FILAMENT_FORCE_SUPPRESS_END TOOL=n，仅停放后无工具时不带 TOOL。单工具一般无需使用。自定义 RESUME 需检查 printer.filament_force.pending_recheck，并仅在故障排除后进入 FILAMENT_FORCE_RESUME；底层恢复宏与插件调用不可递归。原 INDX 及恢复宏完整示例保留于 [英文手册](USER_GUIDE.md#existing-toolchanger-and-manual-resume-integration)，使用前核对本机宏名称、坐标及路径。
