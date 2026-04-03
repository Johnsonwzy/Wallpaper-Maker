"""壁纸渲染引擎：字体、渐变、布局绘制、导出与 CLI。"""
from __future__ import annotations

import math
import os
import random
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageStat

try:
    Image.MAX_IMAGE_PIXELS = 280_000_000
except Exception:
    pass

from wallpaper_maker.config import (
    DEFAULT_BG_BASE_STYLE,
    DEFAULT_BG_OVERLAY_STRENGTH,
    DEFAULT_BG_OVERLAY_STYLE,
    DEFAULT_BG_STYLE,
    DEFAULT_ENABLE_AESTHETIC_RULES,
    DEFAULT_EXPORT_FORMAT,
    DEFAULT_FILTER_STRENGTH,
    DEFAULT_FILTER_STYLE,
    DEFAULT_IMAGE_FOLDER,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_LAYOUT,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RANDOM_COUNT,
    DEFAULT_STAMP_POS,
    DEFAULT_STAMP_SIZE,
    DEFAULT_STYLE_INTENSITY,
    DEFAULT_TEXT_POS,
    DEFAULT_TEXT_SIZE,
    DEFAULT_WALLPAPER_HEIGHT,
    DEFAULT_WALLPAPER_WIDTH,
    DEFAULT_WEBP_QUALITY,
    MAX_SOURCE_IMAGE_FILE_BYTES,
)
from wallpaper_maker.core_export import (
    _export_ext,
    _export_save_path_resolved,
    _normalize_export_format,
    _save_wallpaper_file,
)
from wallpaper_maker.core_filters import apply_post_filter_impl
from wallpaper_maker.core_overlays import (
    _apply_edge_vignette as _apply_edge_vignette_impl,
    apply_bg_overlay_impl,
)
from wallpaper_maker.image_filter import filter_readable_image_paths
from wallpaper_maker.sampling import (
    get_all_image_paths,
    get_image_paths_from_folders as _sampling_get_image_paths_from_folders,
    pick_paths_by_strategy as _sampling_pick_paths_by_strategy,
)
from wallpaper_maker.skip_stats import (
    ImageSourceSkipStats,
    _note_skipped_runtime,
    _pop_image_skip_stats,
    _push_image_skip_stats,
)
from wallpaper_maker.style_intensity import (
    _pop_style_intensity,
    _push_style_intensity,
    _style_profile,
)
from wallpaper_maker.core_layouts import (
    _aesthetic_order_paths,
    _best_columns,
    _bbox_tl,
    _cell_prepare,
    _compute_grid,
    _masonry_in_box,
    _norm_corner_pos,
    _normalize_layout,
    _opposite_corner,
    _paste_rotated_center,
    _paste_stack_strong,
    _paste_tile_shadow,
    _place_tile_constrained,
    _rect_overlap,
    _render_arc,
    _render_centered,
    _render_circle,
    _render_cross,
    _render_diag_two,
    _render_diagonal_flow,
    _render_fade,
    _render_fan,
    _render_focus,
    _render_heart,
    _render_honeycomb,
    _render_layer,
    _render_left_white,
    _render_masonry,
    _render_s_shape,
    _render_scatter,
    _render_split,
    _render_spiral,
    _render_stack,
    _render_text_flow,
    _render_triangle,
    _render_v_shape,
    _render_w_shape,
    _render_wing,
    draw_custom_text,
    get_text_font,
)

def get_image_paths_from_folders(
    folders: Sequence[str],
    *,
    recursive: bool = False,
    per_folder_counts: Optional[List[Tuple[str, int]]] = None,
    per_folder_paths: Optional[List[Tuple[str, List[str]]]] = None,
) -> list[str]:
    """兼容导出：实现已收敛到 sampling 模块。"""
    return _sampling_get_image_paths_from_folders(
        folders,
        recursive=recursive,
        per_folder_counts=per_folder_counts,
        per_folder_paths=per_folder_paths,
    )


def pick_paths_by_strategy(
    pool_paths: Sequence[str],
    count: int,
    *,
    strategy: str = "natural",
    per_folder_paths: Optional[Sequence[Tuple[str, Sequence[str]]]] = None,
    folder_weight_by_path: Optional[Dict[str, float]] = None,
    seed: Optional[int] = None,
) -> List[str]:
    """兼容导出：实现已收敛到 sampling 模块。"""
    return _sampling_pick_paths_by_strategy(
        pool_paths,
        count,
        strategy=strategy,
        per_folder_paths=per_folder_paths,
        folder_weight_by_path=folder_weight_by_path,
        seed=seed,
    )


def _srgb_byte_to_linear(x: int) -> float:
    c = max(0, min(255, x)) / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb_byte(u: float) -> int:
    c = max(0.0, min(1.0, u))
    if c <= 0.0031308:
        s = 12.92 * c
    else:
        s = 1.055 * (c ** (1.0 / 2.4)) - 0.055
    return max(0, min(255, int(round(s * 255))))


def _lerp_srgb(
    top: Tuple[int, int, int], bottom: Tuple[int, int, int], t: float
) -> Tuple[int, int, int]:
    """在线性光空间插值，减轻中间调发灰（比直接 RGB 线性插值更符合感知）。"""
    t = max(0.0, min(1.0, t))
    out: list[int] = []
    for i in range(3):
        a = _srgb_byte_to_linear(top[i])
        b = _srgb_byte_to_linear(bottom[i])
        out.append(_linear_to_srgb_byte(a + (b - a) * t))
    return out[0], out[1], out[2]


def _average_rgb_linear(colors: Sequence[Tuple[int, int, int]]) -> Tuple[int, int, int]:
    if not colors:
        return (128, 128, 128)
    lr = lg = lb = 0.0
    for r, g, b in colors:
        lr += _srgb_byte_to_linear(int(r))
        lg += _srgb_byte_to_linear(int(g))
        lb += _srgb_byte_to_linear(int(b))
    n = float(len(colors))
    return (
        _linear_to_srgb_byte(lr / n),
        _linear_to_srgb_byte(lg / n),
        _linear_to_srgb_byte(lb / n),
    )


def _vertical_gradient(
    width: int,
    height: int,
    top: Tuple[int, int, int],
    bottom: Tuple[int, int, int],
) -> Image.Image:
    h = max(1, height)
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        px[0, y] = _lerp_srgb(top, bottom, t)
    return strip.resize((max(1, width), h), Image.Resampling.BILINEAR)


def _radial_gradient(
    width: int,
    height: int,
    center: Tuple[int, int, int],
    edge: Tuple[int, int, int],
    *,
    max_work_side: int = 720,
) -> Image.Image:
    """中心→边缘径向渐变（线性光空间插值）；大图先算小缓冲再放大以控耗时。"""
    w, h = max(1, width), max(1, height)
    lim = max(64, int(max_work_side))
    if w > lim or h > lim:
        scale = min(lim / w, lim / h)
        ws = max(2, int(round(w * scale)))
        hs = max(2, int(round(h * scale)))
    else:
        ws, hs = w, h
    img = Image.new("RGB", (ws, hs))
    px = img.load()
    cx = (ws - 1) * 0.5
    cy = (hs - 1) * 0.5
    rmax = math.hypot(cx, cy) or 1.0
    for y in range(hs):
        dy = y - cy
        dy2 = dy * dy
        for x in range(ws):
            dx = x - cx
            t = min(1.0, math.sqrt(dx * dx + dy2) / rmax)
            px[x, y] = _lerp_srgb(center, edge, t)
    if (ws, hs) != (w, h):
        return img.resize((w, h), Image.Resampling.BILINEAR)
    return img


def _color_at_stops(
    t: float, stops: Sequence[Tuple[Tuple[int, int, int], float]]
) -> Tuple[int, int, int]:
    """多停靠点 0..1 上的 sRGB 插值（用于杂志风多段渐变）。"""
    if not stops:
        return (128, 128, 128)
    t = max(0.0, min(1.0, t))
    if t <= stops[0][1]:
        return stops[0][0]
    for i in range(len(stops) - 1):
        ta, ca = stops[i][1], stops[i][0]
        tb, cb = stops[i + 1][1], stops[i + 1][0]
        if t <= tb:
            u = (t - ta) / max(tb - ta, 1e-6)
            return _lerp_srgb(ca, cb, u)
    return stops[-1][0]


def _magazine_editorial_gradient(
    width: int, height: int, *, seed: Optional[int]
) -> Image.Image:
    """杂志编辑风：暖纸色多段竖直渐变，轻随机偏移避免模板感。"""
    rng = random.Random(seed)
    drift = rng.uniform(-0.04, 0.04)
    stops: List[Tuple[Tuple[int, int, int], float]] = [
        ((252, 248, 242), 0.0),
        ((245, 232, 218), max(0.0, min(1.0, 0.28 + drift * 0.6))),
        ((228, 208, 192), 0.58),
        ((210, 185, 168), 0.85),
        ((198, 172, 155), 1.0),
    ]
    hh = max(1, height)
    strip = Image.new("RGB", (1, hh))
    px = strip.load()
    for y in range(hh):
        tt = y / max(hh - 1, 1)
        px[0, y] = _color_at_stops(tt, stops)
    return strip.resize((max(1, width), hh), Image.Resampling.BILINEAR)


def _apply_edge_vignette(im: Image.Image, *, strength: float = 0.46) -> Image.Image:
    """暗角：边缘向黑色过渡。"""
    return _apply_edge_vignette_impl(im, strength=strength)


def _mean_rgb_from_path(path: str, size: int = 80) -> Optional[Tuple[int, int, int]]:
    try:
        if not os.path.isfile(path):
            return None
        sz = os.path.getsize(path)
        if sz <= 0 or sz > MAX_SOURCE_IMAGE_FILE_BYTES:
            return None
        with Image.open(path) as im:
            tw = max(size * 2, 96)
            try:
                im.draft("RGB", (tw, tw))
            except Exception:
                pass
            im.load()
            w0, h0 = im.size
            if w0 * h0 > 900_000:
                try:
                    rf = max(
                        2,
                        int(round(math.sqrt((w0 * h0) / 250_000))),
                    )
                    im = im.reduce(rf)
                except (AttributeError, ValueError, TypeError):
                    pass
                w0, h0 = im.size
            im = im.convert("RGB")
            frac = 0.62
            cw = max(2, int(w0 * frac))
            ch = max(2, int(h0 * frac))
            x0 = (w0 - cw) // 2
            y0 = (h0 - ch) // 2
            im = im.crop((x0, y0, x0 + cw, y0 + ch))
            im = im.resize((size, size), Image.Resampling.LANCZOS)
            mu = ImageStat.Stat(im).mean
            return tuple(max(0, min(255, int(round(c)))) for c in mu[:3])
    except Exception:
        return None


def gradient_endpoints_from_covers(
    paths: Sequence[str],
    *,
    seed: Optional[int],
    max_samples: int = 24,
) -> Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]:
    plist = list(paths)
    if not plist:
        return None
    rng = random.Random(seed)
    if len(plist) > max_samples:
        plist = rng.sample(plist, max_samples)
    avgs: list[Tuple[int, int, int]] = []
    for p in plist:
        c = _mean_rgb_from_path(p)
        if c is not None:
            avgs.append(c)
    if not avgs:
        return None

    def _lum(c: Tuple[int, int, int]) -> float:
        r, g, b = c
        return 0.299 * r + 0.587 * g + 0.114 * b

    avgs.sort(key=_lum)
    n = len(avgs)
    k = max(1, n // 3)
    dark = _average_rgb_linear([avgs[i] for i in range(k)])
    light = _average_rgb_linear([avgs[n - 1 - i] for i in range(k)])
    top, bottom = light, dark
    dist2 = sum((top[i] - bottom[i]) ** 2 for i in range(3))
    if dist2 < 420:
        top = tuple(min(255, int(c * 1.1 + 14)) for c in top)
        bottom = tuple(max(0, int(c * 0.9 - 10)) for c in bottom)
    return top, bottom




def _norm_strength(v: object) -> float:
    try:
        # 非线性映射：中档强度更有存在感（便于切换时肉眼感知差异）。
        x = max(0.0, min(1.0, float(v) / 100.0))
        return x ** 0.78
    except Exception:
        return 1.0


def _apply_post_filter(
    im: Image.Image,
    filter_style: str,
    *,
    seed: Optional[int],
    strength: object = DEFAULT_FILTER_STRENGTH,
) -> Image.Image:
    t = _norm_strength(strength)
    return apply_post_filter_impl(
        im,
        filter_style,
        seed=seed,
        strength=t,
        edge_vignette_fn=_apply_edge_vignette,
        lerp_srgb_fn=_lerp_srgb,
    )


def apply_post_filter(
    im: Image.Image,
    filter_style: str,
    *,
    seed: Optional[int] = None,
    strength: object = DEFAULT_FILTER_STRENGTH,
) -> Image.Image:
    """公开给预览层调用：对已生成画面做后期滤镜。"""
    return _apply_post_filter(im, filter_style, seed=seed, strength=strength)


def apply_bg_overlay(
    im: Image.Image,
    overlay_style: str,
    *,
    seed: Optional[int] = None,
    strength: object = DEFAULT_BG_OVERLAY_STRENGTH,
) -> Image.Image:
    """公开给预览层调用：对已生成画面做背景叠层后处理。"""
    return _apply_bg_overlay(im, overlay_style, seed=seed, strength=strength)


def _legacy_bg_to_base_overlay(bg_style: str) -> Tuple[str, str]:
    """兼容旧字段 bg_style：拆分为 base + overlay。"""
    bs = (bg_style or DEFAULT_BG_STYLE).strip().lower()
    if bs == "frosted_glass":
        return "from_covers", "frosted_glass"
    if bs == "edge_vignette":
        return "from_covers", "edge_vignette"
    if bs == "geo_texture":
        return "from_covers", "geo_texture"
    if bs == "magazine_gradient":
        return "magazine_gradient", "none"
    return bs, "none"


def _apply_bg_overlay(
    im: Image.Image,
    overlay_style: str,
    *,
    seed: Optional[int],
    strength: object = DEFAULT_BG_OVERLAY_STRENGTH,
) -> Image.Image:
    t = _norm_strength(strength)
    return apply_bg_overlay_impl(
        im,
        overlay_style,
        seed=seed,
        strength=t,
    )


def create_wallpaper(
    image_paths: Sequence[str],
    count: int,
    w: int,
    h: int,
    out_dir: str,
    custom_text: str = "",
    *,
    seed: Optional[int] = None,
    bg_color: Tuple[int, int, int] = (245, 245, 245),
    margin: int = 40,
    gap: int = 30,
    cover_aspect: float = 1.4,
    cell_outline: bool = True,
    layout: str = "grid",
    scatter_rotation: float = 14.0,
    scatter_scale_min: float = 0.7,
    scatter_scale_max: float = 1.45,
    scatter_bleed: float = 0.1,
    scatter_shadow: bool = True,
    bg_style: str = "from_covers",
    bg_base_style: Optional[str] = None,
    bg_overlay_style: Optional[str] = None,
    bg_overlay_strength: int = DEFAULT_BG_OVERLAY_STRENGTH,
    custom_bg_gradient: Optional[
        Tuple[Tuple[int, int, int], Tuple[int, int, int]]
    ] = None,
    palette_max_samples: int = 24,
    text_size: int = 60,
    stamp_size: int = 42,
    text_pos: str = "bottom_right",
    stamp_pos: str = "bottom_left",
    text_color: tuple = (255,255,255),
    stroke_color: tuple = (0,0,0),
    save_path_override: Optional[str] = None,
    show_stamp: bool = True,
    stamp_place: str = "same_above",
    export_format: str = DEFAULT_EXPORT_FORMAT,
    filter_style: str = DEFAULT_FILTER_STYLE,
    filter_strength: int = DEFAULT_FILTER_STRENGTH,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    webp_quality: int = DEFAULT_WEBP_QUALITY,
    webp_lossless: bool = False,
    embed_srgb_icc: bool = True,
    style_intensity: str = DEFAULT_STYLE_INTENSITY,
    enable_aesthetic_rules: bool = DEFAULT_ENABLE_AESTHETIC_RULES,
    skip_stats: Optional[ImageSourceSkipStats] = None,
    skip_path_validation: bool = False,
) -> str:
    _push_image_skip_stats(skip_stats)
    _push_style_intensity(style_intensity)
    try:
        paths = list(image_paths)
        if not paths:
            raise ValueError("没有可用图片路径")
        if not skip_path_validation:
            filtered, n_bad = filter_readable_image_paths(paths)
            if skip_stats is not None:
                skip_stats.pre_filter_skipped += n_bad
            paths = filtered
            if not paths:
                suf = (
                    f"（已跳过 {n_bad} 个损坏/空文件/过大或无法解码的图源）"
                    if n_bad
                    else ""
                )
                raise ValueError(f"没有可解码的图片{suf}")

        mode = _normalize_layout(layout)
        prof = _style_profile()
        scatter_rotation = float(scatter_rotation) * prof["jitter"]
        scatter_bleed = float(scatter_bleed) * prof["spread"]

        n = max(1, min(int(count), len(paths)))
        # 预览/正式导出已在外层按策略用种子抽样（pick_paths_by_strategy），并传
        # skip_path_validation=True。若此处再用同一 seed 对「已抽好的 n 张」二次
        # random.sample，会与旧版「整池一次 random.sample」消耗的随机序列不一致，
        # 散落等版式里「图序 → rng 消耗顺序」会变，观感明显不同。
        if skip_path_validation and len(paths) == n:
            selected = list(paths)
        else:
            if seed is not None:
                random.seed(seed)
            selected = random.sample(paths, n)
        # 审美一致性：统一主次与节奏（不改变随机池，只重排选中序列）
        if enable_aesthetic_rules and mode in (
            "scatter",
            "focus",
            "diagonal",
            "fan",
            "stack",
            "w_shape",
            "v_shape",
            "arc",
            "cross",
            "wing",
            "heart",
            "circle",
            "s_shape",
            "text_flow",
            "centered",
            "left_white",
            "triangle",
            "spiral",
            "diag_two",
            "layer",
            "honeycomb",
            "fade",
        ):
            selected = _aesthetic_order_paths(selected, seed)

        # 审美一致性：有格言时给版面留一点安全边距，提升呼吸感
        margin_eff = int(margin)
        if enable_aesthetic_rules and custom_text.strip() and mode in (
            "scatter",
            "focus",
            "diagonal",
            "fan",
            "stack",
            "w_shape",
            "v_shape",
            "arc",
            "cross",
            "wing",
            "heart",
            "circle",
            "s_shape",
            "text_flow",
            "left_white",
            "triangle",
            "spiral",
            "diag_two",
            "layer",
            "honeycomb",
            "fade",
        ):
            margin_eff = max(margin_eff, int(min(w, h) * 0.045))

        if save_path_override is not None:
            save_abs = _export_save_path_resolved(
                os.path.abspath(save_path_override), export_format
            )
            parent = os.path.dirname(save_abs)
            if parent:
                os.makedirs(parent, exist_ok=True)
        else:
            ts_ms = int(time.time() * 1000)
            rand_suffix = f"{random.randrange(0, 16**4):04x}"
            os.makedirs(out_dir, exist_ok=True)
            ext = _export_ext(export_format)
            save_abs = os.path.join(out_dir, f"Wallpaper_{ts_ms}_{rand_suffix}{ext}")
    
        grad_top: Optional[Tuple[int, int, int]] = None
        grad_bottom: Optional[Tuple[int, int, int]] = None
    
        def _neutral_line_endpoints() -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
            top = tuple(max(0, min(255, c - 10)) for c in bg_color)
            bottom = tuple(max(0, min(255, c + 12)) for c in bg_color)
            return top, bottom
    
        def _cover_endpoints() -> Optional[
            Tuple[Tuple[int, int, int], Tuple[int, int, int]]
        ]:
            return gradient_endpoints_from_covers(
                selected,
                seed=seed,
                max_samples=max(4, min(int(palette_max_samples), 48)),
            )
    
        legacy_base, legacy_overlay = _legacy_bg_to_base_overlay(bg_style)
        base_style = (
            (bg_base_style or "").strip().lower()
            if bg_base_style is not None
            else legacy_base
        )
        overlay_style = (
            (bg_overlay_style or "").strip().lower()
            if bg_overlay_style is not None
            else legacy_overlay
        )
        if base_style not in (
            "from_covers",
            "neutral_gradient",
            "solid",
            "radial_covers",
            "custom_gradient",
            "custom_gradient_radial",
            "magazine_gradient",
        ):
            base_style = DEFAULT_BG_BASE_STYLE
        if overlay_style not in (
            "none",
            "frosted_glass",
            "edge_vignette",
            "geo_texture",
            "paper_grain",
            "soft_bloom",
            "cinematic_grade",
            "radial_focus",
        ):
            overlay_style = DEFAULT_BG_OVERLAY_STYLE

        if base_style == "solid":
            wallpaper = Image.new("RGB", (w, h), color=bg_color)
        elif base_style in ("custom_gradient", "custom_gradient_radial"):
            cg = custom_bg_gradient
            if cg is not None:
                grad_top, grad_bottom = cg[0], cg[1]
                if base_style == "custom_gradient_radial":
                    wallpaper = _radial_gradient(w, h, grad_top, grad_bottom)
                else:
                    wallpaper = _vertical_gradient(w, h, grad_top, grad_bottom)
            else:
                wallpaper = Image.new("RGB", (w, h), color=bg_color)
        elif base_style == "radial_covers":
            pair = _cover_endpoints()
            if pair is not None:
                grad_top, grad_bottom = pair
            else:
                grad_top, grad_bottom = _neutral_line_endpoints()
            wallpaper = _radial_gradient(w, h, grad_top, grad_bottom)
        elif base_style == "from_covers":
            pair = _cover_endpoints()
            if pair is not None:
                grad_top, grad_bottom = pair
            if grad_top is not None and grad_bottom is not None:
                wallpaper = _vertical_gradient(w, h, grad_top, grad_bottom)
            elif mode != "seamless":
                grad_top, grad_bottom = _neutral_line_endpoints()
                wallpaper = _vertical_gradient(w, h, grad_top, grad_bottom)
            else:
                wallpaper = Image.new("RGB", (w, h), color=bg_color)
        elif base_style == "magazine_gradient":
            wallpaper = _magazine_editorial_gradient(w, h, seed=seed)
            grad_top = (245, 232, 218)
            grad_bottom = (198, 172, 155)
        else:
            if mode != "seamless":
                grad_top, grad_bottom = _neutral_line_endpoints()
                wallpaper = _vertical_gradient(w, h, grad_top, grad_bottom)
            else:
                wallpaper = Image.new("RGB", (w, h), color=bg_color)

        wallpaper = _apply_bg_overlay(
            wallpaper, overlay_style, seed=seed, strength=bg_overlay_strength
        )
    
        scatter_fill = bg_color
        if grad_top is not None and grad_bottom is not None:
            scatter_fill = tuple(
                max(0, min(255, int((grad_top[i] + grad_bottom[i]) / 2)))
                for i in range(3)
            )
    
        if mode == "scatter":
            _render_scatter(
                wallpaper,
                selected,
                w,
                h,
                scatter_fill,
                seed=seed,
                rotation_deg=max(0.0, float(scatter_rotation)),
                scale_min=max(0.2, min(scatter_scale_min, scatter_scale_max)),
                scale_max=max(0.2, max(scatter_scale_min, scatter_scale_max)),
                bleed=max(0.0, min(0.35, float(scatter_bleed))),
                shadow=scatter_shadow,
                text_safe_pos=(
                    _norm_corner_pos(text_pos)
                    if (enable_aesthetic_rules and custom_text.strip())
                    else None
                ),
            )
        elif mode == "focus":
            _render_focus(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "diagonal":
            _render_diagonal_flow(
                wallpaper, selected, w, h, margin_eff, scatter_fill, gap, seed=seed
            )
        elif mode == "masonry":
            _render_masonry(wallpaper, selected, w, h, margin_eff, gap, seed=seed)
        elif mode == "fan":
            _render_fan(wallpaper, selected, w, h, margin_eff, scatter_fill, seed=seed, rotation_deg=scatter_rotation)
        elif mode == "stack":
            _render_stack(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "split":
            _render_split(wallpaper, selected, w, h, margin_eff, gap, seed=seed)
        elif mode == "w_shape":
            _render_w_shape(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "v_shape":
            _render_v_shape(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "arc":
            _render_arc(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "cross":
            _render_cross(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "wing":
            _render_wing(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "heart":
            _render_heart(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "circle":
            _render_circle(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "s_shape":
            _render_s_shape(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "text_flow":
            _render_text_flow(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "centered":
            _render_centered(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "left_white":
            _render_left_white(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "triangle":
            _render_triangle(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "spiral":
            _render_spiral(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "diag_two":
            _render_diag_two(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "layer":
            _render_layer(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "honeycomb":
            _render_honeycomb(wallpaper, selected, w, h, scatter_fill, seed=seed)
        elif mode == "fade":
            _render_fade(wallpaper, selected, w, h, scatter_fill, seed=seed)
        else:
            g = 0 if mode == "seamless" else gap
            outline = cell_outline and mode == "grid"
            cover = mode == "seamless"
            cols, rows, slot_w, slot_h = _compute_grid(
                n, w, h, margin_eff, g, cover_aspect
            )
            draw = ImageDraw.Draw(wallpaper) if outline else None
    
            for idx, img_path in enumerate(selected):
                try:
                    with Image.open(img_path).convert("RGB") as img:
                        tile = _cell_prepare(img, slot_w, slot_h, cover=cover)
                        cell_x = margin_eff + (idx % cols) * (slot_w + g)
                        cell_y = margin_eff + (idx // cols) * (slot_h + g)
                        x = cell_x + (slot_w - tile.width) // 2
                        y = cell_y + (slot_h - tile.height) // 2
                        _paste_tile_shadow(
                            wallpaper, tile, x, y, with_shadow=(mode == "grid")
                        )
                        if outline and draw is not None:
                            draw.rectangle(
                                [
                                    cell_x,
                                    cell_y,
                                    cell_x + slot_w - 1,
                                    cell_y + slot_h - 1,
                                ],
                                outline=(255, 255, 255),
                                width=1,
                            )
                except Exception:
                    _note_skipped_runtime()
    
        wallpaper = _apply_post_filter(
            wallpaper,
            filter_style,
            seed=seed,
            strength=filter_strength,
        )

        stamp_line = time.strftime("%Y-%m-%d %H:%M") if show_stamp else ""
        draw_custom_text(
            wallpaper,
            custom_text,
            stamp_line,
            text_size=text_size,
            stamp_size=stamp_size,
            text_pos=text_pos,
            stamp_pos=stamp_pos,
            text_color=text_color,
            stroke_color=stroke_color,
            stamp_place=stamp_place,
        )
    
        _save_wallpaper_file(
            wallpaper,
            save_abs,
            export_format=export_format,
            jpeg_quality=jpeg_quality,
            webp_quality=webp_quality,
            webp_lossless=webp_lossless,
            embed_srgb_icc=embed_srgb_icc,
        )
        return os.path.abspath(save_abs)
    finally:
        _pop_style_intensity()
        _pop_image_skip_stats()


def run_cli() -> None:
    folder = DEFAULT_IMAGE_FOLDER
    out_dir = DEFAULT_OUTPUT_DIR
    count = DEFAULT_RANDOM_COUNT
    w, h = DEFAULT_WALLPAPER_WIDTH, DEFAULT_WALLPAPER_HEIGHT

    images = get_all_image_paths(folder)
    if not images:
        print("❌ 未找到任何图片，请检查文件夹路径")
        return
    print(f"📁 共检测到 {len(images)} 张图片，随机抽取 {count} 张")
    path = create_wallpaper(
        images,
        count,
        w,
        h,
        out_dir,
        custom_text="Stay Hungry, Stay Foolish",
        layout=DEFAULT_LAYOUT,
        bg_style=DEFAULT_BG_STYLE,
        text_size=DEFAULT_TEXT_SIZE,
        stamp_size=DEFAULT_STAMP_SIZE,
        text_pos=DEFAULT_TEXT_POS,
        stamp_pos=DEFAULT_STAMP_POS,
        style_intensity=DEFAULT_STYLE_INTENSITY,
    )
    print(f"✅ 壁纸生成完成！\n路径：{path}")
