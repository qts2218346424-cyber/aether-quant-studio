"""Binance Futures Trading System - Desktop Control Center
Modern PyQt5-based System Tray with Mini Control Panel, One-Click Start/Stop,
Real-time Health Monitoring, and Global Shortcuts.
"""

from __future__ import annotations

import os
import sys
import time
import socket
import webbrowser
import threading
import subprocess
from pathlib import Path

import psutil
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt5.QtGui import QIcon, QFont, QCursor, QColor, QPixmap, QPainter, QPolygonF
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QCheckBox,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QGraphicsDropShadowEffect,
)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
APP_SCRIPT = ROOT / "app.py"
DASHBOARD_URL = "http://127.0.0.1:8800/"
PORT = 8800

STARTUP_VBS = (
    Path(os.environ.get("APPDATA", ""))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
    / "BinanceTradingDashboard.vbs"
)


def create_dynamic_icon(running: bool) -> QIcon:
    """Generate crisp vector tray icon in memory using QPainter."""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)

    # Rounded background
    bg_color = QColor(240, 185, 11) if running else QColor(75, 85, 99)
    p.setBrush(QtGui.QBrush(bg_color))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QtCore.QRectF(2, 2, 60, 60), 14, 14)

    # Center diamond
    center = 32.0
    fg_color = QColor(18, 22, 28) if running else QColor(229, 231, 235)
    p.setBrush(QtGui.QBrush(fg_color))

    d = 13.0
    poly = QtGui.QPolygonF([
        QPoint(int(center), int(center - d)),
        QPoint(int(center + d), int(center)),
        QPoint(int(center), int(center + d)),
        QPoint(int(center - d), int(center)),
    ])
    p.drawPolygon(poly)

    # Inner cut
    p.setBrush(QtGui.QBrush(bg_color))
    s = 5.5
    poly_in = QtGui.QPolygonF([
        QPoint(int(center), int(center - s)),
        QPoint(int(center + s), int(center)),
        QPoint(int(center), int(center + s)),
        QPoint(int(center - s), int(center)),
    ])
    p.drawPolygon(poly_in)

    # Status badge (bottom-right circle)
    badge_color = QColor(34, 197, 94) if running else QColor(239, 68, 68)
    p.setBrush(QtGui.QBrush(QColor(15, 23, 42)))
    p.drawEllipse(QtCore.QRectF(38, 38, 24, 24))
    p.setBrush(QtGui.QBrush(badge_color))
    p.drawEllipse(QtCore.QRectF(41, 41, 18, 18))

    p.end()
    return QIcon(pixmap)


def is_port_in_use(port: int = PORT) -> bool:
    """Check if port 8800 is listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.12)
        return s.connect_ex(("127.0.0.1", port)) == 0


def get_app_process():
    """Find running app.py python process strictly."""
    current_pid = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.pid == current_pid:
                continue
            name = (proc.info.get("name") or "").lower()
            if name not in ("python.exe", "pythonw.exe"):
                continue
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if "tray_app.py" in cmdline:
                continue
            if "app.py" in cmdline:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def stop_trading_service():
    """Kill trading service and free port 8800."""
    current_pid = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.pid == current_pid:
                continue
            cmdline = " ".join(proc.info.get("cmdline") or [])
            name = proc.info.get("name", "").lower()
            if "python" in name:
                if "app.py" in cmdline or "server_supervisor.py" in cmdline:
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Ensure port 8800 is completely released
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == PORT:
                if conn.pid and conn.pid != current_pid:
                    p = psutil.Process(conn.pid)
                    p.kill()
    except Exception:
        pass


def start_trading_service():
    """Start app.py as hidden background process."""
    if is_port_in_use():
        return

    python_exe = Path(sys.executable)
    console_exe = python_exe.with_name("python.exe")
    exe = str(console_exe if console_exe.exists() else python_exe)

    subprocess.Popen(
        [exe, "-u", str(APP_SCRIPT)],
        cwd=str(ROOT),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def is_startup_enabled() -> bool:
    return STARTUP_VBS.exists()


def set_startup_enabled(enabled: bool):
    try:
        if enabled:
            STARTUP_VBS.parent.mkdir(parents=True, exist_ok=True)
            pythonw = "C:\\Program Files\\Python311\\pythonw.exe"
            script = str(ROOT / "tray_app.py")
            content = f'Set ws = CreateObject("WScript.Shell")\nws.Run "powershell -WindowStyle Hidden -NoProfile -Command ""Start-Process -FilePath \'{pythonw}\' -ArgumentList \'tray_app.py\' -WorkingDirectory \'{ROOT}\'""", 0, False\n'
            STARTUP_VBS.write_text(content, encoding="utf-16")
        else:
            if STARTUP_VBS.exists():
                STARTUP_VBS.unlink(missing_ok=True)
    except Exception as e:
        print(f"Error updating startup: {e}")


# ==================== Mini Control Window ====================

class MiniControlPanel(QWidget):
    def __init__(self, tray_manager):
        super().__init__()
        self.tray = tray_manager
        self.setWindowTitle("币安合约量化控制中心")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.init_ui()

    def init_ui(self):
        self.setFixedSize(340, 420)

        # Outer Container
        container = QFrame(self)
        container.setGeometry(10, 10, 320, 400)
        container.setObjectName("container")

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 4)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 1. Header
        header = QHBoxLayout()
        header.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("🪙 币安合约量化控制中心")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #F0B90B;")
        
        self.lbl_subtitle = QLabel("本地桌面控制中心 · 端口 8800")
        self.lbl_subtitle.setStyleSheet("font-size: 10px; color: #94A3B8;")
        title_col.addWidget(lbl_title)
        title_col.addWidget(self.lbl_subtitle)
        header.addLayout(title_col)

        header.addStretch()

        btn_min = QPushButton("✕")
        btn_min.setFixedSize(26, 26)
        btn_min.setCursor(Qt.PointingHandCursor)
        btn_min.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 13px;
                color: #94A3B8;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #EF4444;
                color: #FFFFFF;
            }
        """)
        btn_min.clicked.connect(self.hide)
        header.addWidget(btn_min)
        layout.addLayout(header)

        # 2. Status Badge Card
        self.status_card = QFrame()
        self.status_card.setObjectName("statusCard")
        status_layout = QHBoxLayout(self.status_card)
        status_layout.setContentsMargins(12, 10, 12, 10)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("font-size: 14px; color: #22C55E;")
        status_layout.addWidget(self.status_dot)

        self.status_text = QLabel("正在检测服务状态...")
        self.status_text.setStyleSheet("font-size: 12px; font-weight: 600; color: #F8FAFC;")
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()

        self.port_badge = QLabel("127.0.0.1:8800")
        self.port_badge.setStyleSheet("""
            font-size: 10px;
            color: #64748B;
            background: rgba(255, 255, 255, 0.05);
            padding: 3px 6px;
            border-radius: 4px;
        """)
        status_layout.addWidget(self.port_badge)
        layout.addWidget(self.status_card)

        # 3. Main Action Buttons
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(8)

        # Start Button
        self.btn_start = QPushButton("▶  启动交易服务")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self.on_start_clicked)
        actions_layout.addWidget(self.btn_start)

        # Stop Button
        self.btn_stop = QPushButton("⏹  停止交易服务")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self.on_stop_clicked)
        actions_layout.addWidget(self.btn_stop)

        # Secondary row (Restart & Open Web)
        sec_layout = QHBoxLayout()
        sec_layout.setSpacing(8)

        self.btn_restart = QPushButton("🔄 重启服务")
        self.btn_restart.setObjectName("btnSecondary")
        self.btn_restart.setCursor(Qt.PointingHandCursor)
        self.btn_restart.clicked.connect(self.on_restart_clicked)
        sec_layout.addWidget(self.btn_restart)

        self.btn_open_web = QPushButton("🌐 打开交易面板")
        self.btn_open_web.setObjectName("btnPrimaryWeb")
        self.btn_open_web.setCursor(Qt.PointingHandCursor)
        self.btn_open_web.clicked.connect(self.on_open_web_clicked)
        sec_layout.addWidget(self.btn_open_web)

        actions_layout.addLayout(sec_layout)
        layout.addLayout(actions_layout)

        # 4. Settings & Shortcuts Info
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 6px;
            padding: 4px;
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(10, 6, 10, 6)
        info_layout.setSpacing(4)

        # Startup checkbox
        self.chk_startup = QCheckBox("开机自动常驻右下角")
        self.chk_startup.setChecked(is_startup_enabled())
        self.chk_startup.setStyleSheet("""
            QCheckBox {
                color: #94A3B8;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #475569;
                background: #1E293B;
            }
            QCheckBox::indicator:checked {
                background: #F0B90B;
                border-color: #F0B90B;
            }
        """)
        self.chk_startup.toggled.connect(set_startup_enabled)
        info_layout.addWidget(self.chk_startup)

        lbl_shortcut = QLabel("快捷键: Ctrl+Alt+S (开关) · Ctrl+Alt+B (打开)")
        lbl_shortcut.setStyleSheet("color: #64748B; font-size: 10px;")
        info_layout.addWidget(lbl_shortcut)

        layout.addWidget(info_frame)

        # 5. Bottom row: Exit Tray
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        btn_exit = QPushButton("❌ 彻底退出全部程序 (Exit)")
        btn_exit.setCursor(Qt.PointingHandCursor)
        btn_exit.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #EF4444;
                font-size: 11px;
                text-decoration: underline;
                padding: 4px;
            }
            QPushButton:hover {
                color: #F87171;
            }
        """)
        btn_exit.clicked.connect(self.tray.exit_application)
        bottom_layout.addWidget(btn_exit)
        layout.addLayout(bottom_layout)

        # Global stylesheet
        self.setStyleSheet("""
            #container {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #181E29, stop:1 #0F131C);
                border: 1px solid rgba(240, 185, 11, 0.35);
                border-radius: 14px;
            }
            #statusCard {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
            QPushButton#btnStart {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
                padding: 9px;
            }
            QPushButton#btnStart:hover {
                background: #34D399;
            }
            QPushButton#btnStart:disabled {
                background: rgba(255, 255, 255, 0.05);
                color: #475569;
            }
            QPushButton#btnStop {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #EF4444, stop:1 #DC2626);
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
                padding: 9px;
            }
            QPushButton#btnStop:hover {
                background: #F87171;
            }
            QPushButton#btnStop:disabled {
                background: rgba(255, 255, 255, 0.05);
                color: #475569;
            }
            QPushButton#btnSecondary {
                background: rgba(255, 255, 255, 0.08);
                color: #E2E8F0;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 7px;
            }
            QPushButton#btnSecondary:hover {
                background: rgba(255, 255, 255, 0.15);
                border-color: #94A3B8;
            }
            QPushButton#btnPrimaryWeb {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F0B90B, stop:1 #D97706);
                color: #0F172A;
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                padding: 7px;
            }
            QPushButton#btnPrimaryWeb:hover {
                background: #FBBF24;
            }
        """)

    def update_status(self, state: str):
        """State: 'RUNNING' | 'STARTING' | 'STOPPED'"""
        if state == "RUNNING":
            self.status_dot.setText("●")
            self.status_dot.setStyleSheet("font-size: 14px; color: #22C55E;")
            self.status_text.setText("服务运行中 (就绪)")
            self.status_text.setStyleSheet("font-size: 12px; font-weight: 600; color: #4ADE80;")
            self.btn_start.setEnabled(False)
            self.btn_start.setText("已在运行中")
            self.btn_stop.setEnabled(True)
            self.btn_stop.setText("⏹  停止交易服务")
            self.btn_restart.setEnabled(True)
        elif state == "STARTING":
            self.status_dot.setText("◐")
            self.status_dot.setStyleSheet("font-size: 14px; color: #F59E0B;")
            self.status_text.setText("正在拉起 (同步K线与行情)...")
            self.status_text.setStyleSheet("font-size: 11px; font-weight: 600; color: #FBBF24;")
            self.btn_start.setEnabled(False)
            self.btn_start.setText("启动中, 稍候...")
            self.btn_stop.setEnabled(True)
            self.btn_stop.setText("⏹  中断停止")
            self.btn_restart.setEnabled(False)
        else:
            self.status_dot.setText("○")
            self.status_dot.setStyleSheet("font-size: 14px; color: #EF4444;")
            self.status_text.setText("服务已停止")
            self.status_text.setStyleSheet("font-size: 12px; font-weight: 600; color: #F87171;")
            self.btn_start.setEnabled(True)
            self.btn_start.setText("▶  启动交易服务")
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("未在运行")
            self.btn_restart.setEnabled(False)

    def on_start_clicked(self):
        self.tray.start_service()

    def on_stop_clicked(self):
        self.status_text.setText("正在强制停止...")
        self.btn_stop.setEnabled(False)
        stop_trading_service()
        QTimer.singleShot(600, self.tray.check_service_state)

    def on_restart_clicked(self):
        self.update_status("STARTING")
        stop_trading_service()
        QTimer.singleShot(1000, start_trading_service)

    def on_open_web_clicked(self):
        webbrowser.open(DASHBOARD_URL)

    def reposition_near_tray(self):
        """Position the popup window near the bottom-right corner."""
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 15
        y = screen.bottom() - self.height() - 15
        self.move(x, y)


# ==================== System Tray Manager ====================

class TrayManager(QtCore.QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.current_state = "STOPPED"

        # Dynamic memory-rendered icons
        self.icon_running = create_dynamic_icon(True)
        self.icon_stopped = create_dynamic_icon(False)

        # Create system tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.icon_stopped)

        # Create Mini Control Panel
        self.panel = MiniControlPanel(self)

        # Create Context Menu
        self.create_menu()

        # Connect tray clicks
        self.tray_icon.activated.connect(self.on_tray_activated)

        # Explicitly show system tray icon
        self.tray_icon.show()

        # Setup periodic health check timer (every 300ms for instant feedback)
        self.starting_deadline = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_service_state)
        self.timer.start(300)

        # Setup global hotkeys
        self.setup_hotkeys()

        # Initial check
        self.check_service_state()

        # Auto-pop the control panel on startup so the user immediately sees it
        QTimer.singleShot(400, self.show_panel)

    def create_menu(self):
        self.menu = QMenu()
        self.menu.setStyleSheet("""
            QMenu {
                background: #181E29;
                color: #F8FAFC;
                border: 1px solid rgba(240, 185, 11, 0.3);
                border-radius: 8px;
                padding: 6px;
                font-size: 12px;
            }
            QMenu::item {
                padding: 7px 22px 7px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: rgba(240, 185, 11, 0.18);
                color: #F0B90B;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255, 255, 255, 0.08);
                margin: 4px 6px;
            }
        """)

        # Status item
        self.act_status = QAction("🟢 服务状态: 检查中...", self.menu)
        self.act_status.setEnabled(False)
        self.menu.addAction(self.act_status)

        self.menu.addSeparator()

        # Show Control Panel
        self.act_panel = QAction("⚡ 呼出控制中心卡片", self.menu)
        self.act_panel.triggered.connect(self.show_panel)
        self.menu.addAction(self.act_panel)

        # Open Web Dashboard
        self.act_open = QAction("🌐 打开交易面板 (Ctrl+Alt+B)", self.menu)
        self.act_open.triggered.connect(lambda: webbrowser.open(DASHBOARD_URL))
        self.menu.addAction(self.act_open)

        self.menu.addSeparator()

        # Start Service
        self.act_start = QAction("▶️ 启动交易服务", self.menu)
        self.act_start.triggered.connect(self.start_service)
        self.menu.addAction(self.act_start)

        # Stop Service
        self.act_stop = QAction("⏹️ 停止交易服务", self.menu)
        self.act_stop.triggered.connect(self.stop_service)
        self.menu.addAction(self.act_stop)

        # Restart Service
        self.act_restart = QAction("🔄 重启交易服务", self.menu)
        self.act_restart.triggered.connect(self.restart_service)
        self.menu.addAction(self.act_restart)

        self.menu.addSeparator()

        # Exit application
        self.act_exit = QAction("❌ 退出控制中心 (Exit)", self.menu)
        self.act_exit.triggered.connect(self.exit_application)
        self.menu.addAction(self.act_exit)

        self.tray_icon.setContextMenu(self.menu)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # Single left-click
            self.toggle_panel()
        elif reason == QSystemTrayIcon.DoubleClick:  # Double click
            webbrowser.open(DASHBOARD_URL)

    def show_panel(self):
        self.panel.reposition_near_tray()
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def toggle_panel(self):
        if self.panel.isVisible():
            self.panel.hide()
        else:
            self.show_panel()

    def check_service_state(self):
        port_open = is_port_in_use()
        proc = get_app_process()

        if port_open:
            state = "RUNNING"
            self.starting_deadline = 0.0
        elif self.starting_deadline and time.time() < self.starting_deadline and proc:
            state = "STARTING"
        else:
            state = "STOPPED"
            self.starting_deadline = 0.0

        self.current_state = state
        self.panel.update_status(state)

        if state == "RUNNING":
            self.tray_icon.setIcon(self.icon_running)
            self.tray_icon.setToolTip("币安合约交易机器人 - 🟢 运行中 (8800)")
            self.act_status.setText("🟢 状态: 运行中 (127.0.0.1:8800)")
            self.act_start.setEnabled(False)
            self.act_stop.setEnabled(True)
            self.act_restart.setEnabled(True)
        elif state == "STARTING":
            self.tray_icon.setIcon(self.icon_stopped)
            self.tray_icon.setToolTip("币安合约交易机器人 - 🟡 正在启动中...")
            self.act_status.setText("🟡 状态: 正在拉起服务...")
            self.act_start.setEnabled(False)
            self.act_stop.setEnabled(True)
            self.act_restart.setEnabled(False)
        else:
            self.tray_icon.setIcon(self.icon_stopped)
            self.tray_icon.setToolTip("币安合约交易机器人 - 🔴 已停止")
            self.act_status.setText("🔴 状态: 已停止")
            self.act_start.setEnabled(True)
            self.act_stop.setEnabled(False)
            self.act_restart.setEnabled(False)

    def start_service(self):
        self.starting_deadline = time.time() + 8.0
        self.panel.update_status("STARTING")
        start_trading_service()

    def stop_service(self):
        stop_trading_service()
        QTimer.singleShot(600, self.check_service_state)

    def restart_service(self):
        self.panel.update_status("STARTING")
        stop_trading_service()
        QTimer.singleShot(1000, start_trading_service)

    def toggle_service(self):
        if self.current_state in ("RUNNING", "STARTING"):
            self.stop_service()
        else:
            self.start_service()

    def exit_application(self):
        """Stop everything and quit tray."""
        stop_trading_service()
        self.tray_icon.hide()
        self.app.quit()

    def setup_hotkeys(self):
        try:
            import keyboard
            keyboard.add_hotkey("ctrl+alt+s", lambda: self.toggle_service())
            keyboard.add_hotkey("ctrl+alt+b", lambda: webbrowser.open(DASHBOARD_URL))
            keyboard.add_hotkey("ctrl+alt+x", lambda: self.exit_application())
        except Exception as e:
            print(f"Global hotkey setup skipped: {e}")


def main():
    log_file = ROOT / "tray_debug.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n--- tray_app started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        with open(log_file, "a", encoding="utf-8") as f:
            f.write("QApplication initialized\n")

        manager = TrayManager(app)

        with open(log_file, "a", encoding="utf-8") as f:
            f.write("TrayManager initialized, entering app.exec_()\n")

        exit_code = app.exec_()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"app.exec_() returned exit_code={exit_code}\n")
        sys.exit(exit_code)
    except Exception as e:
        import traceback
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"FATAL EXCEPTION in main: {e}\n{traceback.format_exc()}\n")


if __name__ == "__main__":
    main()
