"""Tk 界面解析与预览辅助函数。"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from typing import Tuple

from wallpaper_maker.config import PREVIEW_MAX_SIDE

def _parse_gui_int(raw: object, default: int) -> int:
    """输入框可能被清空或非数字，避免 int('') 崩溃。"""
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    try:
        return int(s)
    except ValueError:
        return default


def _parse_gui_float(raw: object, default: float) -> float:
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _read_double_var(var: tk.DoubleVar, default: float) -> float:
    try:
        return float(var.get())
    except (tk.TclError, ValueError, TypeError):
        return default


def _preview_render_params(
    full_w: int,
    full_h: int,
    margin: int,
    gap: int,
    text_size: int,
    stamp_size: int,
    max_side: int = PREVIEW_MAX_SIDE,
) -> Tuple[int, int, int, int, int, int, float]:
    """按正式分辨率等比缩小预览：**预览宽/高比与正式图一致**（长边上限 max_side，不设破坏比例的 min 宽高）。"""
    fw, fh = max(1, full_w), max(1, full_h)
    if max(fw, fh) <= max_side:
        return fw, fh, margin, gap, text_size, stamp_size, 1.0
    scale = max_side / max(fw, fh)
    pw = max(1, int(round(fw * scale)))
    ph = max(1, int(round(fh * scale)))
    return (
        pw,
        ph,
        max(8, int(round(margin * scale))),
        max(4, int(round(gap * scale))),
        max(12, int(round(text_size * scale))),
        max(8, int(round(stamp_size * scale))),
        scale,
    )


def _gallery_optimal_cols(
    n: int,
    cw: int,
    ch: int,
    pad: int,
    min_thumb: int,
    caption_h: int = 20,
) -> int:
    """在可用宽高内选择列数，使缩略图尽可能大（接近 2×4、3×3 等随尺寸自适应）。"""
    if n <= 0:
        return 1
    cw = max(cw, min_thumb * 2 + pad * 3)
    ch = max(ch, min_thumb + caption_h + pad * 2)
    best_cols, best_side = 1, -1
    for cols in range(1, n + 1):
        rows = (n + cols - 1) // cols
        w_cell = (cw - pad * (cols + 1)) // cols
        h_cell = (ch - pad * (rows + 1)) // rows
        inner = max(0, h_cell - caption_h)
        side = min(w_cell - 4, inner)
        if side < min_thumb:
            continue
        if side > best_side:
            best_side = side
            best_cols = cols
    if best_side <= 0:
        return max(
            1,
            min(n, max(1, (cw - pad * 2) // (min_thumb + pad))),
        )
    return best_cols


def _open_image_external(path: str) -> None:
    import subprocess
    import sys

    if not os.path.isfile(path):
        return
    if sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    elif sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "linux":
        subprocess.run(["xdg-open", path], check=False)


def estimate_perf_hint(
    w: int, h: int, count: int, batch: int
) -> Tuple[str, str]:
    """根据分辨率、图片张数与批次数返回 (提示文本, 颜色hex)。

    返回空字符串表示参数在安全区间内，无需提示。
    """
    pixels = w * h
    # 单张 RGBA 约 4B/px，渲染期同时有 wallpaper + 若干贴图在内存中
    mem_per_wallpaper_mb = pixels * 4 / (1024 * 1024)
    # 粗估每张贴图占 (像素 / count) 面积（含缩放后）
    mem_per_tile_mb = (pixels / max(1, count)) * 4 / (1024 * 1024)
    peak_mb = mem_per_wallpaper_mb * 2 + mem_per_tile_mb * count
    total_peak_mb = peak_mb * min(2, batch)  # 并发度有限，但缓存/临时对象翻倍估
    # 耗时粗估：基于 640×360 @ 6 张 ≈ 0.15s 的经验值做线性外推
    base_time_s = 0.15
    scale_pixels = pixels / (640 * 360)
    scale_count = count / 6
    est_per_s = base_time_s * max(1.0, scale_pixels ** 0.85) * max(1.0, scale_count ** 0.6)
    est_total_s = est_per_s * batch

    parts: list[str] = []

    if total_peak_mb > 4096:
        parts.append(f"内存峰值 ≈ {total_peak_mb / 1024:.1f} GB ⚠️ 可能导致系统卡顿")
        color = "#D32F2F"
    elif total_peak_mb > 1536:
        parts.append(f"内存峰值 ≈ {total_peak_mb / 1024:.1f} GB")
        color = "#E65100"
    else:
        color = "#666666"

    if est_total_s > 120:
        parts.append(f"预估耗时 ≈ {est_total_s / 60:.0f} 分钟")
        if color == "#666666":
            color = "#E65100"
    elif est_total_s > 30:
        parts.append(f"预估耗时 ≈ {est_total_s:.0f} 秒")
        if color == "#666666":
            color = "#9E9E9E"

    if pixels > 5120 * 2880:
        parts.append("超高分辨率")
        if color == "#666666":
            color = "#E65100"

    if count > 30:
        parts.append(f"图片张数 {count} 较多")
        if color == "#666666":
            color = "#9E9E9E"

    if not parts:
        return "", ""
    return "⚡ " + "  ·  ".join(parts), color


def _popup_image_menu(widget: tk.Misc, event: tk.Event, path: str) -> None:
    """右键菜单：打开图片、复制路径（输出目录已在界面选定，不再提供「在 Finder 中显示」）。"""
    path = os.path.abspath(os.path.expanduser(str(path).strip()))
    top = widget.winfo_toplevel()
    menu = tk.Menu(top, tearoff=0)
    ok = os.path.isfile(path)
    if ok:
        menu.add_command(
            label="打开图片", command=lambda p=path: _open_image_external(p)
        )
    else:
        menu.add_command(
            label="（文件不可用：尚未写入或路径有误）", state=tk.DISABLED
        )

    menu.add_separator()

    def _copy_path() -> None:
        try:
            top.clipboard_clear()
            top.clipboard_append(path)
        except tk.TclError:
            pass

    menu.add_command(label="复制路径", command=_copy_path)
    try:
        menu.tk_popup(int(event.x_root), int(event.y_root))
    finally:
        try:
            menu.grab_release()
        except tk.TclError:
            pass
