"""Aether Quant Studio · 苍穹量枢 — 原生桌面客户端主程序

一键启动独立桌面 App，自动托管 FastAPI 后台量化引擎，集成系统托盘常驻、
关闭最小化、健康监控与沉浸式暗黑交易终端。
"""

from __future__ import annotations

import msvcrt
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

import webview

# 确保包路径加入 Python 搜索路径
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.desktop.process_manager import backend_manager
from src.desktop.splash_html import SPLASH_HTML
from src.desktop.tray_controller import SystemTrayController

LOCK_FILE = ROOT / "logs" / "desktop_app.lock"
DASHBOARD_URL = "http://127.0.0.1:8800/"
APP_TITLE = "Aether Quant Studio · 苍穹量枢"
ICON_PATH = str(ROOT / "static" / "icons" / "app_icon.ico")


class AetherDesktopApp:
    """桌面客户端主控制器"""

    def __init__(self):
        self.window: Optional[webview.Window] = None
        self.tray: Optional[SystemTrayController] = None
        self.is_quitting: bool = False
        self._lock_handle = None

    def acquire_single_instance(self) -> bool:
        """获取单实例文件排他锁，防止重复多开"""
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._lock_handle = LOCK_FILE.open("w+")
        try:
            msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            # 已有实例在运行
            return False

    def on_window_closing(self) -> bool:
        """拦截窗口关闭按钮：若非主动彻底退出，则默认最小化至系统托盘"""
        if self.is_quitting:
            return True  # 允许窗口销毁

        # 最小化隐藏窗口
        if self.window:
            self.window.hide()

        # 发送系统气泡通知
        if self.tray:
            self.tray.notify(
                "苍穹量枢 正在后台运行",
                "已最小化至系统托盘。量化策略与持仓监控持续工作中，双击托盘图标可重新呼出面板。"
            )
        return False  # 阻止销毁

    def show_window(self) -> None:
        """从托盘激活并显示窗口"""
        if self.window:
            self.window.show()

    def restart_backend(self) -> None:
        """重启后台服务并重新加载窗口内容"""
        backend_manager.restart()
        if self.window:
            self.window.load_url(DASHBOARD_URL)

    def quit_application(self) -> None:
        """彻底安全退出整个桌面 App 与后台交易引擎"""
        self.is_quitting = True

        # 1. 停止托盘
        if self.tray:
            self.tray.stop()

        # 2. 终止后台量化引擎
        backend_manager.stop()

        # 3. 销毁桌面窗口
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass

        # 4. 释放文件锁
        if self._lock_handle:
            try:
                msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                self._lock_handle.close()
            except Exception:
                pass

        sys.exit(0)

    def run_fallback_app_mode(self) -> None:
        """降级方案：调用原生 Edge/Chrome 的独立 App 窗口模式"""
        # 启动后台引擎
        backend_manager.start()
        backend_manager.wait_ready(timeout=10.0)

        # 启动托盘
        self.tray = SystemTrayController(
            on_show_window=lambda: webbrowser.open(DASHBOARD_URL),
            on_restart_backend=backend_manager.restart,
            on_exit_app=self.quit_application,
        )
        self.tray.start()

        # 调起 Edge App 窗口
        edge_cmd = f'start msedge --app="{DASHBOARD_URL}" --window-size=1440,900'
        subprocess.Popen(edge_cmd, shell=True)

        # 保持主线程运行
        try:
            while not self.is_quitting:
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.quit_application()

    def _log(self, msg: str) -> None:
        log_path = ROOT / "logs" / "desktop_app.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as lf:
            lf.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _wait_and_navigate(self, window: webview.Window) -> None:
        """在后台线程等待 FastAPI 就绪后直接导航至主面板（避免前端 CORS 限制）"""
        if backend_manager.is_healthy():
            return
        self._log("开始在 Python 侧探测后台服务就绪状态...")
        ready = backend_manager.wait_ready(timeout=20.0)
        self._log(f"后台服务就绪状态: {ready}")
        if ready and not self.is_quitting:
            self._log(f"执行 window.load_url({DASHBOARD_URL})")
            window.load_url(DASHBOARD_URL)
        elif not self.is_quitting:
            self._log("后台服务等待超时，强制尝试跳转并提示")
            window.load_url(DASHBOARD_URL)

    def run(self) -> None:
        """运行客户端应用"""
        self._log("进入 run()")
        if not self.acquire_single_instance():
            self._log("单实例锁获取失败，已有实例在运行")
            webbrowser.open(DASHBOARD_URL)
            sys.exit(0)

        # 1. 静默拉起后台交易引擎
        self._log("准备启动后台引擎")
        ok = backend_manager.start()
        self._log(f"后台引擎启动调用结果: {ok}")

        # 2. 启动系统托盘控制器
        self.tray = SystemTrayController(
            on_show_window=self.show_window,
            on_restart_backend=self.restart_backend,
            on_exit_app=self.quit_application,
        )
        self.tray.start()
        self._log("托盘控制器已启动")

        # 3. 创建主桌面窗口
        initial_url = DASHBOARD_URL if backend_manager.is_healthy() else None
        initial_html = None if initial_url else SPLASH_HTML
        self._log(f"创建桌面窗口 initial_url={initial_url}")

        try:
            self.window = webview.create_window(
                title=APP_TITLE,
                url=initial_url,
                html=initial_html,
                width=1360,
                height=860,
                min_size=(900, 620),
                maximized=True,
                background_color="#0b0e14",
                text_select=True,
                confirm_close=False,
            )

            # 绑定关闭事件拦截
            self.window.events.closing += self.on_window_closing

            # 启动 WebView 消息泵（阻塞主线程）
            self._log("调用 webview.start()")
            nav_func = None if initial_url else self._wait_and_navigate
            nav_args = (self.window,) if nav_func else ()
            webview.start(
                func=nav_func,
                args=nav_args,
                icon=ICON_PATH if Path(ICON_PATH).exists() else None,
            )
            self._log("webview.start() 正常结束，准备退出")

            # 当 WebView 主循环正常退出后，清理退出
            self.quit_application()

        except Exception as err:
            import traceback
            self._log(f"WebView2 窗口异常，切换至独立 App 模式: {err}\n{traceback.format_exc()}")
            self.run_fallback_app_mode()


def main():
    log_path = ROOT / "logs" / "desktop_app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("a", encoding="utf-8") as lf:
            lf.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 启动桌面客户端 (ROOT={ROOT}, frozen={getattr(sys, 'frozen', False)})\n")
        app = AetherDesktopApp()
        app.run()
    except Exception as exc:
        import traceback
        with log_path.open("a", encoding="utf-8") as lf:
            lf.write(f"[CRASH] {exc}\n{traceback.format_exc()}\n")


if __name__ == "__main__":
    main()
