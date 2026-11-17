"""Unified project path resolution and module search-path bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
SRC_DIR: Path = PROJECT_ROOT / "src"
DATA_DIR: Path = PROJECT_ROOT / "data"
STATIC_DIR: Path = PROJECT_ROOT / "static"
CONFIG_DIR: Path = PROJECT_ROOT / "config"
TOOLS_DIR: Path = PROJECT_ROOT / "tools"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
SCRIPTS_DIR: Path = PROJECT_ROOT / "scripts"

MODULE_SEARCH_DIRS: tuple[Path, ...] = (
    PROJECT_ROOT,
    SRC_DIR,
    SRC_DIR / "core",
    SRC_DIR / "strategies",
    SRC_DIR / "ai",
    SRC_DIR / "integrations",
    SRC_DIR / "api",
    SRC_DIR / "desktop",
    SCRIPTS_DIR,
)


def ensure_sys_path() -> None:
    """Register layered package directories so both legacy and package imports resolve cleanly."""
    for directory in reversed(MODULE_SEARCH_DIRS):
        path_str = str(directory)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def load_frontend_bundle_text() -> str:
    """Aggregate modular frontend HTML + CSS + JS into a unified snapshot for contract inspection."""
    parts: list[str] = []
    index_html = STATIC_DIR / "index.html"
    if index_html.is_file():
        parts.append(index_html.read_text(encoding="utf-8"))

    css_dir = STATIC_DIR / "css"
    if css_dir.is_dir():
        for css_file in sorted(css_dir.glob("*.css")):
            parts.append(f"/* === {css_file.name} === */\n" + css_file.read_text(encoding="utf-8"))

    js_dir = STATIC_DIR / "js"
    if js_dir.is_dir():
        js_chunks = [
            f"// === {js_file.name} ===\n" + js_file.read_text(encoding="utf-8")
            for js_file in sorted(js_dir.glob("*.js"))
        ]
        if js_chunks:
            parts.append("<script>\n" + "\n\n".join(js_chunks) + "\n</script>")

    return "\n\n".join(parts)


ensure_sys_path()
