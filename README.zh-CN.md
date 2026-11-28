# filament_force

简体中文 | [English](README.md)

基于热端称重传感器的 Klipper/Kalico 挤出力监控模块，用于检测堵头、断料和送料异常。需要 `[load_cell_probe]` 或 `[load_cell]`。模块由 Klippy 主机进程加载，不是独立服务，不需要重新编译 MCU 固件。

## 安装与更新

稳定分支：

```sh
cd ~
git clone https://github.com/wangyh775/klipper-filament-force.git
cd klipper-filament-force
./install.sh ~/klipper
```

如果 Kalico 实际源码目录为 ~/kalico，则执行 `./install.sh ~/kalico`。安装器建立从 `klippy/extras/filament_force/` 到仓库 `src/filament_force/` 的符号链接，清理缓存，交互询问是否复制配置与重启服务。已有配置不会覆盖；不需要 pip 安装。当前恢复功能位于实验分支 feature/diagnostic-recovery-fsm，未通过全部集成及实机验证前不要用于生产打印。

在 printer.cfg 中加入：

```ini
[include filament_force.cfg]
```

确认配置、在打印机空闲时重启。安装后的模块可通过 Mainsail 控制台 `FILAMENT_FORCE_QUERY` 查询。更新时：

```sh
cd ~/klipper-filament-force
git pull --ff-only
./install.sh ~/klipper
```

将新增配置手工合入已有 CFG，重启 Klipper。Moonraker 可选配置（稳定 main 分支）：

```ini
[update_manager filament_force]
type: git_repo
path: ~/klipper-filament-force
origin: https://github.com/wangyh775/klipper-filament-force.git
primary_branch: main
managed_services: klipper
is_system_service: False
post_update_script: install.sh
```

若固件目录或服务名不是默认值，应按本机情况调整；非交互安装不复制配置、不主动重启服务。更新管理器默认 post_update_script 使用 ~/klipper。

## 初次使用与检测

确认称重传感器已标定、耗材已装载、设备允许的安全载荷已明确。绝对力阈值可通过 `FILAMENT_FORCE_SET OH_SHIT_FORCE=<g>` 临时调整；项目提供 `FILAMENT_FORCE_CAL_OH_SHIT` 冷挤出峰值标定及 SAVE_CONFIG 持久化。冷挤出主动制造高负载并绕过温度限制，仅在确认硬件安全后监督执行，禁止打印中执行。不要在 include 文件中重复定义通过 SAVE_CONFIG 写入 printer.cfg 的 oh_shit_force。

统计检测按 E 轴进给距离划分窗口（默认 7 mm），按挤出速度组学习受力均值和标准差。默认三个异常窗口确认统计堵头。独立绝对力保护无需模型。断料使用低力参考。有效窗口与传感器状态、空闲、回抽和最低挤出速度有关。

## 模型持久化

默认启用：model_persistence=True、model_save_interval=60 秒。模型保存到 ~/printer_data/config/filament_force_model.json；非默认 model_profile 使用独立文件。采用原子写入及独立工作线程；仅保存健康窗口，不保存运行中的异常计数、零点和故障状态。重启后先验证恢复的参考，连续不匹配会暂停而不是把异常学成正常。工艺、材料、喷嘴、温度、PA 或传感器安装改变时使用新模型标识。FILAMENT_FORCE_RESET [TOOL=n] 清除相应历史并尝试持久化，不能用它掩盖未解决的故障。

## 统一堵头诊断（实验功能）

统计堵头、绝对力超限、历史模型验证异常共用诊断入口，先暂停，再执行策略一。断料独立暂停。绝对力超限不等于真性堵头。

- FILAMENT_FORCE_JAM_ACTION：诊断前准备。核心已暂停；自定义宏负责安全停靠、浮空、废料处理。参数 TOOL、SOURCE、FORCE_G、E_SPEED、TARGET、FIRST_LAYER。
- FILAMENT_FORCE_CONFIRMED_JAM_ACTION：浮空重复高阻力时调用。另含 DIAG_MEAN_G、DIAG_PEAK_G、RESULT。默认提示并保持暂停；不要从该宏直接恢复。

配置示例（均为实验分支参数，诊断力限制需标定）：

```ini
[filament_force]
sensor: load_cell_probe
diagnostic_enabled: False
diagnostic_auto: False
diagnostic_speed: 3.0
diagnostic_match_speed: False
diagnostic_force_limit: 0
diagnostic_force_min: 0
diagnostic_force_max: 0
diagnostic_pulse_mm: 0.5
diagnostic_pulses: 3
diagnostic_baseline_span: 30.0
auto_resume_enabled: False
auto_resume_max_attempts: 2
auto_resume_verify_windows: 3
recovery_verify_timeout: 60.0
first_layer_z_enabled: False
first_layer_z_step: 0.02
first_layer_z_max_adjustments: 3
first_layer_z_max_total: 0.06
first_layer_z_cooldown_s: 10.0
first_layer_z_max_height: 0.60
first_layer_z_max_force: 2000.0
first_layer_verify_windows: 2
first_layer_min_improvement: 0.15
```

诊断速度默认固定 3 mm/s（E 轴耗材进给，范围 0.5–6 mm/s），可通过 CFG 修改。可选匹配模式以该配置速度为上限。脉冲最短持续时间 0.5 s，实际长度为 max(配置最小长度, 速度×0.5 s)，最大 3 mm；默认实际 1.5 mm/次，三次合计 4.5 mm。高温 PEEK 的允许流量及安全载荷必须实测。诊断受力优先复用对应速度组打印模型，人工上下限仅为备用；诊断数据不训练模型。诊断速度不低于故障速度时，两个速度组模型均可信即可跨组评估恢复；诊断速度较低时仅允许同组且偏差不超过 20%。仍需实机验证。正常受力不保证实际出料；力超限终止后续脉冲，不会即时撤销已排队运动。

人工确认喷嘴安全浮空后执行 FILAMENT_FORCE_DIAGNOSE CLEARANCE=1。自动诊断仅在经过验证的准备宏执行 M400 后显式调用 FILAMENT_FORCE_DIAG_READY CLEARANCE=1 时授权，默认宏不移动、不授权。人工命令默认只诊断；RECOVER=1 才请求恢复。

## 自动恢复与首层补偿

自动恢复需显式启用、明确层数、匹配可信模型、同一工具和温度，以及实测兼容的 resume_gcode。非首层诊断正常可有限恢复，不改 Z；首层则需单独启用 first_layer_z_enabled。每次补偿默认 0.02 mm，最多三次且累计不超过 0.06 mm。修改兼容 Kalico PAUSE_STATE 的 Z 基准与恢复位置，避免被 RESUME 覆盖，恢复后检查实际偏移。仅在确认打印机正方向增加喷嘴间隙、运动路径安全且恢复宏兼容时启用。

恢复后冻结正常模型，首层默认两个健康窗口，非首层三个健康窗口；60 秒超时暂停。首层若高力持续且归一化异常改善至少 15%，可有限重试；严重超限、低力或无改善时暂停。绝对峰值和窗口均值不直接比较改善率。结束时尝试只撤销本任务的补偿，异常关机或宏改变偏移时需人工检查。不会自动修改 PA。

## 换刀与主动耗材检查

换刀前 FILAMENT_FORCE_SUPPRESS_BEGIN，成功拾取后 FILAMENT_FORCE_SUPPRESS_END TOOL=n；仅停放后无工具时执行 FILAMENT_FORCE_SUPPRESS_END。单工具打印机通常无需配置。自定义 RESUME 应与 FILAMENT_FORCE_RESUME 和底层恢复路径兼容，禁止递归调用。详见英文文档的 INDX 示例。

FILAMENT_FORCE_CHECK_SPIKE 是独立的主动回抽/复进耗材存在检查：默认回抽 3 mm、复进 3.2 mm，峰值变化至少 50 g 判为存在。不是实时堵头检测。喷嘴必须满足挤出温度；不要在正常打印挤出中执行。同一 Jinja 模板会提前求值，结果应在后续宏读取 last_probe_spike、last_probe_delta_g。支持 SPIKE_G、RETRACT、EXTRA_PRIME、FEEDRATE 等参数。

## 常用命令与状态

| 命令 | 功能 |
|---|---|
| FILAMENT_FORCE_SET | 查询或修改核心参数 |
| FILAMENT_FORCE_SET ENABLE=0/1 | 开关连续检测 |
| FILAMENT_FORCE_QUERY | 查询模型、受力、诊断及恢复状态 |
| FILAMENT_FORCE_RESET [TOOL=n] | 清除历史 |
| FILAMENT_FORCE_CAL_OH_SHIT | 监督冷挤出标定 |
| FILAMENT_FORCE_TEST_RUNOUT RETRACT=<mm> TEMP=<c> | 监督断料测试 |
| FILAMENT_FORCE_CHECK_SPIKE | 主动耗材存在检查 |
| FILAMENT_FORCE_DIAGNOSE CLEARANCE=1 [RECOVER=1] | 人工确认后的浮空诊断 |
| FILAMENT_FORCE_DIAG_READY CLEARANCE=1 | 准备宏内安全浮空确认 |
| FILAMENT_FORCE_RESUME [VELOCITY=v] | 故障恢复 |
| FILAMENT_FORCE_SET_TOOL TOOL=n | 指定工具 |
| FILAMENT_FORCE_SUPPRESS ENABLE=0/1 | 临时抑制检测 |

Moonraker 对象 filament_force 暴露 recovery_state、recovery_attempts、recovery_healthy_windows、recovery_failure、recovery_last_z_score、diagnostic_result、diagnostic_pulse_means_g、diagnostic_pulse_peaks_g 等状态。

## 开发与验证

```sh
uv sync
uv run pytest
uv run ty check src tests
```

[中文设计文档](docs/diagnostic-recovery.zh-CN.md) | [English design](docs/diagnostic-recovery.md) | [示例配置](filament_force.cfg)

自动诊断、恢复和 Z 补偿默认关闭，须完成 CI 和实机安全验证才启用。

## 原生事件与远程监控

参见 [事件协议（中英文）](docs/events.md)。原生 Klippy 事件 filament_force:<kind> 与状态对象 filament_force.events 同时提供，堵头事件包含故障前受力轨迹、窗口统计与唯一 ID。默认保留 30 秒轨迹、最多 512 个保峰降采样点及最近 16 个事件；非完整原始 ADC 数据。Monitor 可经 Moonraker 订阅并将事件及 JSON 数据写入 SQLite、转发 Hermes。连续健康打印默认 60 秒后重置连续恢复次数，单任务累计次数独立记录。
