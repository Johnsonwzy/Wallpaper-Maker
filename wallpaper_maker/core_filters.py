"""后期滤镜域（从 core.py 切分）。"""
from __future__ import annotations

import random
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps


def _clip_u8(x: float) -> int:
    return max(0, min(255, int(round(x))))


def _apply_filter_film_grain(
    im: Image.Image, seed: Optional[int], strength: float
) -> Image.Image:
    if strength <= 0.0:
        return im
    rng = random.Random(seed)
    w, h = im.size
    base = ImageEnhance.Contrast(im).enhance(1.05)
    noise = Image.effect_noise((w, h), rng.uniform(10.0, 16.0)).convert("L")
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    full = Image.blend(base, noise_rgb, 0.11)
    return Image.blend(im, full, strength)


def _apply_filter_cool_tone(im: Image.Image, strength: float) -> Image.Image:
    if strength <= 0.0:
        return im
    r, g, b = im.split()
    r = r.point(lambda x: _clip_u8(x * 0.90 - 2))
    g = g.point(lambda x: _clip_u8(x * 0.96))
    b = b.point(lambda x: _clip_u8(x * 1.13 + 8))
    out = Image.merge("RGB", (r, g, b))
    out = ImageEnhance.Color(out).enhance(0.72)
    full = ImageEnhance.Contrast(out).enhance(1.06)
    return Image.blend(im, full, strength)


def _apply_filter_warm_vintage(im: Image.Image, strength: float) -> Image.Image:
    if strength <= 0.0:
        return im
    r, g, b = im.split()
    r = r.point(lambda x: _clip_u8(x * 1.10 + 10))
    g = g.point(lambda x: _clip_u8(x * 1.04 + 5))
    b = b.point(lambda x: _clip_u8(x * 0.84 - 6))
    out = Image.merge("RGB", (r, g, b))
    out = ImageEnhance.Color(out).enhance(0.80)
    full = ImageEnhance.Contrast(out).enhance(0.94)
    return Image.blend(im, full, strength)


def _apply_filter_high_contrast_bw(im: Image.Image, strength: float) -> Image.Image:
    if strength <= 0.0:
        return im
    g = ImageOps.grayscale(im)
    g = ImageOps.autocontrast(g, cutoff=1)
    g = ImageEnhance.Contrast(g).enhance(1.26)
    g = g.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
    full = g.convert("RGB")
    return Image.blend(im, full, strength)


def _apply_filter_soft_focus(im: Image.Image, strength: float) -> Image.Image:
    if strength <= 0.0:
        return im
    blur = im.filter(ImageFilter.GaussianBlur(radius=2.2))
    out = Image.blend(im, blur, 0.32)
    out = ImageEnhance.Contrast(out).enhance(0.95)
    full = ImageEnhance.Brightness(out).enhance(1.03)
    return Image.blend(im, full, strength)


def _apply_filter_vignette(
    im: Image.Image, strength: float, edge_vignette_fn: Callable[..., Image.Image]
) -> Image.Image:
    if strength <= 0.0:
        return im
    full = edge_vignette_fn(im, strength=0.48)
    return Image.blend(im, full, strength)


def _apply_filter_matte_fade(im: Image.Image, strength: float) -> Image.Image:
    if strength <= 0.0:
        return im
    out = ImageEnhance.Contrast(im).enhance(0.82)
    out = ImageEnhance.Brightness(out).enhance(1.06)
    full = ImageEnhance.Color(out).enhance(0.84)
    return Image.blend(im, full, strength)


def _apply_filter_editorial_crisp(im: Image.Image, strength: float) -> Image.Image:
    if strength <= 0.0:
        return im
    out = im.filter(ImageFilter.UnsharpMask(radius=1.35, percent=170, threshold=2))
    out = ImageEnhance.Contrast(out).enhance(1.15)
    full = ImageEnhance.Color(out).enhance(0.92)
    return Image.blend(im, full, strength)


def _apply_filter_lomo_vignette(
    im: Image.Image, strength: float, edge_vignette_fn: Callable[..., Image.Image]
) -> Image.Image:
    if strength <= 0.0:
        return im
    dark = edge_vignette_fn(im, strength=0.78)
    center = ImageEnhance.Brightness(im).enhance(1.08)
    full = Image.blend(dark, center, 0.24)
    return Image.blend(im, full, strength)


def _apply_filter_lomo_tone_shift(im: Image.Image, strength: float) -> Image.Image:
    if strength <= 0.0:
        return im
    r, g, b = im.split()
    r = r.point(lambda x: _clip_u8(x * 1.14 + 10))
    g = g.point(lambda x: _clip_u8(x * 0.94))
    b = b.point(lambda x: _clip_u8(x * 1.11 + 6))
    out = Image.merge("RGB", (r, g, b))
    out = ImageEnhance.Color(out).enhance(1.16)
    full = ImageEnhance.Contrast(out).enhance(1.12)
    return Image.blend(im, full, strength)


def _apply_filter_lomo_fade(im: Image.Image, strength: float) -> Image.Image:
    if strength <= 0.0:
        return im
    r, g, b = im.split()
    lift = 26
    r = r.point(lambda x: _clip_u8(lift + x * 0.86 + 12))
    g = g.point(lambda x: _clip_u8(lift + x * 0.83 + 8))
    b = b.point(lambda x: _clip_u8(lift + x * 0.76 + 4))
    out = Image.merge("RGB", (r, g, b))
    out = ImageEnhance.Color(out).enhance(0.72)
    full = ImageEnhance.Contrast(out).enhance(0.84)
    return Image.blend(im, full, strength)


def _apply_filter_lomo_light_fx(
    im: Image.Image,
    strength: float,
    seed: Optional[int],
    lerp_srgb_fn: Callable[[tuple[int, int, int], tuple[int, int, int], float], tuple[int, int, int]],
) -> Image.Image:
    if strength <= 0.0:
        return im
    rng = random.Random(seed)
    w, h = im.size
    leak = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(leak)
    side = rng.choice(("left", "right"))
    if side == "left":
        c1, c2 = (255, 120, 40), (255, 210, 70)
        for x in range(w):
            t = max(0.0, 1.0 - x / max(1, int(w * 0.55)))
            col = lerp_srgb_fn(c2, c1, t)
            d.line([(x, 0), (x, h)], fill=col)
    else:
        c1, c2 = (255, 90, 35), (255, 195, 80)
        for x in range(w):
            t = max(0.0, 1.0 - (w - 1 - x) / max(1, int(w * 0.55)))
            col = lerp_srgb_fn(c2, c1, t)
            d.line([(x, 0), (x, h)], fill=col)
    leak = leak.filter(ImageFilter.GaussianBlur(radius=max(8, min(w, h) // 20)))
    out = Image.blend(im, leak, 0.24)
    full = ImageEnhance.Contrast(out).enhance(1.06)
    return Image.blend(im, full, strength)


def apply_post_filter_impl(
    im: Image.Image,
    filter_style: str,
    *,
    seed: Optional[int],
    strength: float,
    edge_vignette_fn: Callable[..., Image.Image],
    lerp_srgb_fn: Callable[[tuple[int, int, int], tuple[int, int, int], float], tuple[int, int, int]],
) -> Image.Image:
    fs = (filter_style or "none").strip().lower()
    if fs in ("", "none", "off") or strength <= 0.0:
        return im
    if fs == "film_grain":
        return _apply_filter_film_grain(im, seed, strength)
    if fs == "cool_tone":
        return _apply_filter_cool_tone(im, strength)
    if fs == "warm_vintage":
        return _apply_filter_warm_vintage(im, strength)
    if fs == "high_contrast_bw":
        return _apply_filter_high_contrast_bw(im, strength)
    if fs == "soft_focus":
        return _apply_filter_soft_focus(im, strength)
    if fs == "vignette":
        return _apply_filter_vignette(im, strength, edge_vignette_fn)
    if fs == "matte_fade":
        return _apply_filter_matte_fade(im, strength)
    if fs == "editorial_crisp":
        return _apply_filter_editorial_crisp(im, strength)
    if fs == "lomo_vignette":
        return _apply_filter_lomo_vignette(im, strength, edge_vignette_fn)
    if fs == "lomo_tone_shift":
        return _apply_filter_lomo_tone_shift(im, strength)
    if fs == "lomo_fade":
        return _apply_filter_lomo_fade(im, strength)
    if fs == "lomo_light_fx":
        return _apply_filter_lomo_light_fx(im, strength, seed, lerp_srgb_fn)
    return im

