"""风格强度 profile（影响散落等版式的随机幅度）。"""
from __future__ import annotations

from typing import Dict, List

_style_intensity_stack: List[str] = []


def _push_style_intensity(level: str) -> None:
    _style_intensity_stack.append((level or "normal").strip().lower())


def _pop_style_intensity() -> None:
    if _style_intensity_stack:
        _style_intensity_stack.pop()


def _style_profile() -> Dict[str, float]:
    lv = _style_intensity_stack[-1] if _style_intensity_stack else "normal"
    if lv == "conservative":
        return {
            "jitter": 0.78,
            "shadow": 0.86,
            "overlap": 0.82,
            "visible": 1.10,
            "spread": 0.9,
        }
    if lv == "aggressive":
        return {
            "jitter": 1.28,
            "shadow": 1.16,
            "overlap": 1.20,
            "visible": 0.90,
            "spread": 1.12,
        }
    return {
        "jitter": 1.0,
        "shadow": 1.0,
        "overlap": 1.0,
        "visible": 1.0,
        "spread": 1.0,
    }
