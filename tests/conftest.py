"""Pytest bootstrap for layered backend modules and modular frontend bundle inspection."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src  # noqa: F401 - register src/* layered module paths


def load_frontend_bundle_text() -> str:
    """Aggregate modular frontend HTML + CSS + JS into a unified text snapshot for contract tests."""
    static_dir = PROJECT_ROOT / "static"
    parts: list[str] = []

    index_html = static_dir / "index.html"
    if index_html.is_file():
        parts.append(index_html.read_text(encoding="utf-8"))

    css_dir = static_dir / "css"
    if css_dir.is_dir():
        for css_file in sorted(css_dir.glob("*.css")):
            parts.append(f"/* === {css_file.name} === */\n" + css_file.read_text(encoding="utf-8"))

    js_dir = static_dir / "js"
    if js_dir.is_dir():
        js_chunks = [
            f"// === {js_file.name} ===\n" + js_file.read_text(encoding="utf-8")
            for js_file in sorted(js_dir.glob("*.js"))
        ]
        if js_chunks:
            parts.append("<script>\n" + "\n\n".join(js_chunks) + "\n</script>")

    return "\n\n".join(parts)
