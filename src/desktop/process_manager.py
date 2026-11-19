"""Aether Quant Studio · 后台核心量化引擎生命周期管理器

负责 FastAPI 服务进程的静默拉起、健康状态探测、优雅退出与强制端口清理。
"""

from __future__ import annotations

import os
import sys
import time
import socket
import subprocess
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error

import psutil

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parents[2]
APP_PY = ROOT / "app.py"
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SERVER_LOG = LOGS_DIR / "server-8800.log"
PORT = 8800
BASE_URL = f"http://127.0.0.1:{PORT}"


class BackendProcessManager:
    """管理后台量化核心服务的启动、停止与状态监测"""

    def __init__(self, port: int = PORT):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self._proc: Optional[subprocess.Popen] = None

    def is_port_listening(self) -> bool:
        """检查指定端口是否处于监听状态"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            return sock.connect_ex(("127.0.0.1", self.port)) == 0

    def is_healthy(self) -> bool:
        """HTTP GET 探测后台服务是否可响应"""
        if not self.is_port_listening():
            return False
        try:
            req = urllib.request.Request(
                self.base_url + "/",
                headers={"User-Agent": "AetherDesktop/2.0"},
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status in (200, 301, 302, 404)
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def get_python_exe(self) -> str:
        """获取用于启动后端的 Python 解释器路径"""
        import shutil
        exe = Path(sys.executable)
        if not getattr(sys, "frozen", False):
            console_exe = exe.with_name("python.exe")
            if console_exe.exists():
                return str(console_exe)
            if exe.name.lower() in ("python.exe", "pythonw.exe"):
                return str(exe)

        # 打包后的 exe 环境：查找真实可用的 python.exe（排除 WindowsApps 商店占位符）
        for candidate in [
            r"C:\Program Files\Python311\python.exe",
            r"C:\Program Files\Python312\python.exe",
            r"C:\Program Files\Python310\python.exe",
        ]:
            if Path(candidate).exists():
                return candidate

        which_py = shutil.which("python")
        if which_py and "WindowsApps" not in which_py:
            return which_py
        return "python"

    def start(self) -> bool:
        """在后台静默启动 app.py 服务"""
        if self.is_port_listening():
            return True

        python_bin = self.get_python_exe()
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        # 清理 PyInstaller 注入的环境变量，防止子进程 Python 冲突
        env = os.environ.copy()
        for key in ("_MEIPASS2", "PYTHONHOME", "PYTHONPATH"):
            env.pop(key, None)

        # 启动后端进程，输出重定向到日志文件
        log_fh = SERVER_LOG.open("a", encoding="utf-8", buffering=1)
        log_fh.write(f"\n--- [Desktop App] 启动量化服务 {time.strftime('%Y-%m-%d %H:%M:%S')} (python={python_bin}) ---\n")
        log_fh.flush()

        try:
            self._proc = subprocess.Popen(
                [python_bin, "-u", str(APP_PY)],
                cwd=str(ROOT),
                env=env,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            return True
        except Exception as err:
            log_fh.write(f"[ERROR] 无法启动后台进程: {err}\n")
            log_fh.flush()
            return False

    def wait_ready(self, timeout: float = 12.0) -> bool:
        """阻塞轮询直到后端完全就绪或超时"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_healthy():
                return True
            time.sleep(0.3)
        return False

    def stop(self) -> None:
        """安全停止后台量化服务并彻底释放端口"""
        current_pid = os.getpid()

        # 1. 尝试终止自启动的子进程句柄
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1.5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        # 2. 扫描系统中运行 app.py 的残留 Python 进程
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.pid == current_pid:
                    continue
                name = (proc.info.get("name") or "").lower()
                if "python" in name:
                    cmdline = " ".join(proc.info.get("cmdline") or [])
                    if "app.py" in cmdline or "server_supervisor.py" in cmdline:
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 3. 释放端口 8800 上的任何连接
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr and conn.laddr.port == self.port:
                    if conn.pid and conn.pid != current_pid:
                        try:
                            p = psutil.Process(conn.pid)
                            p.kill()
                        except Exception:
                            pass
        except Exception:
            pass

    def restart(self) -> bool:
        """重启后台服务"""
        self.stop()
        time.sleep(1.0)
        started = self.start()
        if started:
            return self.wait_ready(timeout=12.0)
        return False


backend_manager = BackendProcessManager()
