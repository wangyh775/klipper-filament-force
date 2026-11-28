# Second reliability repair / 第二轮可靠性整改

D-F01: live print watchdog no longer exempts recovery states. If the queued pause cannot complete within sensor_timeout_s and printing continues, request Klippy shutdown without the G-code mutex. Explicit suppression is retained outside recovery; ordinary intentional pause is not treated as live printing. D-F02: deep copy event input, return and status. D-F03: full nominal pulse coverage required before middle 60% scoring. A cap detected during diagnosis or pre-resume capture schedules a host shutdown by default (diagnostic_shutdown_on_limit: True). This is not a real-time hardware interlock; buffered samples, queued motion, reactor scheduling and MCU response require bench qualification. Disabling the option retains pulse termination only.

D-F01：实际打印时不因恢复状态豁免看门狗；暂停回调若在 sensor_timeout_s 内未完成且仍在打印，绕过 G-code mutex 请求 Klippy shutdown。正常换刀显式抑制保留。D-F02：事件输入、返回与查询深复制隔离。D-F03：完整名义脉冲覆盖合格才计算中间 60%。诊断或恢复前采样超限默认请求主机停机（diagnostic_shutdown_on_limit: True），并非实时硬件联锁；批次延迟、已下发运动、reactor 与 MCU 响应仍须台架验证。关闭选项仅终止后续脉冲。

Window quality: reject buffered samples outside MCU print-time age 1 s or >0.1 s in the future; reset hard dwell on gaps >0.05 s. Normal windows require ≥5 samples, bounded gap and sufficient observed span (poll period + age tolerance); invalid windows freeze learning/verification and repeated invalid windows request protection pause. This is conservative coverage gating, not exact motion-synchronized integration. New quality parameters enter the model fingerprint.

窗口质量：使用 MCU print-time 判断积压数据（默认 1 s）及超前时间（0.1 s），间隔超 0.05 s 重置硬力持续计时。普通窗口最少 5 点、限制最大间隔及观测时长（允许轮询与数据年龄误差）；不合格冻结学习及验证，连续不合格触发保护暂停。此为保守覆盖门控，非严格运动同步积分。新质量参数纳入模型指纹。
