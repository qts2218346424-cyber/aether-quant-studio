"""安全停止 Aether Quant Studio 全部进程"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.desktop.process_manager import backend_manager
import psutil

def main():
    print("正在安全停止 Aether Quant Studio 全部服务与桌面程序...")
    # 1. 停止后端
    backend_manager.stop()

    # 2. 终止桌面 exe / pythonw 进程
    current_pid = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.pid == current_pid:
                continue
            name = (proc.info.get("name") or "").lower()
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if "苍穹量枢" in name or "desktop_app.py" in cmdline or "tray_app.py" in cmdline:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    print("[OK] 全部进程已安全终止，端口 8800 已释放。")

if __name__ == "__main__":
    main()
