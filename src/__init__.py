"""Aether Quant Studio layered backend package."""

from src.paths import PROJECT_ROOT, ensure_sys_path

ensure_sys_path()

__all__ = ["PROJECT_ROOT", "ensure_sys_path"]
