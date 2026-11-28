# Installation

English | [简体中文](INSTALL.zh-CN.md) · [Home](../README.md)

> Reference: main commit 25b359b. Automatic diagnosis, resume and Z compensation are opt-in and have not been qualified on hardware.

## Install / upgrade

Requires a compatible Klipper/Kalico checkout and calibrated `[load_cell_probe]` or `[load_cell]`. Use the same OS user as Klippy. Stop printing before changes.

```sh
cd ~
git clone https://github.com/wangyh775/klipper-filament-force.git
cd klipper-filament-force
./install.sh ~/klipper
```

If actual checkout is ~/kalico, pass that instead. The script symlinks src/filament_force to klippy/extras/filament_force, removes the legacy file shim and stale bytecode, may copy the sample config if absent and asks to restart in a TTY. It will not replace an existing CFG. Inspect any legacy shim before installing. No MCU rebuild or separate service. Add to printer.cfg:

```ini
[include filament_force.cfg]
```

For upgrades back up CFG/model JSON, run git pull --ff-only then the same install command; merge new options manually. Restart and run FILAMENT_FORCE_QUERY. Moonraker manager (default firmware path/service only):

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

For rollback stop printing, disable the include, restore the previous CFG and model backup, or check out a known working commit and rerun installer; restart. Do not downgrade with an incompatible model file.