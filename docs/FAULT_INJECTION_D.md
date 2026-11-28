# Stage D fault injection / 阶段 D 故障注入

Review baseline: 7d20521. Test-only changes; no production behavior modified. Strict xfail captures a known, reproducible defect; XPASS requires re-review and removal of the marker. These are not passing safety tests.

| Case | Injection | Required behavior |
|---|---|---|
| D-F01 | actual printing while RESUMING; stale force | watchdog must not silently exempt a live job |
| D-F02 | native observer mutates payload | retained journal remains immutable to listeners |
| D-F03 | missing pulse onset/tail, healthy middle | no healthy diagnostic authorization |
| Regression | offset command exception | retain ownership, require reconciliation |
| Regression | native observer raises | local pause remains possible |
| Regression | overload after healthy pulse means | FORCE_LIMIT dominates |

审查基准 7d20521，仅新增测试，不修改生产行为。strict xfail 为已知缺陷，不能算安全测试通过；意外通过也必须复审。D-F01：恢复宏已启动打印而状态仍为 RESUMING 时断流；D-F02：原生监听者篡改事件；D-F03：诊断脉冲首尾缺失但中间正常。另验证撤销命令异常保留所有权、监听者异常不阻止本地暂停、超限优先于正常均值。所有运动均模拟，无实机运行。
