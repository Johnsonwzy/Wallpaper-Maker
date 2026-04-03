"""背景叠层域（从 core.py 切分）。"""
from __future__ import annotations

import math
import random
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps


def _clip_u8(x: float) -> int:
    return max(0, min(255, int(round(x))))


def _radial_vignette_mask(w: int, h: int, strength: float) -> Image.Image:
    """L 通道：中心亮、边缘暗，用于压暗角。"""
    sw, sh = min(96, w), min(96, h)
    sw, sh = max(32, sw), max(32, sh)
    img = Image.new("L", (sw, sh))
    px = img.load()
    cx = (sw - 1) * 0.5
    cy = (sh - 1) * 0.5
    rmax = math.hypot(cx, cy) or 1.0
    for y in range(sh):
        for x in range(sw):
            d = math.hypot(x - cx, y - cy) / rmax
            d = min(1.0, d ** 1.18)
            v = int(255 * (1.0 - strength * d))
            px[x, y] = max(0, min(255, v))
    return img.resize((w, h), Image.Resampling.BILINEAR)


def _apply_edge_vignette(im: Image.Image, *, strength: float = 0.46) -> Image.Image:
    """暗角：边缘向黑色过渡。"""
    w, h = im.size
    mask = _radial_vignette_mask(w, h, strength)
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(im, dark, mask)


def _apply_frosted_overlay(im: Image.Image, *, seed: Optional[int]) -> Image.Image:
    """磨砂感：轻模糊叠层 + 细微颗粒。"""
    rng = random.Random(seed)
    w, h = im.size
    blur_r = max(0.6, min(w, h) / 640.0)
    soft = im.filter(ImageFilter.GaussianBlur(radius=blur_r))
    base = Image.blend(im, soft, 0.42)
    try:
        n = Image.effect_noise((w, h), rng.uniform(10, 20))
        n = n.convert("RGB")
        n = ImageOps.autocontrast(n, cutoff=0)
    except Exception:
        n = Image.new("RGB", (w, h), (248, 246, 242))
        dr = ImageDraw.Draw(n)
        step = max(6, min(w, h) // 100)
        for y in range(0, h, step):
            for x in range(0, w, step):
                g = 240 + rng.randint(-6, 6)
                dr.rectangle([x, y, x + step, y + step], fill=(g, g, g))
    return Image.blend(base, n, 0.065)


def _apply_geometric_texture(im: Image.Image, *, seed: Optional[int]) -> Image.Image:
    """几何纹理：低对比斜线 + 细点阵，与底图柔光混合。"""
    rng = random.Random(seed)
    w, h = im.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(overlay)
    lw = max(1, min(w, h) // 480)
    n_lines = 24 + rng.randint(0, 16)
    for _ in range(n_lines):
        x0 = rng.randint(-w // 3, w + w // 3)
        y0 = rng.randint(-h // 3, h + h // 3)
        ang = rng.uniform(-0.4, 0.4)
        ln = max(w, h)
        x1 = int(x0 + math.cos(ang) * ln)
        y1 = int(y0 + math.sin(ang) * ln)
        a = rng.randint(26, 62)
        dr.line([(x0, y0), (x1, y1)], fill=(255, 255, 255, a), width=lw)
    for _ in range(70 + rng.randint(0, 50)):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        r = rng.randint(1, 3)
        dr.ellipse(
            [x - r, y - r, x + r, y + r],
            fill=(255, 255, 255, rng.randint(14, 34)),
        )
    base = im.convert("RGBA")
    out = Image.alpha_composite(base, overlay)
    return out.convert("RGB")


def _apply_paper_grain_overlay(im: Image.Image, *, seed: Optional[int]) -> Image.Image:
    """纸张纹理：低对比纤维噪点，偏自然材质。"""
    rng = random.Random(seed)
    w, h = im.size
    n = Image.effect_noise((w, h), rng.uniform(6.0, 11.0)).convert("L")
    n = ImageOps.autocontrast(n, cutoff=3)
    nrgb = Image.merge("RGB", (n, n, n))
    tint = Image.new("RGB", (w, h), (246, 243, 236))
    grain = Image.blend(nrgb, tint, 0.72)
    return Image.blend(im, grain, 0.08)


def _apply_soft_bloom_overlay(im: Image.Image) -> Image.Image:
    """柔光雾化：亮部轻柔扩散，保留主体。"""
    glow = ImageEnhance.Brightness(im).enhance(1.18)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=6.0))
    out = Image.blend(im, glow, 0.36)
    return ImageEnhance.Contrast(out).enhance(0.96)


def _apply_cinematic_grade_overlay(im: Image.Image) -> Image.Image:
    """电影分级：轻青橙偏移，统一组图气质。"""
    r, g, b = im.split()
    r = r.point(lambda x: _clip_u8(x * 1.035 + 3))
    g = g.point(lambda x: _clip_u8(x * 1.00))
    b = b.point(lambda x: _clip_u8(x * 1.04 + 2))
    out = Image.merge("RGB", (r, g, b))
    out = ImageEnhance.Color(out).enhance(0.95)
    return ImageEnhance.Contrast(out).enhance(1.03)


def _apply_radial_focus_overlay(im: Image.Image) -> Image.Image:
    """中心聚光：中心微提亮，边缘微压暗。"""
    w, h = im.size
    mask = _radial_vignette_mask(w, h, 0.62)
    cen = ImageEnhance.Brightness(im).enhance(1.065)
    edge = ImageEnhance.Brightness(im).enhance(0.94)
    out = Image.composite(cen, edge, mask)
    return ImageEnhance.Contrast(out).enhance(1.02)


def apply_bg_overlay_impl(
    im: Image.Image,
    overlay_style: str,
    *,
    seed: Optional[int],
    strength: float,
) -> Image.Image:
    osk = (overlay_style or "none").strip().lower()
    if osk in ("", "none", "off") or strength <= 0.0:
        return im
    if osk == "frosted_glass":
        full = _apply_frosted_overlay(im, seed=seed)
        return Image.blend(im, full, min(1.0, strength * 1.18))
    if osk == "edge_vignette":
        full = _apply_edge_vignette(im, strength=0.46)
        return Image.blend(im, full, min(1.0, strength * 1.28))
    if osk == "geo_texture":
        full = _apply_geometric_texture(im, seed=seed)
        return Image.blend(im, full, min(1.0, strength * 1.55))
    if osk == "paper_grain":
        full = _apply_paper_grain_overlay(im, seed=seed)
        return Image.blend(im, full, min(1.0, strength * 1.30))
    if osk == "soft_bloom":
        full = _apply_soft_bloom_overlay(im)
        return Image.blend(im, full, min(1.0, strength * 1.26))
    if osk == "cinematic_grade":
        full = _apply_cinematic_grade_overlay(im)
        return Image.blend(im, full, min(1.0, strength * 1.18))
    if osk == "radial_focus":
        full = _apply_radial_focus_overlay(im)
        return Image.blend(im, full, min(1.0, strength * 1.24))
    return im

