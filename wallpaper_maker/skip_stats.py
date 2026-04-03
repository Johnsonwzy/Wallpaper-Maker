"""图源跳过统计与上下文栈。"""
from __future__ import annotations

from typing import List, Optional

class ImageSourceSkipStats:
    """图源前置剔除 + 绘制时跳过计数，供状态栏/批处理汇总。"""

    __slots__ = ("pre_filter_skipped", "runtime_skipped")

    def __init__(self) -> None:
        self.pre_filter_skipped = 0
        self.runtime_skipped = 0

    def summary_zh(self) -> str:
        parts: List[str] = []
        if self.pre_filter_skipped:
            parts.append(f"前置剔除 {self.pre_filter_skipped} 张")
        if self.runtime_skipped:
            parts.append(f"绘制跳过 {self.runtime_skipped} 张")
        if not parts:
            return ""
        return "　|　图源：" + "，".join(parts)

    def summary_en(self) -> str:
        parts: List[str] = []
        if self.pre_filter_skipped:
            parts.append(f"pre-filter skipped {self.pre_filter_skipped}")
        if self.runtime_skipped:
            parts.append(f"render skipped {self.runtime_skipped}")
        if not parts:
            return ""
        return " | source: " + ", ".join(parts)

    def summary(self, lang: str = "zh") -> str:
        return self.summary_en() if lang == "en" else self.summary_zh()


_image_skip_stats_stack: List[Optional[ImageSourceSkipStats]] = []


def _push_image_skip_stats(s: Optional[ImageSourceSkipStats]) -> None:
    _image_skip_stats_stack.append(s)


def _pop_image_skip_stats() -> None:
    if _image_skip_stats_stack:
        _image_skip_stats_stack.pop()


def _note_skipped_runtime() -> None:
    if _image_skip_stats_stack and _image_skip_stats_stack[-1] is not None:
        _image_skip_stats_stack[-1].runtime_skipped += 1
