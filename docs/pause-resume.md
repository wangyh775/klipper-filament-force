# Fault pause/resume / 故障暂停与恢复

Normal PAUSE/RESUME are unchanged. FILAMENT_FORCE_PAUSE explicitly requests a module-owned pause (manual reason, no fabricated jam). Detection uses the same internal fault pause path. FILAMENT_FORCE_RESUME authorizes manual recovery of an acknowledged module-owned fault pause; it does not resume a normal pause. The automatic recovery state machine uses the same execution hook. No Monitor dependency.

Weak execution hooks are independently replaceable by user macros:
```ini
[gcode_macro FILAMENT_FORCE_PAUSE_ACTION]
gcode:
    PAUSE

[gcode_macro FILAMENT_FORCE_RESUME_ACTION]
gcode:
    RESUME {("VELOCITY=" ~ params.VELOCITY) if "VELOCITY" in params else ""}
```
Omit either section for the weak default. Default resume uses existing resume_gcode if configured, otherwise native RESUME. The strong lifecycle commands are not override hooks. REASON is passed to both hooks, MODE (manual/automatic) and optional VELOCITY to resume. Do not call the lifecycle command from its own hook. PAUSE must acknowledge pause; RESUME must actually resume the active print. Automatic resume still requires an explicitly configured, tested resume_gcode or custom resume action plus all existing gates. Existing JAM_ACTION remains post-pause diagnostic preparation.

Status filament_force.pause_context contains pause_id, pause_owner, pause_reason, pause_incident_id, pause_phase (none/requested/paused/resumed), acknowledgements and resume_mode. The acknowledged transitions emit filament_force:pause and filament_force:resume and optional Moonraker notify_filament_force_pause / notify_filament_force_resume. Detection events remain separate and retain force windows. Ordinary state changes still appear on Moonraker. A resumed context is historical, not active ownership. Job reset clears the context. An already-paused job is not claimed. Native RESUME is not intercepted; existing watchdog catches a pending fault resumed externally (not instantaneous). A normal PAUSE issued while already fault-paused cannot be distinguished from a duplicate without an explicit user macro integration. Do not assume automatic recovery is safe if operators issue conflicting commands. No model reset while a fault is pending.

普通 PAUSE/RESUME 不变。FILAMENT_FORCE_PAUSE 显式请求模块暂停（manual 原因，不伪造堵头）；自动检测走同一内部暂停入口。FILAMENT_FORCE_RESUME 仅授权恢复已确认归本模块所有的故障暂停，不恢复普通暂停。自动恢复复用同一执行宏。上方两个 ACTION 宏可分别弱定义覆盖，未定义时分别复用 PAUSE 和 RESUME（已有 resume_gcode 优先保留）。强命令负责事务、保护及事件，禁止用 ACTION 递归调用其自身生命周期命令。自动恢复仍需经过已验证的自定义恢复宏或 resume_gcode 及原有门控；原 JAM_ACTION 仍在暂停确认后执行诊断准备。

pause_context 提供暂停 ID、所有者、原因、故障 ID、阶段、确认及恢复方式；确认成功才发 pause/resume 事件，原堵头数据窗口不变。普通状态推送保留，消费方自行关联。resumed 为历史上下文，不代表仍持有暂停；任务重置清除。已由外部暂停的任务不抢占所有权。原生 RESUME 未被拦截，绕过故障锁存由原有看门狗检测并重新暂停，非瞬时拦截。已暂停时再次发普通 PAUSE 无法仅凭原生状态识别，需用户宏协作；不得假定存在冲突指令时自动恢复安全。故障待处理时禁止模型重置。尚需实机验证宏兼容性。
