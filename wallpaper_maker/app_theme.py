"""主题相关逻辑（从 app.py 拆分）。"""
from __future__ import annotations

import subprocess
import sys
from typing import Callable, Dict


def detect_macos_appearance() -> str:
    if sys.platform != "darwin":
        return "light"
    try:
        out = subprocess.check_output(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return "dark" if out.lower() == "dark" else "light"
    except Exception:
        return "light"


def resolve_theme_mode(
    user_mode: str,
    *,
    detector: Callable[[], str] = detect_macos_appearance,
) -> str:
    mode = (user_mode or "system").strip().lower()
    if mode == "system":
        return detector()
    return "dark" if mode == "dark" else "light"


def theme_palette(mode: str) -> Dict[str, str]:
    if (mode or "light").strip().lower() == "dark":
        return {
            "bg": "#1E1E20",
            "panel": "#2A2A2E",
            "input_bg": "#323238",
            "fg": "#F2F2F7",
            "muted": "#B3B3BD",
            "hint": "#8E8E99",
            "accent": "#4EA1FF",
            "accent_fg": "#FFFFFF",
            "danger": "#FF6B6B",
            "divider": "#3A3A40",
        }
    return {
        "bg": "#FFFFFF",
        "panel": "#F5F5F7",
        "input_bg": "#F5F5F7",
        "fg": "#111111",
        "muted": "#555555",
        "hint": "#888888",
        "accent": "#0A84FF",
        "accent_fg": "#FFFFFF",
        "danger": "#CC0000",
        "divider": "#E5E5EA",
    }

