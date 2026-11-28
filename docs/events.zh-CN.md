# 事件协议

简体中文 | [English](events.md) · [首页](../README.zh-CN.md)

> 依据 main 提交 25b359b。自动诊断、恢复、Z 补偿均须显式启用，尚未完成实机验收。

![图 11. 故障前受力轨迹示意，非完整采样数据。](media/zh-CN/11-trace.svg)

*图 11. 故障前受力轨迹示意，非完整采样数据。*
Klippy 本地监听通过 `printer.register_event_handler("filament_force:jam_detected", handler)` 接收字典。远程订阅独立 get_status 队列；无需修改 Moonraker，原生事件不会自动转发。

```json
{"jsonrpc":"2.0","method":"printer.objects.subscribe","params":{"objects":{"filament_force":["events"]}},"id":1}
```

| kind | Monitor | 含义 |
|---|---|---|
| jam_detected | filament_jam_detected | 疑似堵头 |
| runout_detected | filament_runout_detected | 断料/送料异常 |
| diagnosis_result | filament_diagnosis_result | 浮空结果 |
| jam_confirmed | filament_jam_confirmed | 重复高阻力 |
| z_adjusted | filament_z_adjusted | 确认偏移 |
| recovery_started | filament_recovery_started | 恢复验证 |
| recovery_verified | filament_recovery_verified | 健康窗口 |
| recovery_failed | filament_recovery_failed | 已覆盖失败路径 |

Schema 1：boot_id（每 Klippy 实例随机）、seq、event_id=boot_id:seq、kind、host_monotonic_s、incident_id、filename。初始检测 incident_id=null，后续关联其 event_id。检测字段 source、layer、tool、force_g、e_speed_mm_s、target_c、detection_length_mm、absolute_limit_g、window。窗口含 clock、start_time、duration_s、sample_count、returned_count、downsampled、force_ref_g、columns、samples、windows。每采样点 [相对 MCU print time 秒, 有符号标定 gf]；统计窗口使用 host monotonic 时间，不是 UTC，不可直接相减。独立轨迹可能含空闲/移动，内存最多 40000 点、默认 30 s、传输最多 512 点、最近 32 个统计窗口。分桶极值降采样有损。仅保留最近 16 条事件，重启或长断线可丢失未读事件。Monitor SQLite 按源 ID 去重，并将结构化 event 通过签名 Webhook 转发。

## 诊断及恢复事件字段

diagnosis_result 携带 result、diagnostic_speed_mm_s、reference_compatible、pulse_means_g、pulse_peaks_g、extruded_mm。z_adjusted 携带 step_mm、total_mm。recovery_started 与 recovery_verified 携带 attempts，后者额外携带 before_z_score、after_z_score、improvement（可能为 null）。recovery_failed 携带 reason，但并非所有失败路径都发出该事件。初始事件关联后续事件仅在同一故障期间有效。

以下为简化结构示例，数值不是实测：

```json
{
  "schema": 1,
  "boot_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "seq": 12,
  "event_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:12",
  "incident_id": null,
  "kind": "jam_detected",
  "source": "hard",
  "layer": 1,
  "force_g": 4200.0,
  "e_speed_mm_s": 1.0,
  "window": {
    "clock": "mcu_print_time",
    "columns": ["t_s", "force_g"],
    "samples": [[0.0, 530.0], [0.1, 4200.0]]
  }
}
```

远程链路图及路由说明参见 [Monitor](https://github.com/wangyh775/hermes-plugin-kalico-monitor/blob/main/docs/ARCHITECTURE.zh-CN.md).
