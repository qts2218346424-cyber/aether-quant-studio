"""为 Aether Quant Studio · 苍穹量枢 在 Windows 桌面与开始菜单创建专属软件快捷方式"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import win32com.client

ROOT = Path(__file__).resolve().parents[1]
ICON_ICO = ROOT / "static" / "icons" / "app_icon.ico"
VBS_LAUNCHER = ROOT / "启动苍穹量枢.vbs"
EXE_LAUNCHER = ROOT / "苍穹量枢.exe"


def create_shortcuts():
    shell = win32com.client.Dispatch("WScript.Shell")
    desktop_dir = Path(shell.SpecialFolders("Desktop"))
    programs_dir = Path(shell.SpecialFolders("Programs"))

    # 确定目标可执行体：优先指向打包后的 exe，若未打包则指向静默 vbs 引导器
    if EXE_LAUNCHER.exists():
        target_path = str(EXE_LAUNCHER)
        arguments = ""
    else:
        target_path = "wscript.exe"
        arguments = f'"{VBS_LAUNCHER}"'

    shortcut_name = "苍穹量枢 · Aether Quant Studio.lnk"
    destinations = [desktop_dir / shortcut_name, programs_dir / shortcut_name]

    for link_path in destinations:
        try:
            shortcut = shell.CreateShortCut(str(link_path))
            shortcut.TargetPath = target_path
            if arguments:
                shortcut.Arguments = arguments
            shortcut.WorkingDirectory = str(ROOT)
            shortcut.Description = "Aether Quant Studio 苍穹量枢 · 币安合约多策略量化智能终端"
            if ICON_ICO.exists():
                shortcut.IconLocation = f"{ICON_ICO},0"
            shortcut.Save()
            print(f"[OK] 成功创建快捷方式: {link_path}")
        except Exception as err:
            print(f"[ERROR] 创建快捷方式失败 {link_path}: {err}")


if __name__ == "__main__":
    create_shortcuts()
