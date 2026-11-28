# Event protocol / 事件协议 (schema 1)

Internal Klippy listeners may register with `printer.register_event_handler("filament_force:jam_detected", handler)`; the handler receives one event dictionary. Native dispatch uses a reactor callback; observers must be nonblocking and must not issue movement. Observer failures do not authorize recovery. Remote clients subscribe to the `events` field of the `filament_force` status object via Moonraker. Native events are not automatically forwarded by Moonraker.

固件内部通过 register_event_handler 订阅，回调收到一个字典；事件通过 reactor 回调发送，观察者不得阻塞或控制运动。远程端通过 Moonraker 订阅状态字段，不依赖修改 Moonraker 源码。

| Klippy event suffix / 状态 kind | Monitor event kind | Meaning / 含义 |
|---|---|---|
| jam_detected | filament_jam_detected | Suspected jam / 疑似堵头 |
| runout_detected | filament_runout_detected | Low force / 断料或送料异常 |
| diagnosis_result | filament_diagnosis_result | Free-air result / 浮空诊断 |
| jam_confirmed | filament_jam_confirmed | Repeated high resistance / 重复高阻力 |
| z_adjusted | filament_z_adjusted | Offset applied / Z 补偿 |
| recovery_started | filament_recovery_started | Resume requested and acknowledged / 恢复验证 |
| recovery_verified | filament_recovery_verified | Healthy windows / 受力验证通过 |
| recovery_failed | filament_recovery_failed | Recovery stopped / 恢复失败 |

Schema: every event has schema=1, boot_id (random per Klippy instance), seq (monotonic per boot), event_id=boot_id:seq, kind, host_monotonic_s, incident_id and filename. The initial detection has incident_id=null; subsequent events reference its event_id. Detection fields include source, force_g, e_speed_mm_s, layer, tool, target_c, detection_length_mm, absolute_limit_g. Diagnosis contains result, diagnostic_speed_mm_s, reference_compatible, pulse_means_g, pulse_peaks_g and extruded_mm. Recovery events include relevant attempt, offset, failure or z-score fields.

Detection window: raw calibrated load-cell readings before trip handling, captured independently of the detector's rolling average. Time is MCU print time relative to start_time, not wall-clock UTC; window summaries use host monotonic time. Contains force_ref_g (nullable), duration_s, sample_count, returned_count, downsampled, columns=[t_s,force_g], samples and recent statistical windows. The two clocks must not be directly subtracted. Trace may include travel/idle and is bounded; it is not an exact copy of the scoring accumulator. Min/max bucket sampling preserves peaks but is not lossless. Empty/short traces are possible on startup. At most 40000 readings retained in memory; defaults are 30 s / 512 transmitted points; recent 32 window summaries. Use a separate acquisition tool for full-rate research datasets.

检测窗口是独立的触发前受力轨迹，不等同于原算法滑动均值缓存；包含可能的空闲及移动，保峰降采样而非全量无损 ADC 数据。时间戳分别为 MCU print time 和 host monotonic，两者不可直接相减。窗口最大 40000 原始点、默认 30 秒及最多 512 个传输点，最近 32 个统计窗口。初始事件用自身 event_id 关联后续事件。

```ini
[filament_force]
# ... existing settings
event_enabled: True
event_window_s: 30.0
event_max_points: 512
auto_resume_reset_s: 60.0
```

```json
{"jsonrpc":"2.0","method":"printer.objects.subscribe","params":{"objects":{"filament_force":["events"]}},"id":1}
```

Only the last 16 events are replayable from Klippy memory; a longer outage or restart can lose unseen events. Monitor durably deduplicates by event_id in SQLite after receipt, and includes the event dictionary in signed Hermes webhook JSON as event. Normal pause/resume events remain independent. Configure KALICO_WATCH_NOZZLE_FORCE=1 and individual event routes in Monitor. No direct HTTP from Klippy and no remote recovery commands. Test actual integration before enabling automatic recovery.

Klippy 内存仅保留最近 16 条事件；重启或超出保留范围可能丢失尚未读取事件。Monitor 收到后持久化 SQLite，并按 event_id 去重，Hermes 签名 Webhook 的 event 字段包含完整传输结构。原有暂停/恢复通知不受影响。开启 KALICO_WATCH_NOZZLE_FORCE=1，按事件配置 direct/agent/both/off。Klippy 不直接联网，Monitor 不执行运动命令。
