"""Aether Quant Studio · 本地开发环境与知识库自动探测引擎

参照知识库项目 (obsidian-viz) local-agent-bridge 架构：
1. 自动探测本机 Antigravity 2.0 安装状态 (Antigravity.exe / agy CLI / ~/.gemini/antigravity)
   及本地 OpenAI 兼容反代网关 (127.0.0.1:8045 等) 实际可用性；
2. 自动扫描电脑本地已安装的 Obsidian 知识库列表 (读取官方 obsidian.json 与标准文档目录)；
3. 零硬编码个人路径，支持任意开发者克隆后开箱自动识别与复刻。
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
    """全维度探测本地 Antigravity 客户端、CLI、数据目录与反代网关真实可用性"""
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    user_home = Path.home()

    # 1. 探测本地 Antigravity.exe
    ag_exe_path = ""
    if local_appdata:
        cand_exe = Path(local_appdata) / "Programs" / "antigravity" / "Antigravity.exe"
        if cand_exe.exists():
            ag_exe_path = str(cand_exe)

    # 2. 探测 agy CLI
    agy_cli = shutil.which("agy") or ""
    if not agy_cli and local_appdata:
        win_agy = Path(local_appdata) / "agy" / "bin" / "agy.exe"
        if win_agy.exists():
            agy_cli = str(win_agy)
    if not agy_cli and appdata:
        npm_agy = Path(appdata) / "npm" / "agy.cmd"
        if npm_agy.exists():
            agy_cli = str(npm_agy)

    # 3. 探测 ~/.gemini/antigravity 工作区目录
    gemini_dir = user_home / ".gemini" / "antigravity"
    data_dir_exists = gemini_dir.exists() and gemini_dir.is_dir()

    # 4. 探测本地 OpenAI 兼容网关及真实服务就绪性 (避免端口开着但服务 disabled 误判)
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
    gateway_disabled_reason = ""

    for base_v1 in candidate_urls:
        try:
            host_port = base_v1.split("://", 1)[-1].split("/", 1)[0]
            if ":" in host_port:
                host, port_str = host_port.split(":", 1)
                if not _check_tcp_port(host, int(port_str), timeout=0.2):
                    continue

            req = urllib.request.Request(
                f"{base_v1}/models",
                headers={"User-Agent": "AetherQuant/2.3"},
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
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8", errors="ignore")
            if "disabled" in err_body.lower():
                gateway_disabled_reason = "本地网关端口已监听，但反代开关未开启"
                detected_url = base_v1
            elif http_err.code == 401:
                # 需要认证说明网关本身在线可用
                gateway_online = True
                detected_url = base_v1
                break
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            continue

    installed = bool(ag_exe_path or agy_cli or data_dir_exists)
    if gateway_online:
        status_summary = f"本地网关在线 ({detected_url})"
    elif installed:
        status_summary = "已检测到本机 Antigravity (自动双轨兜底模式)"
    else:
        status_summary = "未检测到本机 Antigravity，将使用云端 API"

    return {
        "installed": installed,
        "antigravity_exe": ag_exe_path,
        "agy_cli_available": bool(agy_cli),
        "agy_cli_path": agy_cli,
        "data_dir_exists": data_dir_exists,
        "data_dir_path": str(gemini_dir) if data_dir_exists else "",
        "gateway_online": gateway_online,
        "gateway_url": detected_url or "http://127.0.0.1:8045/v1",
        "gateway_note": gateway_disabled_reason,
        "models": models[:30],
        "status_summary": status_summary,
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

    home = Path.home()
    for cand in (
        home / "Documents" / "Obsidian Vault",
        home / "Documents" / "交易知识库",
        home / "Obsidian",
        home / "OneDrive" / "Obsidian",
    ):
        _add_vault(cand, is_open=False, source="scan")

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
