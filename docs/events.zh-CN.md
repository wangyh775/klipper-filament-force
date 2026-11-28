# 公开事件协议（schema 1）

[English](events.md) | [简体中文](events.zh-CN.md)

Filament Force 是独立 Klippy Extra。本地检测、暂停、恢复及事件生产不依赖 Moonraker 或任何事件消费方。提供 Klippy 内部事件、Moonraker 标准对象状态队列以及可选的独立 Moonraker 通知。可选组件只订阅和广播，不执行打印机指令、不路由到外部服务、不需要额外常驻进程。

## 可选 Moonraker 原生通知

```bash
cd ~/klipper-filament-force
./install.sh ~/klipper --moonraker-dir ~/moonraker
```

路径按实际 Klipper/Kalico、Moonraker 源码目录替换。安装器将独立组件软链接到 moonraker/components，不修改核心源码、不自动编辑配置。空闲时在 moonraker.conf 加入下列配置并重启 Moonraker。不需要该组件时可省略安装选项及配置节。

```ini
[filament_force_events]
```

```bash
sudo systemctl restart moonraker
```

连接标准 /websocket 端点（通常 7125 端口），按服务端策略认证，监听下列 JSON-RPC 通知。独立通知无需客户端额外注册或订阅。组件使用 Moonraker register_notification 注册，并在内部订阅对象状态，保留原始负载。

| Klippy | Moonraker | 含义 |
|---|---|---|
| `filament_force:jam_detected` | `notify_filament_force_jam_detected` | 疑似堵头 |
| `filament_force:runout_detected` | `notify_filament_force_runout_detected` | 断料或送料异常 |
| `filament_force:diagnosis_result` | `notify_filament_force_diagnosis_result` | 浮空诊断结果 |
| `filament_force:jam_confirmed` | `notify_filament_force_jam_confirmed` | 浮空重复高阻力 |
| `filament_force:z_adjusted` | `notify_filament_force_z_adjusted` | 已应用 Z 补偿 |
| `filament_force:recovery_started` | `notify_filament_force_recovery_started` | 恢复动作已确认 |
| `filament_force:recovery_verified` | `notify_filament_force_recovery_verified` | 恢复受力验证通过 |
| `filament_force:recovery_failed` | `notify_filament_force_recovery_failed` | 恢复或保护失败 |
| `filament_force:sensor_fault` | `notify_filament_force_sensor_fault` | 传感器或基准异常 |
| `filament_force:pause` | `notify_filament_force_pause` | 模块故障暂停确认 |
| `filament_force:resume` | `notify_filament_force_resume` | 模块故障恢复确认 |

## 示例：堵头通知

模拟数据，非实测。jam_detected 携带故障受力窗口；jam_confirmed 复用原故障窗口，另含 window_event_id 与诊断脉冲统计；若原快照已不可用，window 为 null，不伪造数据。

```json
{
  "jsonrpc": "2.0",
  "method": "notify_filament_force_jam_detected",
  "params": [
    {
      "schema": 1,
      "boot_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "seq": 12,
      "event_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:12",
      "incident_id": null,
      "kind": "jam_detected",
      "host_monotonic_s": 1200,
      "filename": "example.gcode",
      "source": "hard",
      "force_g": 4200,
      "tool": 0,
      "layer": 1,
      "e_speed_mm_s": 2.5,
      "target_c": 400,
      "detection_length_mm": 7,
      "absolute_limit_g": 4000,
      "window": {
        "clock": "mcu_print_time",
        "start_time": 100,
        "duration_s": 0.2,
        "sample_count": 3,
        "returned_count": 3,
        "downsampled": false,
        "force_ref_g": 100,
        "columns": [
          "t_s",
          "force_g"
        ],
        "samples": [
          [
            0,
            520
          ],
          [
            0.1,
            4300
          ],
          [
            0.2,
            4320
          ]
        ],
        "windows": []
      }
    }
  ]
}
```

窗口为标定受力（gf），不是原始 ADC 计数，可能含空闲及移动。它是故障处理前的有限轨迹，不等于评分累计器或精确触发截止。分桶最小/最大值降采样保留极值但有损。默认 30 s / 最多 512 输出点，内存最多 40000 点及最近 32 个统计窗口。MCU print-time 相对时间与主机单调时钟不可直接相减。

## 状态订阅及历史

```json
{"jsonrpc":"2.0","method":"printer.objects.subscribe","params":{"objects":{"filament_force":["events"]}},"id":1}
```

即使未安装可选组件，上述订阅也可使用未修改的 Moonraker。通过 printer.objects.query 或 GET /printer/objects/query?filament_force=events 查询快照。Klippy 内部通过 printer.register_event_handler('filament_force:jam_detected', handler) 注册，回调收到一个字典，不得阻塞。

```ini
[filament_force]
# ... existing settings
event_enabled: True
event_window_s: 30.0
event_max_points: 512
```

## 投递语义

组件广播首次订阅的保留快照及后续队列变化，在当前 Moonraker 进程按 boot_id、seq 去重。同一进程重连不会重复广播已见事件；Moonraker 重启可能重播最近 16 条事件。消费端应按 event_id 去重，连接后可查询有限历史。首次检测 incident_id=null，后续事件引用其 event_id。序号缺失可记录日志，但无法找回已淘汰数据。这是尽力广播，不提供持久化队列、逐客户端 ACK 或严格一次语义。Klippy 重启清空队列，断线、停机及长时间中断可能丢失事件。本地保护不等待通知投递。

需要在目标打印机验证 Klipper/Moonraker API 集成及实际广播延迟。自动测试模拟 Moonraker 组件 API，不涉及实机运动。

暂停恢复事件含 pause_id、pause_owner、pause_reason、pause_incident_id、pause_phase、pause_requested、pause_acknowledged、resume_acknowledged、resume_mode、print_state；原生 PAUSE/RESUME 状态保持不变，详见 [独立暂停恢复](pause-resume.md)。
