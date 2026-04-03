"""扩展测试：布局类型组合、导出格式边界、滤镜/叠层极端强度。

目标：与既有 7 用例合并后总数 ≥ 20。
"""
from __future__ import annotations

import os
import tempfile
from typing import List

import pytest
from PIL import Image, ImageDraw, ImageStat

from wallpaper_maker.core import create_wallpaper, apply_post_filter, apply_bg_overlay
from wallpaper_maker.core_export import (
    _normalize_export_format,
    _save_wallpaper_file,
    _export_ext,
)
from wallpaper_maker.core_filters import apply_post_filter_impl
from wallpaper_maker.core_overlays import apply_bg_overlay_impl
from wallpaper_maker.core_layouts import VALID_LAYOUTS, _normalize_layout, LAYOUT_ALIASES


# ---------------------------------------------------------------------------
# 测试夹具
# ---------------------------------------------------------------------------

def _make_test_images(folder: str, n: int = 6) -> List[str]:
    os.makedirs(folder, exist_ok=True)
    paths: List[str] = []
    for i in range(n):
        p = os.path.join(folder, f"test_{i}.png")
        im = Image.new("RGB", (400 + i * 10, 600 + i * 10),
                        (40 + i * 20, 80 + i * 15, 120 + i * 10))
        d = ImageDraw.Draw(im)
        d.rectangle((10, 10, 100, 100), outline=(255, 255, 255), width=2)
        im.save(p)
        paths.append(p)
    return paths


def _dummy_edge_vignette(im: Image.Image, *, strength: float = 0.46) -> Image.Image:
    """简化暗角函数，供滤镜测试使用。"""
    dark = Image.new("RGB", im.size, (0, 0, 0))
    return Image.blend(im, dark, min(1.0, strength * 0.3))


def _dummy_lerp_srgb(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


# ---------------------------------------------------------------------------
# 1) 布局类型组合测试
# ---------------------------------------------------------------------------

_LAYOUT_SAMPLE = [
    "grid", "seamless", "scatter", "focus", "diagonal",
    "masonry", "fan", "stack", "split", "heart",
    "honeycomb", "spiral", "circle", "centered",
]


@pytest.mark.parametrize("layout", _LAYOUT_SAMPLE)
def test_create_wallpaper_layout_produces_valid_image(layout: str) -> None:
    """每种布局均能生成预期尺寸的 RGB 图像。"""
    with tempfile.TemporaryDirectory(prefix="wm_layout_") as td:
        src = os.path.join(td, "src")
        out_dir = os.path.join(td, "out")
        os.makedirs(out_dir)
        paths = _make_test_images(src, 8)
        save = os.path.join(out_dir, "result.png")
        create_wallpaper(
            image_paths=paths,
            count=6,
            w=640,
            h=360,
            out_dir=out_dir,
            custom_text="",
            seed=12345,
            layout=layout,
            bg_base_style="from_covers",
            bg_overlay_style="none",
            filter_style="none",
            show_stamp=False,
            save_path_override=save,
        )
        assert os.path.isfile(save), f"布局 {layout} 未生成输出文件"
        with Image.open(save) as im:
            assert im.mode == "RGB"
            assert im.width == 640
            assert im.height == 360


# ---------------------------------------------------------------------------
# 2) 导出格式边界测试
# ---------------------------------------------------------------------------

class TestExportFormats:
    def test_save_png(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "out.png")
            im = Image.new("RGB", (100, 100), (128, 128, 128))
            _save_wallpaper_file(im, p, export_format="png")
            assert os.path.isfile(p)
            with Image.open(p) as loaded:
                assert loaded.format == "PNG"

    def test_save_jpeg_quality_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p_lo = os.path.join(td, "lo.jpg")
            p_hi = os.path.join(td, "hi.jpg")
            im = Image.new("RGB", (200, 200), (200, 100, 50))
            _save_wallpaper_file(im, p_lo, export_format="jpeg", jpeg_quality=1)
            _save_wallpaper_file(im, p_hi, export_format="jpeg", jpeg_quality=95)
            assert os.path.getsize(p_lo) < os.path.getsize(p_hi)

    def test_save_webp_lossy_vs_lossless(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p_lossy = os.path.join(td, "lossy.webp")
            p_lossless = os.path.join(td, "lossless.webp")
            im = Image.new("RGB", (200, 200), (60, 120, 180))
            _save_wallpaper_file(im, p_lossy, export_format="webp", webp_quality=50, webp_lossless=False)
            _save_wallpaper_file(im, p_lossless, export_format="webp", webp_lossless=True)
            assert os.path.isfile(p_lossy)
            assert os.path.isfile(p_lossless)

    def test_export_ext_mapping(self) -> None:
        assert _export_ext("jpeg") == ".jpg"
        assert _export_ext("jpg") == ".jpg"
        assert _export_ext("png") == ".png"
        assert _export_ext("webp") == ".webp"
        assert _export_ext("bmp") == ".png"  # 未知格式回退 png

    def test_rgba_input_converts_to_rgb_on_save(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "rgba.jpg")
            im = Image.new("RGBA", (100, 100), (128, 128, 128, 200))
            _save_wallpaper_file(im, p, export_format="jpeg")
            with Image.open(p) as loaded:
                assert loaded.mode == "RGB"


# ---------------------------------------------------------------------------
# 3) 滤镜极端强度测试
# ---------------------------------------------------------------------------

_ALL_FILTERS = [
    "film_grain", "cool_tone", "warm_vintage", "high_contrast_bw",
    "soft_focus", "matte_fade", "editorial_crisp",
    "lomo_tone_shift", "lomo_fade",
]

_FILTERS_NEED_EDGE_VIG = ["vignette", "lomo_vignette"]
_FILTERS_NEED_LERP = ["lomo_light_fx"]


class TestFilterExtremeStrength:
    @pytest.mark.parametrize("fs", _ALL_FILTERS)
    def test_filter_zero_strength_returns_original(self, fs: str) -> None:
        im = Image.new("RGB", (120, 80), (100, 150, 200))
        out = apply_post_filter_impl(
            im, fs, seed=1, strength=0.0,
            edge_vignette_fn=_dummy_edge_vignette,
            lerp_srgb_fn=_dummy_lerp_srgb,
        )
        assert list(out.getdata()) == list(im.getdata())

    @pytest.mark.parametrize("fs", _ALL_FILTERS)
    def test_filter_full_strength_differs_from_original(self, fs: str) -> None:
        im = Image.new("RGB", (120, 80), (100, 150, 200))
        out = apply_post_filter_impl(
            im, fs, seed=1, strength=1.0,
            edge_vignette_fn=_dummy_edge_vignette,
            lerp_srgb_fn=_dummy_lerp_srgb,
        )
        assert out.size == im.size
        assert list(out.getdata()) != list(im.getdata()), f"{fs} 满强度应与原图不同"

    def test_vignette_filter_extreme(self) -> None:
        im = Image.new("RGB", (120, 80), (100, 150, 200))
        out = apply_post_filter_impl(
            im, "vignette", seed=1, strength=1.0,
            edge_vignette_fn=_dummy_edge_vignette,
            lerp_srgb_fn=_dummy_lerp_srgb,
        )
        assert out.size == im.size

    def test_lomo_light_fx_extreme(self) -> None:
        im = Image.new("RGB", (120, 80), (100, 150, 200))
        out = apply_post_filter_impl(
            im, "lomo_light_fx", seed=42, strength=1.0,
            edge_vignette_fn=_dummy_edge_vignette,
            lerp_srgb_fn=_dummy_lerp_srgb,
        )
        assert out.size == im.size

    def test_unknown_filter_passthrough(self) -> None:
        im = Image.new("RGB", (64, 64), (50, 50, 50))
        out = apply_post_filter_impl(
            im, "nonexistent_filter", seed=1, strength=1.0,
            edge_vignette_fn=_dummy_edge_vignette,
            lerp_srgb_fn=_dummy_lerp_srgb,
        )
        assert list(out.getdata()) == list(im.getdata())


# ---------------------------------------------------------------------------
# 4) 叠层极端强度测试
# ---------------------------------------------------------------------------

_ALL_OVERLAYS = [
    "frosted_glass", "edge_vignette", "geo_texture", "paper_grain",
    "soft_bloom", "cinematic_grade", "radial_focus",
]


class TestOverlayExtremeStrength:
    @pytest.mark.parametrize("ov", _ALL_OVERLAYS)
    def test_overlay_zero_strength_passthrough(self, ov: str) -> None:
        im = Image.new("RGB", (120, 80), (100, 150, 200))
        out = apply_bg_overlay_impl(im, ov, seed=1, strength=0.0)
        assert list(out.getdata()) == list(im.getdata())

    @pytest.mark.parametrize("ov", _ALL_OVERLAYS)
    def test_overlay_full_strength_modifies_image(self, ov: str) -> None:
        im = Image.new("RGB", (120, 80), (100, 150, 200))
        out = apply_bg_overlay_impl(im, ov, seed=1, strength=1.0)
        assert out.size == im.size
        assert list(out.getdata()) != list(im.getdata()), f"{ov} 满强度应与原图不同"

    def test_none_overlay_passthrough(self) -> None:
        im = Image.new("RGB", (64, 64), (50, 50, 50))
        out = apply_bg_overlay_impl(im, "none", seed=1, strength=1.0)
        assert list(out.getdata()) == list(im.getdata())


# ---------------------------------------------------------------------------
# 5) 布局辅助函数
# ---------------------------------------------------------------------------

class TestLayoutHelpers:
    def test_normalize_layout_aliases(self) -> None:
        assert _normalize_layout("标准网格") == "grid"
        assert _normalize_layout("scatter") == "scatter"
        assert _normalize_layout("unknown_layout_xyz") == "grid"

    def test_valid_layouts_completeness(self) -> None:
        assert "grid" in VALID_LAYOUTS
        assert "scatter" in VALID_LAYOUTS
        assert "heart" in VALID_LAYOUTS
        assert len(VALID_LAYOUTS) >= 20

    def test_all_aliases_point_to_valid_layout(self) -> None:
        for alias, target in LAYOUT_ALIASES.items():
            assert target in VALID_LAYOUTS, f"别名 {alias!r} 指向无效布局 {target!r}"


# ---------------------------------------------------------------------------
# 6) apply_post_filter / apply_bg_overlay 公开 API 入口测试
# ---------------------------------------------------------------------------

class TestPublicFilterOverlayAPI:
    def test_apply_post_filter_core_api(self) -> None:
        im = Image.new("RGB", (100, 100), (128, 128, 128))
        out = apply_post_filter(im, "cool_tone", seed=1, strength=70)
        assert out.size == im.size
        assert out.mode == "RGB"

    def test_apply_bg_overlay_core_api(self) -> None:
        im = Image.new("RGB", (100, 100), (128, 128, 128))
        out = apply_bg_overlay(im, "cinematic_grade", seed=1, strength=70)
        assert out.size == im.size
        assert out.mode == "RGB"
