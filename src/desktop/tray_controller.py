"""Aether Quant Studio · 系统托盘控制器

负责在 Windows 任务栏右下角常驻金色币安量化图标，提供状态监控、唤出主窗口、浏览器直通与安全退出等控制。
"""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable, Optional

from PIL import Image
import pystray

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parents[2]
ICON_PNG = ROOT / "static" / "icons" / "app_icon.png"
DASHBOARD_URL = "http://127.0.0.1:8800/"

STARTUP_VBS = (
    Path(os.environ.get("APPDATA", ""))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
    / "AetherQuantStudio.vbs"
)


class SystemTrayController:
    """管理系统托盘图标、菜单交互与通知提示"""

    def __init__(
        self,
        on_show_window: Optional[Callable[[], None]] = None,
        on_restart_backend: Optional[Callable[[], None]] = None,
        on_exit_app: Optional[Callable[[], None]] = None,
    ):
        self.on_show_window = on_show_window
        self.on_restart_backend = on_restart_backend
        self.on_exit_app = on_exit_app
        self._icon: Optional[pystray.Icon] = None
        self._is_running = False

    def is_startup_enabled(self) -> bool:
        """检查开机自启是否已配置"""
        return STARTUP_VBS.exists()

    def toggle_startup(self, icon=None, item=None) -> None:
        """切换开机自启动"""
        try:
            if self.is_startup_enabled():
                STARTUP_VBS.unlink(missing_ok=True)
                self.notify("苍穹量枢", "已关闭开机自启功能")
            else:
                STARTUP_VBS.parent.mkdir(parents=True, exist_ok=True)
                vbs_launcher = ROOT / "启动苍穹量枢.vbs"
                content = (
                    f'Set ws = CreateObject("WScript.Shell")\n'
                    f'ws.Run "wscript.exe ""{vbs_launcher}""", 0, False\n'
                )
                STARTUP_VBS.write_text(content, encoding="utf-16")
                self.notify("苍穹量枢", "已成功设置开机常驻自启")
        except Exception as err:
            self.notify("苍穹量枢", f"设置开机自启失败: {err}")

    def notify(self, title: str, message: str) -> None:
        """向 Windows 发送右下角气泡通知"""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass

    def _create_menu(self) -> pystray.Menu:
        """构建现代系统托盘右键菜单"""
        return pystray.Menu(
            pystray.MenuItem(
                "⚡ 唤出客户端主窗口",
                lambda icon, item: self._handle_show_window(),
                default=True,  # 双击托盘默认激活
            ),
            pystray.MenuItem(
                "🌐 在浏览器中打开 (8800)",
                lambda icon, item: webbrowser.open(DASHBOARD_URL),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "🔄 重启量化核心引擎",
                lambda icon, item: self._handle_restart(),
            ),
            pystray.MenuItem(
                "📌 开机自动常驻后台",
                self.toggle_startup,
                checked=lambda item: self.is_startup_enabled(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "❌ 彻底退出苍穹量枢 (Exit)",
                lambda icon, item: self._handle_exit(),
            ),
        )

    def _handle_show_window(self) -> None:
        if self.on_show_window:
            self.on_show_window()

    def _handle_restart(self) -> None:
        self.notify("苍穹量枢", "正在重启量化引擎...")
        if self.on_restart_backend:
            self.on_restart_backend()
        self.notify("苍穹量枢", "量化核心引擎重启就绪")

    def _handle_exit(self) -> None:
        self.stop()
        if self.on_exit_app:
            self.on_exit_app()

    def start(self) -> None:
        """启动后台常驻托盘线程"""
        if self._is_running:
            return

        try:
            pil_image = Image.open(str(ICON_PNG)).resize((64, 64), Image.Resampling.LANCZOS)
        except Exception:
            pil_image = Image.new("RGBA", (64, 64), (240, 185, 11, 255))

        self._icon = pystray.Icon(
            name="AetherQuantStudio",
            icon=pil_image,
            title="Aether Quant Studio · 苍穹量枢 (运行中)",
            menu=self._create_menu(),
        )
        self._is_running = True

        def runner():
            try:
                self._icon.run()
            except Exception as err:
                print(f"[Tray] 托盘运行异常: {err}")
            finally:
                self._is_running = False

        thread = threading.Thread(target=runner, name="TrayThread", daemon=True)
        thread.start()

    def update_tooltip(self, text: str) -> None:
        """更新鼠标悬停提示文案"""
        if self._icon:
            self._icon.title = text

    def stop(self) -> None:
        """停止托盘图标"""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
        self._is_running = False
