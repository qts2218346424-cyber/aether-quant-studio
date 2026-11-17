"""Keep the local trading dashboard on port 8800 alive.

The trading process still starts with auto_trade=False. This supervisor only
restores the web service and does not enable automatic trading.
"""

from __future__ import annotations

import datetime as dt
import msvcrt
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
APP = ROOT / "app.py"
PORT = 8800
LOCK_FILE = LOGS_DIR / "server-supervisor.lock"
SUPERVISOR_LOG = LOGS_DIR / "server-supervisor.log"
SERVER_LOG = LOGS_DIR / "server-8800.log"


def log(message: str) -> None:
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {message}\n"
    with SUPERVISOR_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)


def port_is_open() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", PORT)) == 0


def acquire_single_instance_lock():
    LOCK_FILE.touch(exist_ok=True)
    handle = LOCK_FILE.open("r+b")
    if LOCK_FILE.stat().st_size == 0:
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def python_executable() -> str:
    exe = Path(sys.executable)
    console_python = exe.with_name("python.exe")
    return str(console_python if console_python.exists() else exe)


def main() -> int:
    lock_handle = acquire_single_instance_lock()
    if lock_handle is None:
        return 0

    log(f"supervisor started pid={os.getpid()} port={PORT}")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    while True:
        if port_is_open():
            time.sleep(5)
            continue

        log("port 8800 is down; starting app.py")
        with SERVER_LOG.open("ab", buffering=0) as server_log:
            process = subprocess.Popen(
                [python_executable(), "-u", str(APP)],
                cwd=str(ROOT),
                stdout=server_log,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            log(f"app.py started pid={process.pid}")
            exit_code = process.wait()
            log(f"app.py exited code={exit_code}; restart in 3 seconds")
        time.sleep(3)


if __name__ == "__main__":
    raise SystemExit(main())
