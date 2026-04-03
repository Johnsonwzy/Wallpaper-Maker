"""布局渲染器与辅助绘图函数 —— 从 core.py 抽取。

包含所有 ``_render_*`` 布局函数、网格计算、贴图辅助、
文本绘制 (``draw_custom_text``) 和审美排序。
"""
from __future__ import annotations

import math
import os
import random
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageFont, ImageStat

from wallpaper_maker.skip_stats import _note_skipped_runtime
from wallpaper_maker.style_intensity import _style_profile


LAYOUT_ALIASES = {
    "grid": "grid",
    "标准网格": "grid",
    "seamless": "seamless",
    "无缝": "seamless",
    "无缝铺满": "seamless",
    "scatter": "scatter",
    "散落": "scatter",
    "重叠": "scatter",
    "focus": "focus",
    "中心大图": "focus",
    "焦点": "focus",
    "diagonal": "diagonal",
    "斜向流": "diagonal",
    "对角流": "diagonal",
    "masonry": "masonry",
    "瀑布流": "masonry",
    "fan": "fan",
    "扇形": "fan",
    "放射": "fan",
    "stack": "stack",
    "堆叠": "stack",
    "翻页堆叠": "stack",
    "split": "split",
    "分屏对称": "split",
    "对称": "split",
    "w_shape": "w_shape",
    "W型波浪": "w_shape",
    "v_shape": "v_shape",
    "V型": "v_shape",
    "arc": "arc",
    "弧形": "arc",
    "cross": "cross",
    "十字扩散": "cross",
    "wing": "wing",
    "对称翼型": "wing",
    "heart": "heart",
    "心形": "heart",
    "circle": "circle",
    "圆形环绕": "circle",
    "s_shape": "s_shape",
    "S型": "s_shape",
    "text_flow": "text_flow",
    "斜排文字流": "text_flow",
        # 高级感新排版
    "centered": "centered",
    "极简居中对称": "centered",
    "left_white": "left_white",
    "左对齐留白": "left_white",
    "triangle": "triangle",
    "三角稳定构图": "triangle",
    "spiral": "spiral",
    "螺旋环绕": "spiral",
    "diag_two": "diag_two",
    "对角线双飞": "diag_two",
    "layer": "layer",
    "上下分层极简": "layer",
    "honeycomb": "honeycomb",
    "六边形蜂窝": "honeycomb",
    "fade": "fade",
    "渐隐散点": "fade",
}

VALID_LAYOUTS = frozenset(
    {
        "grid",
        "seamless",
        "scatter",
        "focus",
        "diagonal",
        "masonry",
        "fan",
        "stack",
        "split",
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
    }
)


def get_text_font(size: int = 60):
    import sys
    try:
        if sys.platform == "darwin":
            # macOS 标准字体，不写死系统路径，只依赖 fontname
            return ImageFont.truetype("STHeiti Medium", size)
        elif sys.platform == "win32":
            return ImageFont.truetype("Microsoft YaHei", size)
        else:
            return ImageFont.truetype("DejaVu Sans", size)
    except:
        try:
            return ImageFont.truetype("Arial Bold", size)
        except:
            return ImageFont.load_default(size)

def _best_columns(
    count: int, w: int, h: int, margin: int, gap: int, cover_aspect: float
) -> int:
    if count <= 1:
        return 1
    target_wh = 1.0 / cover_aspect
    best_c: Optional[int] = None
    best_key: Tuple[int, float] | None = None

    for cols in range(1, count + 1):
        rows = (count + cols - 1) // cols
        waste = cols * rows - count
        aw = w - 2 * margin - (cols - 1) * gap
        ah = h - 2 * margin - (rows - 1) * gap
        if aw <= 0 or ah <= 0:
            continue
        sw, sh = aw / cols, ah / rows
        if sh <= 0 or sw <= 0:
            continue
        ratio = sw / sh
        aspect_err = (ratio - target_wh) ** 2
        key = (waste, aspect_err)
        if best_key is None or key < best_key:
            best_key, best_c = key, cols

    return best_c if best_key is not None else max(1, int(count**0.5))

def _compute_grid(
    count: int, w: int, h: int, margin: int, gap: int, cover_aspect: float
) -> Tuple[int, int, int, int]:
    cols = _best_columns(count, w, h, margin, gap, cover_aspect)
    rows = (count + cols - 1) // cols

    avail_w = w - 2 * margin - (cols - 1) * gap
    avail_h = h - 2 * margin - (rows - 1) * gap
    if avail_w <= 0 or avail_h <= 0:
        margin = min(margin, w // 8, h // 8)
        gap = min(gap, 10)
        cols = _best_columns(count, w, h, margin, gap, cover_aspect)
        rows = (count + cols - 1) // cols
        avail_w = max(1, w - 2 * margin - (cols - 1) * gap)
        avail_h = max(1, h - 2 * margin - (rows - 1) * gap)

    slot_w = max(1, avail_w // cols)
    slot_h = max(1, avail_h // rows)
    return cols, rows, slot_w, slot_h

def _normalize_layout(layout: str) -> str:
    key = (layout or "grid").strip().lower()
    if key in LAYOUT_ALIASES:
        return LAYOUT_ALIASES[key]
    if key in VALID_LAYOUTS:
        return key
    return "grid"

def _cell_prepare(
    img: Image.Image, slot_w: int, slot_h: int, *, cover: bool
) -> Image.Image:
    if cover:
        return ImageOps.fit(img, (slot_w, slot_h), Image.Resampling.LANCZOS)
    out = img.copy()
    out.thumbnail((slot_w, slot_h), Image.Resampling.LANCZOS)
    return out

def _paste_tile_shadow(
    wallpaper: Image.Image,
    img: Image.Image,
    x: int,
    y: int,
    *,
    with_shadow: bool,
) -> None:
    if not with_shadow:
        wallpaper.paste(img, (x, y))
        return
    prof = _style_profile()
    pad = max(4, min(16, int((min(img.size) // 18) * prof["shadow"])))
    blur_r = max(3, min(12, int((min(img.size) // 25) * prof["shadow"])))
    alpha = min(60, max(16, int((22 + min(img.size) // 30) * prof["shadow"])))
    shadow = Image.new(
        "RGBA",
        (img.width + pad * 2, img.height + pad * 2),
        (0, 0, 0, 0),
    )
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rectangle(
        [pad, pad, pad + img.width - 1, pad + img.height - 1],
        fill=(0, 0, 0, alpha),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur_r))
    wallpaper.paste(shadow, (x - pad, y - pad), shadow)
    wallpaper.paste(img, (x, y))

def _render_scatter(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    bg_color: Tuple[int, int, int],
    *,
    seed: Optional[int],
    rotation_deg: float,
    scale_min: float,
    scale_max: float,
    bleed: float,
    shadow: bool,
    text_safe_pos: Optional[str] = None,
) -> None:
    rng = random.Random(seed)
    tiles: List[Tuple[float, Image.Image, int, int]] = []
    n = max(1, len(paths))
    base = max(96, int((w * h / n) ** 0.5 * 1.72))

    for p in paths:
        try:
            with Image.open(p).convert("RGB") as im0:
                im = im0.copy()
        except Exception:
            _note_skipped_runtime()
            continue

        ar = im.width / max(im.height, 1)
        sc = rng.uniform(scale_min, scale_max)
        long_side = max(32, int(base * sc))
        if ar >= 1:
            nw, nh = long_side, max(1, int(long_side / ar))
        else:
            nh, nw = long_side, max(1, int(long_side * ar))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        ang = rng.uniform(-rotation_deg, rotation_deg)
        rot = im.rotate(
            ang,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor=bg_color,
        )
        rw, rh = rot.size
        mx = int(w * bleed)
        my = int(h * bleed)
        # 留白规则：给文本角位留出“安全区”，降低核心元素压字概率
        sx0 = sy0 = sx1 = sy1 = None
        if text_safe_pos in ("top_left", "top_right", "bottom_left", "bottom_right"):
            safe_w = int(w * 0.34)
            safe_h = int(h * 0.24)
            pad = int(min(w, h) * 0.03)
            if text_safe_pos == "top_left":
                sx0, sy0, sx1, sy1 = pad, pad, pad + safe_w, pad + safe_h
            elif text_safe_pos == "top_right":
                sx0, sy0, sx1, sy1 = w - pad - safe_w, pad, w - pad, pad + safe_h
            elif text_safe_pos == "bottom_left":
                sx0, sy0, sx1, sy1 = pad, h - pad - safe_h, pad + safe_w, h - pad
            elif text_safe_pos == "bottom_right":
                sx0, sy0, sx1, sy1 = w - pad - safe_w, h - pad - safe_h, w - pad, h - pad

        cx = rng.uniform(-mx, w + mx)
        cy = rng.uniform(-my, h + my)
        if sx0 is not None:
            for _ in range(8):
                if sx0 <= cx <= sx1 and sy0 <= cy <= sy1:
                    cx = rng.uniform(-mx, w + mx)
                    cy = rng.uniform(-my, h + my)
                else:
                    break
        x = int(cx - rw / 2)
        y = int(cy - rh / 2)
        tiles.append((rng.random(), rot, x, y))

    tiles.sort(key=lambda t: t[0])
    for _z, rot, x, y in tiles:
        if shadow:
            _paste_tile_shadow(wallpaper, rot, x, y, with_shadow=True)
        else:
            wallpaper.paste(rot, (x, y))

def _rect_overlap(
    ax: int,
    ay: int,
    aw: int,
    ah: int,
    bx: int,
    by: int,
    bw: int,
    bh: int,
    pad: int = 0,
) -> bool:
    return not (
        ax + aw + pad <= bx
        or bx + bw + pad <= ax
        or ay + ah + pad <= by
        or by + bh + pad <= ay
    )

def _place_tile_constrained(
    wallpaper: Image.Image,
    img: Image.Image,
    x: int,
    y: int,
    *,
    with_shadow: bool,
    placed: List[Tuple[int, int, int, int]],
    w: int,
    h: int,
    rng: random.Random,
    min_visible: float = 0.52,
    max_overlap: float = 0.68,
    max_tries: int = 14,
    jitter_px: int = 32,
) -> bool:
    """统一稳定性底座：可见面积 + 重叠阈值 + 抖动重试 + 回退落位。"""
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return False
    prof = _style_profile()
    min_visible = max(0.25, min(0.95, float(min_visible) * prof["visible"]))
    max_overlap = max(0.08, min(0.95, float(max_overlap) * prof["overlap"]))
    max_tries = max(4, int(max_tries * (0.9 + prof["jitter"] * 0.3)))
    jitter_px = max(8, int(jitter_px * prof["jitter"]))

    def _visible_ratio(px: int, py: int) -> float:
        x0 = max(px, 0)
        y0 = max(py, 0)
        x1 = min(px + iw, w)
        y1 = min(py + ih, h)
        inter = max(0, x1 - x0) * max(0, y1 - y0)
        return inter / float(iw * ih)

    def _max_overlap_ratio(px: int, py: int) -> float:
        if not placed:
            return 0.0
        best = 0.0
        a0 = iw * ih
        for bx, by, bw, bh in placed:
            ix0 = max(px, bx)
            iy0 = max(py, by)
            ix1 = min(px + iw, bx + bw)
            iy1 = min(py + ih, by + bh)
            inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            if inter <= 0:
                continue
            den = max(1, min(a0, bw * bh))
            best = max(best, inter / float(den))
        return best

    best_xy = (x, y)
    best_score = -1e9
    tried: List[Tuple[int, int]] = [(x, y)]
    for i in range(max_tries):
        if i == 0:
            px, py = x, y
        else:
            px = x + rng.randint(-jitter_px, jitter_px)
            py = y + rng.randint(-jitter_px, jitter_px)
            tried.append((px, py))
        vr = _visible_ratio(px, py)
        ov = _max_overlap_ratio(px, py)
        score = vr - ov * 0.65
        if score > best_score:
            best_score = score
            best_xy = (px, py)
        if vr >= min_visible and ov <= max_overlap:
            _paste_tile_shadow(wallpaper, img, px, py, with_shadow=with_shadow)
            placed.append((px, py, iw, ih))
            return True

    px, py = best_xy
    vr = _visible_ratio(px, py)
    if vr < 0.34:
        # 回退：尽量把图放回画布内，避免“几乎整张不可见”
        px = max(0, min(px, max(0, w - iw)))
        py = max(0, min(py, max(0, h - ih)))
        vr = _visible_ratio(px, py)
    if vr >= 0.34:
        _paste_tile_shadow(wallpaper, img, px, py, with_shadow=with_shadow)
        placed.append((px, py, iw, ih))
        return True
    return False

def _paste_rotated_center(
    wallpaper: Image.Image,
    im: Image.Image,
    cx: float,
    cy: float,
    angle_deg: float,
    fill: Tuple[int, int, int],
    *,
    with_shadow: bool,
) -> None:
    rot = im.rotate(
        angle_deg,
        expand=True,
        resample=Image.Resampling.BICUBIC,
        fillcolor=fill,
    )
    x = int(cx - rot.width / 2)
    y = int(cy - rot.height / 2)
    _paste_tile_shadow(wallpaper, rot, x, y, with_shadow=with_shadow)

def _paste_stack_strong(
    wallpaper: Image.Image,
    im: Image.Image,
    x: int,
    y: int,
) -> None:
    pad = max(18, min(im.size) // 6)
    shadow = Image.new(
        "RGBA",
        (im.width + pad * 2, im.height + pad * 2),
        (0, 0, 0, 0),
    )
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rectangle(
        [pad, pad, pad + im.width - 1, pad + im.height - 1],
        fill=(0, 0, 0, 85),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    wallpaper.paste(shadow, (x - pad + 14, y - pad + 18), shadow)
    wallpaper.paste(im, (x, y))

def _masonry_in_box(
    wallpaper: Image.Image,
    paths: Sequence[str],
    box: Tuple[int, int, int, int],
    gap: int,
    rng: random.Random,
    preprocess=None,
) -> None:
    left, top, right, bottom = box
    rw = right - left
    if rw < 40 or not paths:
        return
    cols_n = max(2, min(6, rw // max(72, rw // 5)))
    col_w = max(28, (rw - (cols_n - 1) * gap) // cols_n)
    col_y = [top] * cols_n
    order = list(range(len(paths)))
    rng.shuffle(order)
    for oi in order:
        p = paths[oi]
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                if preprocess:
                    im = preprocess(im)
                ar = im.width / max(im.height, 1)
                nh = max(3, int(col_w / ar))
                tile = im.resize((col_w, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        ci = min(range(cols_n), key=lambda j: col_y[j])
        x = left + ci * (col_w + gap)
        y = col_y[ci]
        if y + tile.height > bottom + gap:
            continue
        _paste_tile_shadow(wallpaper, tile, x, y, with_shadow=True)
        col_y[ci] = y + tile.height + gap

def _render_focus(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    if not paths:
        return
    hero_path = paths[0]
    small_paths = list(paths[1:])
    hw = int(min(w, h) * 0.48)
    hero: Optional[Image.Image] = None
    try:
        with Image.open(hero_path).convert("RGB") as im0:
            im = im0.copy()
            ar = im.width / max(im.height, 1)
            if ar >= 1:
                nh = int(hw / ar)
                hero = im.resize((hw, nh), Image.Resampling.LANCZOS)
            else:
                nh = hw
                nw = max(1, int(hw * ar))
                hero = im.resize((nw, nh), Image.Resampling.LANCZOS)
    except Exception:
        _note_skipped_runtime()
        return
    assert hero is not None
    hcx, hcy = w / 2, h / 2
    hx0 = int(hcx - hero.width / 2)
    hy0 = int(hcy - hero.height / 2)
    hero_ang = rng.uniform(-4.0, 4.0)
    hero_rot = hero.rotate(
        hero_ang,
        expand=True,
        resample=Image.Resampling.BICUBIC,
        fillcolor=fill,
    )
    hx = int(hcx - hero_rot.width / 2)
    hy = int(hcy - hero_rot.height / 2)
    hero_bbox = (hx, hy, hero_rot.width, hero_rot.height)

    placed: List[Tuple[int, int, int, int]] = [hero_bbox]

    for p in small_paths:
        try:
            with Image.open(p).convert("RGB") as im0:
                sm = im0.copy()
        except Exception:
            _note_skipped_runtime()
            continue
        side = int(min(w, h) * rng.uniform(0.09, 0.15))
        ar = sm.width / max(sm.height, 1)
        if ar >= 1:
            sw = side
            sh = max(1, int(side / ar))
        else:
            sh = side
            sw = max(1, int(side * ar))
        sm = sm.resize((sw, sh), Image.Resampling.LANCZOS)
        ang = rng.uniform(-18.0, 18.0)
        rot = sm.rotate(
            ang, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=fill
        )
        rw, rh = rot.size
        rmid = max(hero_bbox[2], hero_bbox[3]) // 2 + min(w, h) // 10
        rmax = int(min(w, h) * 0.48)
        ok = False
        for _ in range(36):
            t = rng.uniform(0, math.tau)
            r = rng.uniform(rmid, rmax)
            cx = hcx + math.cos(t) * r
            cy = hcy + math.sin(t) * r
            x = int(cx - rw / 2)
            y = int(cy - rh / 2)
            clash = False
            for px, py, pw, ph in placed:
            
                if _rect_overlap(x, y, rw, rh, px, py, pw, ph, pad=12):
                    clash = True
                    break
            if (
                not clash
                and x > -rw // 3
                and y > -rh // 3
                and x + rw < w + rw // 3
                and y + rh < h + rh // 3
            ):
                _paste_tile_shadow(wallpaper, rot, x, y, with_shadow=True)
                placed.append((x, y, rw, rh))
                ok = True
                break
        if not ok:
            xb = max(8, w - rw - 8)
            yb = max(8, h - rh - 8)
            x = rng.randint(8, xb) if xb >= 8 else 8
            y = rng.randint(8, yb) if yb >= 8 else 8
            _paste_tile_shadow(wallpaper, rot, x, y, with_shadow=True)

    _paste_stack_strong(wallpaper, hero_rot, hx, hy)

def _render_diagonal_flow(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    margin: int,
    fill: Tuple[int, int, int],
    gap: int,
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    sx, sy = float(margin), float(h - margin)
    ex, ey = float(w - margin), float(margin)
    dx, dy = ex - sx, ey - sy
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L

    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im0:
                im = im0.copy()
        except Exception:
            _note_skipped_runtime()
            continue
        t = 0.5 if n <= 1 else (i + 0.5) / n
        px = sx + t * (ex - sx)
        py = sy + t * (ey - sy)
        off = (i - (n - 1) / 2.0) * (6.0 + gap * 0.12)
        px += nx * off
        py += ny * off
        prog = i / max(n - 1, 1) if n > 1 else 0.5
        size_scale = 0.38 + 0.62 * prog
        base = min(w, h) * 0.17 * size_scale
        ar = im.width / max(im.height, 1)
        if ar >= 1:
            nw = max(24, int(base * ar))
            nh = max(24, int(base))
            im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        else:
            nh = max(24, int(base))
            nw = max(24, int(base * ar))
            im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        ang = math.degrees(math.sin(i * 0.55) * 0.22) + rng.uniform(-5.0, 5.0)
        _paste_rotated_center(wallpaper, im, px, py, ang, fill, with_shadow=True)

def _render_masonry(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    margin: int,
    gap: int,
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    box = (margin, margin, w - margin, h - margin)
    _masonry_in_box(wallpaper, paths, box, gap, rng)

def _render_fan(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    margin: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
    rotation_deg: float = 14.0
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    cx = w * 0.5 + rng.uniform(-min(w, h) * 0.02, min(w, h) * 0.02)
    cy = h - margin * 0.35
    ang0, ang1 = math.radians(-56), math.radians(56)
    r0 = min(w, h) * 0.22
    r1 = min(w, h) * 0.82

    layers: List[Tuple[float, Image.Image, int, int]] = []
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im0:
                im = im0.copy()
        except Exception:
            _note_skipped_runtime()
            continue
        t = i / max(n - 1, 1) if n > 1 else 0.5
        theta = ang0 + t * (ang1 - ang0) + rng.uniform(-0.05, 0.05)
        r = r0 + t * (r1 - r0)
        icx = cx + r * math.sin(theta)
        icy = cy - r * math.cos(theta)
        mh = int(h * (0.11 + 0.1 * t))
        ar = im.width / max(im.height, 1)
        nw = max(20, int(mh * ar))
        nh = mh
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        rot_deg = math.degrees(theta) + rng.uniform(-rotation_deg, rotation_deg)
        rot = im.rotate(
            rot_deg,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor=fill,
        )
        x = int(icx - rot.width / 2)
        y = int(icy - rot.height / 2)
        layers.append((t + rng.random() * 0.01, rot, x, y))
    layers.sort(key=lambda x: x[0])
    for _d, rot, x, y in layers:
        _paste_tile_shadow(wallpaper, rot, x, y, with_shadow=True)

def _render_stack(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    use = list(paths)[-min(28, len(paths)) :]
    n = len(use)
    if n == 0:
        return
    cw = int(min(w, h) * 0.24)
    dx = 15 + rng.randint(0, 6)
    dy = 11 + rng.randint(0, 5)
    d_ang = 2.2 + rng.random() * 0.8
    base_x = w // 2 - cw // 2 - (n - 1) * dx // 2 + rng.randint(-8, 8)
    base_y = h // 2 - int(cw * 1.35) // 2 - (n - 1) * dy // 2 + rng.randint(-10, 10)

    for i, p in enumerate(use):
        try:
            with Image.open(p).convert("RGB") as im0:
                im = im0.copy()
        except Exception:
            _note_skipped_runtime()
            continue
        im.thumbnail((cw + 20, int(cw * 1.55)), Image.Resampling.LANCZOS)
        ang = (i - (n - 1) * 0.5) * d_ang + rng.uniform(-1.2, 1.2)
        rot = im.rotate(
            ang,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor=fill,
        )
        x = base_x + i * dx
        y = base_y + i * dy
        _paste_stack_strong(wallpaper, rot, x, y)

def _render_split(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    margin: int,
    gap: int,
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    mid = w // 2
    g2 = max(4, gap)
    left_box = (margin, margin, mid - g2 // 2, h - margin)
    right_box = (mid + g2 // 2, margin, w - margin, h - margin)
    n = len(paths)
    if n == 0:
        return
    left_n = (n + 1) // 2
    left_paths = paths[:left_n]
    right_paths = paths[left_n:]

    def bright(im: Image.Image) -> Image.Image:
        return ImageEnhance.Brightness(im).enhance(1.09)

    def gray(im: Image.Image) -> Image.Image:
        return ImageOps.grayscale(im).convert("RGB")

    _masonry_in_box(wallpaper, left_paths, left_box, gap, rng, bright)
    _masonry_in_box(wallpaper, right_paths, right_box, gap, rng, gray)
    draw = ImageDraw.Draw(wallpaper)
    mx = int(mid)
    draw.line([mx, margin, mx, h - margin], fill=(220, 220, 224), width=max(1, g2 // 2))
# ====================== 新增：W型波浪排版 ======================

def _render_w_shape(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    placed: List[Tuple[int, int, int, int]] = []

    base_size = int(min(w, h) * 0.18)
    cy_mid = h // 2
    amp = h * 0.12

    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width / im.height
                nw = base_size
                nh = int(base_size / ar)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue

        t = i / max(n-1, 1) if n>1 else 0.5
        x = int(80 + t * (w - 160))
        phase = t * math.pi * 2
        y_offset = int(math.sin(phase) * amp)
        y = cy_mid + y_offset - nh//2
        ang = rng.uniform(-3, 3)
        rot = im.rotate(ang, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=fill)
        _place_tile_constrained(
            wallpaper,
            rot,
            x - rot.width // 2,
            y - rot.height // 2,
            with_shadow=True,
            placed=placed,
            w=w,
            h=h,
            rng=rng,
        )

# ====================== V型 ======================

def _render_v_shape(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    placed: List[Tuple[int, int, int, int]] = []
    cx = w // 2
    base_y = h - 120
    size = int(min(w, h) * 0.16)
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width / im.height
                if ar >= 1:
                    nw, nh = size, int(size / ar)
                else:
                    nw, nh = int(size * ar), size
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        t = i / max(n-1, 1) if n > 1 else 0.5
        x = int(80 + t * (w - 160))
        y = base_y - int(abs(x - cx) / cx * h * 0.4)
        ang = rng.uniform(-2, 2)
        rot = im.rotate(ang, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=fill)
        _place_tile_constrained(
            wallpaper,
            rot,
            x - rot.width // 2,
            y - rot.height // 2,
            with_shadow=True,
            placed=placed,
            w=w,
            h=h,
            rng=rng,
        )

# ====================== 弧形 / 半圆 ======================

def _render_arc(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    placed: List[Tuple[int, int, int, int]] = []
    cx, cy = w//2, int(h*0.6)
    r = w//3
    size = int(min(w,h)*0.15)
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width / im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        ang = math.radians(135 - i/(n-1)*90 if n>1 else 135)
        x = cx + int(r * math.cos(ang))
        y = cy - int(r * math.sin(ang))
        rot = im.rotate(0, expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper,
            rot,
            x - rot.width // 2,
            y - rot.height // 2,
            with_shadow=True,
            placed=placed,
            w=w,
            h=h,
            rng=rng,
        )

# ====================== 十字中心扩散 ======================

def _render_cross(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    placed: List[Tuple[int, int, int, int]] = []
    cx, cy = w//2, h//2
    size = int(min(w,h)*0.14)
    step = 160
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width / im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        d = (i//4 +1)*step
        slot = i%4
        if slot ==0: x,y = cx+d, cy
        elif slot ==1: x,y = cx-d, cy
        elif slot ==2: x,y = cx, cy+d
        else: x,y = cx, cy-d
        rot = im.rotate(rng.uniform(-2,2), expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper,
            rot,
            x - rot.width // 2,
            y - rot.height // 2,
            with_shadow=True,
            placed=placed,
            w=w,
            h=h,
            rng=rng,
        )

# ====================== 左右对称翼型 ======================

def _render_wing(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    placed: List[Tuple[int, int, int, int]] = []
    m = min(w, h)
    cx = w // 2
    # 参数自适应：数量越多，左右翼收拢、纵向步长减小，避免越界与过密
    off = int(max(80, min(w * 0.32, m * (0.24 - min(n, 24) * 0.0035))))
    y_top = int(max(24, h * 0.08))
    y_bottom = int(min(h - 28, h * 0.9))
    y_step = (y_bottom - y_top) / max(1, n - 1) if n > 1 else 0.0
    size = int(m * max(0.11, 0.18 - min(n, 24) * 0.002))
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width / im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        y = int(y_top + i * y_step) if n > 1 else h // 2
        ang = rng.uniform(-2.5, 2.5)
        rot = im.rotate(ang, expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper,
            rot,
            cx - off - rot.width // 2,
            y,
            with_shadow=True,
            placed=placed,
            w=w,
            h=h,
            rng=rng,
        )
        _place_tile_constrained(
            wallpaper,
            rot,
            cx + off - rot.width // 2,
            y,
            with_shadow=True,
            placed=placed,
            w=w,
            h=h,
            rng=rng,
        )


# ====================== 整齐排满心形（和你图片一模一样） ======================

def _render_heart(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    placed: List[Tuple[int, int, int, int]] = []

    # 核心：完全按你图片的「心形轮廓 + 整齐排列」来排布
    cx = w // 2
    cy = h // 2 + int(h * 0.05)
    size = int(min(w, h) * 0.135)   # 杂志大小
    radius = int(min(w, h) * 0.38)  # 心形整体大小

    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width / im.height
                # 保持杂志竖版
                nw = size
                nh = int(size / ar)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue

        t = i / max(n - 1, 1)
        angle = math.pi * t * 2

        # ✅ 标准心形公式（和你图片轮廓 100% 匹配）
        x_offset = int(16 * math.sin(angle) **3 * radius / 14)
        y_offset = -int(
            13 * math.cos(angle)
            - 5 * math.cos(2*angle)
            - 2 * math.cos(3*angle)
            - math.cos(4*angle)
        ) * radius // 14

        x = cx + x_offset
        y = cy + y_offset

        # ✅ 几乎不旋转，完全对齐你图片的整齐感
        ang = rng.uniform(-1.0, 1.0)

        rot = im.rotate(
            ang,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor=fill
        )
        px = int(x - rot.width / 2)
        py = int(y - rot.height / 2)
        _place_tile_constrained(
            wallpaper,
            rot,
            px,
            py,
            with_shadow=True,
            placed=placed,
            w=w,
            h=h,
            rng=rng,
        )
# ====================== 圆形环绕 ======================

def _render_circle(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    placed: List[Tuple[int, int, int, int]] = []
    cx, cy = w//2, h//2
    r = int(min(w,h)*0.35)
    size = int(min(w,h)*0.14)
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width / im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        ang = 2*math.pi * i/n
        x = cx + int(r*math.cos(ang))
        y = cy + int(r*math.sin(ang))
        rot = im.rotate(math.degrees(ang)+rng.uniform(-3,3), expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper,
            rot,
            x - rot.width // 2,
            y - rot.height // 2,
            with_shadow=True,
            placed=placed,
            w=w,
            h=h,
            rng=rng,
        )

# ====================== S 型 ======================

def _render_s_shape(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    placed: List[Tuple[int, int, int, int]] = []
    cx = w//2
    size = int(min(w,h)*0.16)
    amp = h//4
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width / im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        t = i/(n-1) if n>1 else 0.5
        x = int(80 + t*(w-160))
        y = h//2 + int(math.sin(t*math.pi*2)*amp)
        ang = rng.uniform(-3,3)
        rot = im.rotate(ang, expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper,
            rot,
            x - rot.width // 2,
            y - rot.height // 2,
            with_shadow=True,
            placed=placed,
            w=w,
            h=h,
            rng=rng,
        )

# ====================== 斜排文字流 ======================

def _render_text_flow(
    wallpaper: Image.Image,
    paths: Sequence[str],
    w: int,
    h: int,
    fill: Tuple[int, int, int],
    *,
    seed: Optional[int],
) -> None:
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    placed: List[Tuple[int, int, int, int]] = []
    m = min(w, h)
    # 参数自适应：把「斜排文字流」约束在可视安全区，并按数量调整步长
    x_pad = int(max(36, w * 0.08))
    y_pad = int(max(28, h * 0.08))
    x0, y0 = x_pad, y_pad
    x1 = int(max(x_pad + 1, w - x_pad))
    y1 = int(max(y_pad + 1, h - y_pad))
    step_x = (x1 - x0) / max(1, n - 1) if n > 1 else 0.0
    step_y = (y1 - y0) / max(1, n - 1) if n > 1 else 0.0
    size = int(m * max(0.11, 0.16 - min(n, 28) * 0.0018))
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width / im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        x = int(x0 + i * step_x) if n > 1 else w // 2
        y = int(y0 + i * step_y) if n > 1 else h // 2
        ang = rng.uniform(-4.5, 4.5)
        rot = im.rotate(ang, expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper,
            rot,
            x - rot.width // 2,
            y - rot.height // 2,
            with_shadow=True,
            placed=placed,
            w=w,
            h=h,
            rng=rng,
        )


# ====================== 增强版文字绘制（3.0） ======================

def _norm_corner_pos(pos: str) -> str:
    if pos in ("top_left", "top_right", "bottom_left", "bottom_right", "center"):
        return pos
    return "bottom_right"

def _opposite_corner(pos: str) -> str:
    """与格言左右对侧：仅水平镜像（上左↔上右，下左↔下右），不对角。"""
    return {
        "top_left": "top_right",
        "top_right": "top_left",
        "bottom_left": "bottom_right",
        "bottom_right": "bottom_left",
        "center": "center",
    }.get(_norm_corner_pos(pos), "bottom_left")

def _bbox_tl(
    w: int, h: int, tw: int, th: int, pad: int, pos: str
) -> tuple[int, int]:
    """返回左上角坐标 (x,y)，使文本块落在 pos 所指角/居中。"""
    pos = _norm_corner_pos(pos)
    if pos == "top_left":
        return pad, pad
    if pos == "top_right":
        return w - tw - pad, pad
    if pos == "bottom_left":
        return pad, h - th - pad
    if pos == "center":
        return (w - tw) // 2, (h - th) // 2
    return w - tw - pad, h - th - pad

def draw_custom_text(
    wallpaper,
    text: str,
    stamp: str,
    text_size: int = 60,
    stamp_size: int = 42,
    text_pos: str = "bottom_right",
    stamp_pos: str = "bottom_left",
    text_color: tuple = (255, 255, 255),
    stroke_color: tuple = (0, 0, 0),
    stamp_place: str = "same_above",
):
    """格言 + 时间戳。stamp_place: same_above | opposite | center（见界面「戳位置」）。"""
    _ = stamp_pos
    w, h = wallpaper.size
    draw = ImageDraw.Draw(wallpaper)

    font_text = get_text_font(text_size)
    font_stamp = get_text_font(stamp_size)

    t_str = text.strip()
    s_str = stamp.strip()
    if not t_str and not s_str:
        return

    pad = 60
    line_gap = 10

    def dims(s: str, font) -> tuple[int, int, int, int]:
        return draw.textbbox((0, 0), s, font=font)

    tw = th = sw = sh = 0
    if t_str:
        l, t, r, b = dims(t_str, font_text)
        tw, th = r - l, b - t
    if s_str:
        l, t, r, b = dims(s_str, font_stamp)
        sw, sh = r - l, b - t

    side = _norm_corner_pos(text_pos)
    sp = stamp_place if stamp_place in ("same_above", "opposite", "center") else "same_above"
    if sp == "opposite" and side == "center":
        sp = "same_above"

    xt = yt = xs = ys = 0

    if sp == "same_above":
        if side == "top_left":
            if t_str and s_str:
                xt, yt = pad, pad
                xs, ys = pad, pad + th + line_gap
            elif t_str:
                xt, yt = pad, pad
            else:
                xs, ys = pad, pad
        elif side == "top_right":
            if t_str and s_str:
                xt, yt = w - tw - pad, pad
                xs, ys = w - sw - pad, pad + th + line_gap
            elif t_str:
                xt, yt = w - tw - pad, pad
            else:
                xs, ys = w - sw - pad, pad
        elif side == "bottom_left":
            if t_str and s_str:
                ys = h - pad - sh
                yt = ys - line_gap - th
                xt = xs = pad
            elif t_str:
                xt, yt = pad, h - th - pad
            else:
                xs, ys = pad, h - sh - pad
        elif side == "center":
            if t_str and s_str:
                stack_h = th + line_gap + sh
                yt = (h - stack_h) // 2
                ys = yt + th + line_gap
                xt = (w - tw) // 2
                xs = (w - sw) // 2
            elif t_str:
                xt, yt = (w - tw) // 2, (h - th) // 2
            else:
                xs, ys = (w - sw) // 2, (h - sh) // 2
        else:
            if t_str and s_str:
                ys = h - pad - sh
                yt = ys - line_gap - th
                xt = w - tw - pad
                xs = w - sw - pad
            elif t_str:
                xt, yt = w - tw - pad, h - th - pad
            else:
                xs, ys = w - sw - pad, h - sh - pad
    elif sp == "opposite":
        if t_str:
            xt, yt = _bbox_tl(w, h, tw, th, pad, side)
        if s_str:
            xs, ys = _bbox_tl(w, h, sw, sh, pad, _opposite_corner(side))
    else:
        if t_str:
            xt, yt = _bbox_tl(w, h, tw, th, pad, side)
        if s_str:
            xs, ys = _bbox_tl(w, h, sw, sh, pad, "center")

    if t_str:
        draw.text(
            (xt, yt),
            t_str,
            font=font_text,
            fill=text_color,
            stroke_width=3,
            stroke_fill=stroke_color,
        )
    if s_str:
        draw.text(
            (xs, ys),
            s_str,
            font=font_stamp,
            fill=text_color,
            stroke_width=2,
            stroke_fill=stroke_color,
        )
# ====================== 高级感排版合集 ======================

# 1. 极简居中对称（大牌高级感）

def _render_centered(wallpaper, paths, w, h, fill, *, seed=None):
    rng = random.Random(seed)
    cx, cy = w//2, h//2
    size = int(min(w,h)*0.16)
    placed: List[Tuple[int, int, int, int]] = []
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width/im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        d = i * 90
        ang = rng.uniform(-1,1)
        rot = im.rotate(ang, expand=True, fillcolor=fill)
        x = cx - rot.width//2
        y = cy + d - rot.height//2
        _place_tile_constrained(
            wallpaper, rot, x, y,
            with_shadow=True, placed=placed, w=w, h=h, rng=rng
        )

# 2. 左对齐留白（杂志高级留白）

def _render_left_white(wallpaper, paths, w, h, fill, *, seed=None):
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    m = min(w, h)
    # 左留白：数量越多，单卡尺寸略缩，纵向步长自适应，保持左侧序列感
    left_pad = int(max(36, w * 0.07))
    top_pad = int(max(24, h * 0.09))
    bottom_pad = int(max(24, h * 0.1))
    y_span = max(1, h - top_pad - bottom_pad)
    step = y_span / max(1, n - 1) if n > 1 else 0.0
    drift_x = int(max(10, w * 0.012))
    size = int(m * max(0.1, 0.16 - min(n, 28) * 0.0019))
    placed: List[Tuple[int, int, int, int]] = []
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width/im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        x = int(left_pad + i * drift_x)
        y = int(top_pad + i * step) if n > 1 else h // 2
        ang = rng.uniform(-2,2)
        rot = im.rotate(ang, expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper, rot, x, y,
            with_shadow=True, placed=placed, w=w, h=h, rng=rng
        )

# 3. 三角稳定构图（高级平衡）

def _render_triangle(wallpaper, paths, w, h, fill, *, seed=None):
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    m = min(w, h)
    cx = w // 2
    y1 = int(max(24, h * 0.18))
    y2 = h // 2
    y3 = int(min(h - 24, h * 0.82))
    x_spread = int(max(70, min(w * 0.24, m * 0.34)))
    size = int(m * max(0.1, 0.16 - min(n, 26) * 0.002))
    placed: List[Tuple[int, int, int, int]] = []
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width/im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        mode = i%3
        if mode == 0:
            x, y = cx, y1
        elif mode == 1:
            x, y = cx - x_spread, y2
        else:
            x, y = cx + x_spread, y3
        rot = im.rotate(rng.uniform(-1,1), expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper, rot, x - rot.width // 2, y - rot.height // 2,
            with_shadow=True, placed=placed, w=w, h=h, rng=rng
        )

# 4. 螺旋环绕（艺术感）

def _render_spiral(wallpaper, paths, w, h, fill, *, seed=None):
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    m = min(w, h)
    cx, cy = w // 2, h // 2
    # 参数自适应：密图时缩小尺寸并减缓半径增长，避免螺旋外圈爆出画布
    size = int(m * max(0.085, 0.145 - min(n, 44) * 0.00125))
    r0 = m * 0.08
    r1 = m * 0.42
    turns = 1.25 + min(2.1, n * 0.05)
    placed: List[Tuple[int, int, int, int]] = []
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width/im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        t = i / max(1, n - 1) if n > 1 else 0.5
        r = r0 + t * (r1 - r0)
        ang = turns * math.tau * t + rng.uniform(-0.06, 0.06)
        x = cx + int(r*math.cos(ang))
        y = cy + int(r*math.sin(ang))
        rot = im.rotate(math.degrees(ang) + rng.uniform(-2.0, 2.0), expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper, rot, x - rot.width // 2, y - rot.height // 2,
            with_shadow=True, placed=placed, w=w, h=h, rng=rng
        )

# 5. 对角线双飞（电影感）

def _render_diag_two(wallpaper, paths, w, h, fill, *, seed=None):
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    m = min(w, h)
    size = int(m * max(0.11, 0.17 - min(n, 30) * 0.0019))
    placed: List[Tuple[int, int, int, int]] = []
    x_pad = int(max(40, w * 0.11))
    y_top = int(max(30, h * 0.09))
    y_bottom = int(min(h - 30, h * 0.88))
    y_step = (y_bottom - y_top) / max(1, n - 1) if n > 1 else 0.0
    amp = int(max(26, w * 0.06))
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width/im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        y = int(y_top + i * y_step) if n > 1 else h // 2
        if i % 2 == 0:
            t = i / max(1, n - 1)
            x = int(x_pad + t * (w - 2 * x_pad) - amp * 0.42)
        else:
            t = i / max(1, n - 1)
            x = int(w - x_pad - t * (w - 2 * x_pad) + amp * 0.42)
        rot = im.rotate(rng.uniform(-2,2), expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper, rot, x - rot.width // 2, y - rot.height // 2,
            with_shadow=True, placed=placed, w=w, h=h, rng=rng
        )

# 6. 上下分层极简（大牌海报）

def _render_layer(wallpaper, paths, w, h, fill, *, seed=None):
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    m = min(w, h)
    cx = w // 2
    y1 = int(h * 0.34)
    y2 = int(h * 0.68)
    size = int(m * max(0.09, 0.18 - min(n, 42) * 0.0018))
    # 参数自适应：按数量调节层内横向扩散，避免“左右两端跑飞”
    spread = int(max(36, min(w * 0.23, m * (0.24 - min(n, 28) * 0.0032))))
    placed: List[Tuple[int, int, int, int]] = []
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width/im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        y = y1 if i%2==0 else y2
        k = i // 2
        side = 1 if i % 4 < 2 else -1
        x = cx + side * int((k + 0.2) * spread * 0.42)
        rot = im.rotate(rng.uniform(-1,1), expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper, rot, x - rot.width // 2, y - rot.height // 2,
            with_shadow=True, placed=placed, w=w, h=h, rng=rng
        )

# 7. 六边形蜂窝（精致高级）

def _render_honeycomb(wallpaper, paths, w, h, fill, *, seed=None):
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    m = min(w, h)
    cx, cy = w // 2, h // 2
    size = int(m * max(0.085, 0.14 - min(n, 40) * 0.0014))
    dx = int(max(34, size * 0.95))
    dy = int(max(28, size * 0.78))
    grid = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,0),(0,1),(1,-1),(1,0),(1,1)]
    placed: List[Tuple[int, int, int, int]] = []
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width/im.height
                nw, nh = (size, int(size/ar)) if ar>=1 else (int(size*ar), size)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        gx, gy = grid[i % len(grid)]
        row = i // len(grid)
        y_row_shift = int(row * dy * 0.9)
        x_row_shift = int((row % 2) * dx * 0.5)
        x = cx + gx * dx + x_row_shift
        y = cy + gy * dy + y_row_shift
        rot = im.rotate(0, expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper, rot, x - rot.width // 2, y - rot.height // 2,
            with_shadow=True, placed=placed, w=w, h=h, rng=rng
        )

# 8. 渐隐散点（高级氛围感）

def _render_fade(wallpaper, paths, w, h, fill, *, seed=None):
    rng = random.Random(seed)
    n = len(paths)
    if n == 0:
        return
    m = min(w, h)
    cx, cy = w // 2, h // 2
    base = int(m * max(0.09, 0.2 - min(n, 44) * 0.0019))
    r0 = m * 0.05
    r1 = m * 0.48
    turns = 1.05 + min(1.7, n * 0.04)
    placed: List[Tuple[int, int, int, int]] = []
    for i, p in enumerate(paths):
        try:
            with Image.open(p).convert("RGB") as im:
                ar = im.width/im.height
                s = int(base * (1.0 - i / max(1, n) * 0.52))
                nw, nh = (s, int(s/ar)) if ar>=1 else (int(s*ar), s)
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        except Exception:
            _note_skipped_runtime()
            continue
        t = i / max(n - 1, 1) if n > 1 else 0.5
        r = r0 + t * (r1 - r0)
        ang = turns * math.tau * t + rng.uniform(-0.08, 0.08)
        x = cx + int(r*math.cos(ang))
        y = cy + int(r*math.sin(ang))
        rot = im.rotate(rng.uniform(-2.5,2.5), expand=True, fillcolor=fill)
        _place_tile_constrained(
            wallpaper, rot, x - rot.width // 2, y - rot.height // 2,
            with_shadow=True, placed=placed, w=w, h=h, rng=rng
        )

def _aesthetic_order_paths(paths: Sequence[str], seed: Optional[int]) -> List[str]:
    """
    审美一致性规则（主次 + 节奏）：
    - 主次：先挑“主图候选”放第一位（比例更协调、尺寸更有支撑）
    - 节奏：余图按视觉权重交错（大-小-大-小），减少一坨同质感
    """
    plist = list(paths)
    if len(plist) <= 2:
        return plist
    rng = random.Random(seed)
    metas: List[Tuple[str, float, float]] = []
    for p in plist:
        try:
            with Image.open(p) as im:
                w0, h0 = im.size
            ar = w0 / max(h0, 1)
            # 杂志壁纸常见审美：略竖或近方图做主图更稳
            ratio_score = 1.0 - min(1.0, abs(ar - 0.82))
            mass = math.sqrt(max(1.0, float(w0) * float(h0)))
            metas.append((p, ratio_score, mass))
        except Exception:
            metas.append((p, 0.3, 1.0))
    # 主图：比例优先，尺寸次之
    hero = max(metas, key=lambda x: (x[1], x[2]))[0]
    rest = [m for m in metas if m[0] != hero]
    rest.sort(key=lambda x: x[2], reverse=True)
    hi = rest[::2]
    lo = list(reversed(rest[1::2]))
    rhythm: List[str] = []
    i = j = 0
    while i < len(hi) or j < len(lo):
        if i < len(hi):
            rhythm.append(hi[i][0])
            i += 1
        if j < len(lo):
            rhythm.append(lo[j][0])
            j += 1
    # 小幅随机打散，避免模板味过重
    if len(rhythm) > 4:
        k = rng.randint(1, min(3, len(rhythm) - 1))
        rhythm = rhythm[k:] + rhythm[:k]
    return [hero] + rhythm

