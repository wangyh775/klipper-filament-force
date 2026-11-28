# 安装与升级

简体中文 | [English](INSTALL.md) · [首页](../README.zh-CN.md)

> 依据 main 提交 25b359b。自动诊断、恢复、Z 补偿均须显式启用，尚未完成实机验收。

## 安装与升级

需要兼容 Klipper/Kalico 源码与已标定的 `[load_cell_probe]` 或 `[load_cell]`。使用 Klippy 所在系统用户，打印结束后操作。

```sh
cd ~
git clone https://github.com/wangyh775/klipper-filament-force.git
cd klipper-filament-force
./install.sh ~/klipper
```

若源码在 ~/kalico，替换参数。脚本将 src/filament_force 符号链接至 klippy/extras/filament_force，删除旧文件 shim、清理缓存；交互时询问复制缺失配置及重启，已有 CFG 不覆盖。安装前检查旧 shim。无需 MCU 编译或独立服务。在 printer.cfg 加入：

```ini
[include filament_force.cfg]
```

升级先备份 CFG/模型 JSON，git pull --ff-only 后重跑相同安装命令；手工合入新增项。重启后 FILAMENT_FORCE_QUERY。Moonraker 更新管理（仅默认固件目录与服务名）：

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

回滚时停止打印，禁用 include、恢复旧 CFG/模型备份，或切回已验证提交重跑安装器并重启。不要混用不兼容模型。