#!/usr/bin/env python3
"""
# filament_force - Pause the print on filament runout or jam
#
# Copyright (C) 2026 Charlie Mayall
#
# This file may be distributed under the terms of the GNU GPLv3 license.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Package directory -> klippy/extras/filament_force
PACKAGE_NAME = "filament_force"
# Previous tool_state install used a file shim at extras/filament_force.py
LEGACY_SHIM = "filament_force.py"
EXAMPLE_CFG = "filament_force.cfg"
PRINTER_CONFIG_DIR = Path.home() / "printer_data" / "config"


def ensure_git_exclude(klipper_dir: Path, exclude_line: str) -> None:
    git_dir = klipper_dir / ".git"
    if not git_dir.is_dir():
        return
    exclude_file = git_dir / "info" / "exclude"
    exclude_file.parent.mkdir(parents=True, exist_ok=True)
    exclude_file.touch(exist_ok=True)
    lines = exclude_file.read_text().splitlines()
    if exclude_line not in lines:
        with exclude_file.open("a", encoding="utf-8") as fh:
            if lines and lines[-1]:
                fh.write("\n")
            fh.write(f"{exclude_line}\n")


def install_symlink(target: Path, link: Path) -> Path:
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        print(f"Refusing to replace non-symlink: {link}", file=sys.stderr)
        sys.exit(1)
    link.symlink_to(target)
    return link


def clear_stale_pyc(*roots: Path) -> list[Path]:
    """Remove __pycache__ trees and loose .pyc/.pyo under the given roots.

    Klipper may keep importing stale bytecode after source edits when the
    extras are symlinked in; wipe caches on every install.
    """
    removed: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)

        for pycache in sorted(resolved.rglob("__pycache__"), reverse=True):
            if not pycache.is_dir():
                continue
            shutil.rmtree(pycache)
            removed.append(pycache)

        for pattern in ("*.pyc", "*.pyo"):
            for stale in resolved.rglob(pattern):
                if stale.is_file():
                    stale.unlink()
                    removed.append(stale)
    return removed


def remove_legacy_shim(extras_dir: Path) -> Path | None:
    """Drop extras/filament_force.py so the package directory can own the name."""
    shim = extras_dir / LEGACY_SHIM
    if not shim.exists() and not shim.is_symlink():
        return None
    if shim.is_symlink() or shim.is_file():
        shim.unlink()
        return shim
    print(f"Refusing to replace non-file: {shim}", file=sys.stderr)
    sys.exit(1)


def install(klipper_dir: Path, repo_dir: Path) -> None:
    if not klipper_dir.is_dir():
        print(f"Klipper directory does not exist: {klipper_dir}", file=sys.stderr)
        sys.exit(1)

    package_src = repo_dir / "src" / PACKAGE_NAME
    extras_dir = klipper_dir / "klippy" / "extras"
    package_link = extras_dir / PACKAGE_NAME

    if not package_src.is_dir():
        print(f"Package source not found: {package_src}", file=sys.stderr)
        sys.exit(1)

    extras_dir.mkdir(parents=True, exist_ok=True)
    removed_shim = remove_legacy_shim(extras_dir)

    install_symlink(package_src, package_link)
    ensure_git_exclude(klipper_dir, f"klippy/extras/{PACKAGE_NAME}")
    ensure_git_exclude(klipper_dir, f"klippy/extras/{LEGACY_SHIM}")

    cleared = clear_stale_pyc(package_src, package_link)
    extras_pycache = extras_dir / "__pycache__"
    if extras_pycache.is_dir():
        for pattern in ("filament_force*.pyc", "filament_force*.pyo"):
            for stale in extras_pycache.glob(pattern):
                stale.unlink()
                cleared.append(stale)

    print("Installed extras:")
    print(f"  {package_link} -> {package_src}")
    if removed_shim is not None:
        print(f"  removed legacy shim {removed_shim}")
    if cleared:
        print(f"Cleared {len(cleared)} stale bytecode path(s)")
    else:
        print("No stale bytecode to clear")
    print()


def copy_example_cfg(src: Path, dest: Path) -> bool:
    """Copy example cfg if dest is missing. Returns True if copied."""
    if dest.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def offer_example_config(repo_dir: Path) -> None:
    # Moonraker post_update_script has no TTY. Do not hang on input.
    if not sys.stdin.isatty():
        return
    src = repo_dir / EXAMPLE_CFG
    dest = PRINTER_CONFIG_DIR / EXAMPLE_CFG
    if not src.is_file():
        return
    if dest.exists():
        print(f"config already exists: {dest}")
        return
    if not PRINTER_CONFIG_DIR.is_dir():
        print(f"No {PRINTER_CONFIG_DIR}; copy {EXAMPLE_CFG} into printer_data/config")
        return
    answer = input(f"Copy {EXAMPLE_CFG} to {dest}? (y/n) ").strip().lower()
    if answer not in ("y", "yes"):
        return
    copy_example_cfg(src, dest)
    print(f"Copied {dest}")


def prompt_restart_klipper() -> None:
    if not sys.stdin.isatty():
        return
    answer = input("Restart klipper? (y/n) ").strip().lower()
    if answer in ("y", "yes"):
        subprocess.run(
            ["sudo", "systemctl", "restart", "klipper"],
            check=True,
        )


def install_moonraker(moonraker_dir: Path, repo_dir: Path) -> Path:
    components = moonraker_dir / "moonraker" / "components"
    if not components.is_dir() or not (components / "klippy_apis.py").is_file():
        raise ValueError(f"Not a Moonraker checkout: {moonraker_dir}")
    source = repo_dir / "src" / "filament_force_events.py"
    if not source.is_file():
        raise ValueError(f"Component source missing: {source}")
    link = components / "filament_force_events.py"
    if link.is_symlink() and link.resolve() != source.resolve():
        raise ValueError(f"Refusing to replace unrelated symlink: {link}")
    if link.exists() and not link.is_symlink():
        raise ValueError(f"Refusing to replace existing component: {link}")
    if not link.is_symlink():
        link.symlink_to(source.resolve())
    ensure_git_exclude(moonraker_dir, "moonraker/components/filament_force_events.py")
    stale = components / "__pycache__"
    if stale.is_dir():
        for path in stale.glob("filament_force_events.*.pyc"):
            path.unlink()
    return link


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install filament_force into a Klipper extras directory."
    )
    parser.add_argument(
        "klipper_dir",
        nargs="?",
        default=os.path.expanduser("~/klipper"),
        help="Klipper checkout (default: ~/klipper)",
    )
    parser.add_argument("--moonraker-dir", type=Path, default=None,
                        help="Optionally install the event component into this Moonraker checkout")
    args = parser.parse_args()

    repo_dir = Path(__file__).resolve().parent
    klipper_dir = Path(args.klipper_dir).expanduser().resolve()

    install(klipper_dir, repo_dir)
    if args.moonraker_dir is not None:
        try:
            link = install_moonraker(args.moonraker_dir.expanduser().resolve(), repo_dir)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Moonraker component: {link}")
        print("Add [filament_force_events] to moonraker.conf, then restart Moonraker.")
    offer_example_config(repo_dir)
    print("Add to printer.cfg:")
    print(f"  [include {EXAMPLE_CFG}]")
    print()
    print("Then load filament, run FILAMENT_FORCE_CAL_OH_SHIT, SAVE_CONFIG.")
    print()
    prompt_restart_klipper()


if __name__ == "__main__":
    main()
