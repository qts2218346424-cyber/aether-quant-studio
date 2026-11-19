"""Aether Quant Studio · 本地开发环境与知识库自动探测引擎

负责自动发现本机：
1. 本地 Antigravity / antigravity-tools OpenAI 兼容网关 (默认 127.0.0.1:8045) 与 agy CLI
2. 电脑本地已安装的 Obsidian 知识库列表 (读取官方 obsidian.json 与标准文档目录)
3. 系统网络代理与币安 API 密钥就绪状态

设计目标：零硬编码个人路径，支持任意开发者克隆后开箱自动识别与复刻。
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import load_config

CANDIDATE_GATEWAY_PORTS = [8045, 8080, 3000, 11434]


def _check_tcp_port(host: str, port: int, timeout: float = 0.25) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def probe_local_antigravity(custom_url: Optional[str] = None) -> Dict[str, Any]:
    """探测本地 Antigravity 网关、模型列表与 agy CLI 状态"""
    agy_cli = shutil.which("agy")
    if not agy_cli:
        win_agy = Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe"
        if win_agy.exists():
            agy_cli = str(win_agy)

    candidate_urls: List[str] = []
    if custom_url:
        clean = custom_url.strip().rstrip("/")
        if clean:
            candidate_urls.append(clean if clean.endswith("/v1") else f"{clean}/v1")

    for port in CANDIDATE_GATEWAY_PORTS:
        url = f"http://127.0.0.1:{port}/v1"
        if url not in candidate_urls:
            candidate_urls.append(url)

    detected_url: Optional[str] = None
    models: List[str] = []
    gateway_online = False

    for base_v1 in candidate_urls:
        try:
            # 先快速检测端口连通，避免无效 HTTP 超时阻塞
            host_port = base_v1.split("://", 1)[-1].split("/", 1)[0]
            if ":" in host_port:
                host, port_str = host_port.split(":", 1)
                if not _check_tcp_port(host, int(port_str), timeout=0.2):
                    continue

            req = urllib.request.Request(
                f"{base_v1}/models",
                headers={"User-Agent": "AetherQuant/2.1"},
            )
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    data_list = payload.get("data", []) if isinstance(payload, dict) else []
                    models = [
                        str(item.get("id"))
                        for item in data_list
                        if isinstance(item, dict) and item.get("id")
                    ]
                    detected_url = base_v1
                    gateway_online = True
                    break
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            # 即使 /models 需要鉴权返回 401，也说明网关是活的
            continue

    # 如果 /models 未直接返回 200，但 8045 端口处于监听状态，仍标记网关在线
    if not gateway_online and _check_tcp_port("127.0.0.1", 8045, timeout=0.2):
        gateway_online = True
        detected_url = "http://127.0.0.1:8045/v1"

    return {
        "gateway_online": gateway_online,
        "gateway_url": detected_url or "http://127.0.0.1:8045/v1",
        "models": models[:30],
        "agy_cli_available": bool(agy_cli),
        "agy_cli_path": agy_cli or "",
    }


def detect_obsidian_vaults() -> Dict[str, Any]:
    """扫描电脑本地的 Obsidian 知识库列表"""
    vaults: List[Dict[str, Any]] = []
    seen_paths: set[str] = set()

    def _add_vault(path_obj: Path, is_open: bool = False, source: str = "obsidian.json"):
        try:
            resolved = path_obj.expanduser().resolve()
            key = str(resolved).lower()
            if key in seen_paths or not resolved.exists() or not resolved.is_dir():
                return
            seen_paths.add(key)
            has_templates = (resolved / "01-交易策略").exists() and (resolved / "02-交易复盘").exists()
            vaults.append(
                {
                    "name": resolved.name or str(resolved),
                    "path": str(resolved),
                    "is_open": is_open,
                    "has_templates": has_templates,
                    "source": source,
                }
            )
        except Exception:
            pass

    # 1. 读取 Obsidian 官方配置文件
    obs_json_candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        obs_json_candidates.append(Path(appdata) / "obsidian" / "obsidian.json")
    obs_json_candidates.append(Path.home() / ".config" / "obsidian" / "obsidian.json")
    obs_json_candidates.append(Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json")

    for obs_json in obs_json_candidates:
        if obs_json.exists():
            try:
                data = json.loads(obs_json.read_text(encoding="utf-8"))
                for v in (data.get("vaults") or {}).values():
                    if isinstance(v, dict) and v.get("path"):
                        _add_vault(Path(v["path"]), is_open=bool(v.get("open")), source="obsidian")
            except Exception:
                pass

    # 2. 扫描常见标准文档目录
    home = Path.home()
    for cand in (
        home / "Documents" / "Obsidian Vault",
        home / "Documents" / "交易知识库",
        home / "Obsidian",
        home / "OneDrive" / "Obsidian",
    ):
        _add_vault(cand, is_open=False, source="scan")

    # 优先把当前打开的仓库排在前面
    vaults.sort(key=lambda item: (not item["is_open"], not item["has_templates"], item["name"]))

    cfg = load_config()
    configured_path = str((cfg.get("obsidian") or {}).get("vault_path") or "").strip()

    return {
        "configured_path": configured_path,
        "auto_sync": bool((cfg.get("obsidian") or {}).get("auto_sync", True)),
        "vaults": vaults,
    }


def detect_full_environment() -> Dict[str, Any]:
    """返回完整本地环境自动检测报告"""
    cfg = load_config()
    ai_routing = cfg.get("ai_routing") or {}
    local_cfg = ai_routing.get("local_antigravity") or {}

    ag_info = probe_local_antigravity(local_cfg.get("base_url"))
    obs_info = detect_obsidian_vaults()

    return {
        "antigravity": ag_info,
        "ai_routing": {
            "mode": ai_routing.get("mode", "local_first"),
            "local_antigravity": {
                "enabled": bool(local_cfg.get("enabled", True)),
                "base_url": local_cfg.get("base_url") or ag_info["gateway_url"],
                "api_key": "***" if local_cfg.get("api_key") else "",
                "model": local_cfg.get("model") or (ag_info["models"][0] if ag_info["models"] else "gemini-2.5-flash"),
            },
        },
        "obsidian": obs_info,
        "proxy": cfg.get("proxy") or "",
    }
