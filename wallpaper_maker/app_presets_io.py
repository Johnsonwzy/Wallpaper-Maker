"""预设收集/应用逻辑（从 app.py 切分）。"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, List

from wallpaper_maker.config import (
    DEFAULT_BG_BASE_STYLE,
    DEFAULT_BG_OVERLAY_STRENGTH,
    DEFAULT_BG_OVERLAY_STYLE,
    DEFAULT_BG_STYLE,
    DEFAULT_ENABLE_AESTHETIC_RULES,
    DEFAULT_FILTER_STRENGTH,
    DEFAULT_FILTER_STYLE,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RANDOM_COUNT,
    DEFAULT_SAMPLING_STRATEGY,
    DEFAULT_SEED_COUNT,
    DEFAULT_STYLE_INTENSITY,
    DEFAULT_TEXT,
    DEFAULT_TEXT_POS,
    DEFAULT_STAMP_SIZE,
    DEFAULT_TEXT_SIZE,
    DEFAULT_UI_THEME_MODE,
    DEFAULT_WALLPAPER_HEIGHT,
    DEFAULT_WALLPAPER_WIDTH,
    DEFAULT_WEBP_QUALITY,
)
from wallpaper_maker.core import _norm_corner_pos, _normalize_export_format, _normalize_layout
from wallpaper_maker.gui_utils import _parse_gui_float, _parse_gui_int, _read_double_var
from wallpaper_maker.presets import _empty_preset_template, _merge_preset_payload


def collect_preset_data(app: Any) -> Dict[str, Any]:
    lay = app._layout_by_label[app.var_layout_label.get()]
    fmt = app._export_fmt_by_label.get(app._to_zh(app._combo_export_fmt.get()), "png")
    tmpl = _empty_preset_template()
    tmpl.update(
        {
            "layout": lay,
            "random_count": max(
                1, _parse_gui_int(app.var_count.get(), DEFAULT_RANDOM_COUNT)
            ),
            "seed_base": app.var_seed.get().strip() or str(DEFAULT_SEED_COUNT),
            "width": max(
                1, _parse_gui_int(app.var_width.get(), DEFAULT_WALLPAPER_WIDTH)
            ),
            "height": max(
                1, _parse_gui_int(app.var_height.get(), DEFAULT_WALLPAPER_HEIGHT)
            ),
            "batch_count": max(1, _parse_gui_int(app.var_batch_count.get(), 3)),
            "margin": max(0, _parse_gui_int(app.var_margin.get(), 40)),
            "gap": max(0, _parse_gui_int(app.var_gap.get(), 30)),
            "rotation_deg": _read_double_var(app.var_rot, 15.0),
            "scatter_bleed": _parse_gui_float(app.var_scatter_bleed.get(), 0.1),
            "scatter_scale_min": _parse_gui_float(app.var_scatter_smin.get(), 0.7),
            "scatter_scale_max": _parse_gui_float(app.var_scatter_smax.get(), 1.45),
            "scatter_shadow": bool(app.var_scatter_shadow.get()),
            "bg_base_style": app.var_bg_base_style.get(),
            "bg_overlay_style": app.var_bg_overlay_style.get(),
            "bg_overlay_strength": max(
                0, min(100, int(round(float(app.var_bg_overlay_strength.get()))))
            ),
            # 向后兼容旧版本：保留合成后的 bg_style。
            "bg_style": app._bg_parts_to_legacy_style(
                app.var_bg_base_style.get(),
                app.var_bg_overlay_style.get(),
            ),
            "filter_style": app.var_filter_style.get(),
            "filter_strength": max(
                0, min(100, int(round(float(app.var_filter_strength.get()))))
            ),
            "bg_custom_top": app.var_bg_custom_top.get(),
            "bg_custom_bottom": app.var_bg_custom_bottom.get(),
            "custom_text": app.var_text.get(),
            "text_size": max(1, _parse_gui_int(app.var_text_size.get(), DEFAULT_TEXT_SIZE)),
            "stamp_size": max(1, _parse_gui_int(app.var_stamp_size.get(), DEFAULT_STAMP_SIZE)),
            "text_pos": app.var_text_pos.get(),
            "stamp_place": app.var_stamp_place.get(),
            "text_color_name": app.var_text_color.get(),
            "stroke_color_name": app.var_stroke_color.get(),
            "show_stamp": bool(app.var_show_stamp.get()),
            "recursive": bool(app.var_recursive.get()),
            "output_dir": app.var_out_dir.get().strip() or DEFAULT_OUTPUT_DIR,
            "export_format": fmt,
            "jpeg_quality": max(
                1,
                min(95, _parse_gui_int(app.var_jpeg_quality.get(), DEFAULT_JPEG_QUALITY)),
            ),
            "webp_quality": max(
                1,
                min(100, _parse_gui_int(app.var_webp_quality.get(), DEFAULT_WEBP_QUALITY)),
            ),
            "webp_lossless": bool(app.var_webp_lossless.get()),
            "embed_srgb_icc": bool(app.var_embed_srgb_icc.get()),
            "preview_batch_sync": bool(app.var_preview_batch_sync.get()),
            "preview_batch_count": max(
                1, _parse_gui_int(app.var_preview_batch_count.get(), 3)
            ),
            "follow_preview_seed": bool(app.var_follow_preview_seed.get()),
            "auto_show_gallery_on_preview": bool(
                app.var_auto_show_gallery_on_preview.get()
            ),
            "ui_theme_mode": app.var_ui_theme_mode.get(),
            "enable_aesthetic_rules": bool(app.var_enable_aesthetic_rules.get()),
            "style_intensity": app.var_style_intensity.get(),
            "sampling_strategy": app.var_sampling_strategy.get(),
            "magazine_style": bool(app._preset_magazine_style),
            "source_folder_weights": {
                app._norm_source_path(k): float(v)
                for k, v in app._source_folder_weight_by_path.items()
                if float(v) > 0
            },
            "source_folders": list(app._source_folders),
        }
    )
    return tmpl


def apply_preset_data(app: Any, data: Dict[str, Any]) -> None:
    d = _merge_preset_payload(data)
    app._preset_magazine_style = bool(d.get("magazine_style", False))

    def _gi(key: str, default: int) -> int:
        try:
            v = d.get(key, default)
            return int(v)
        except (TypeError, ValueError):
            return default

    def _gf(key: str, default: float) -> float:
        try:
            v = d.get(key, default)
            return float(v)
        except (TypeError, ValueError):
            return default

    lay = _normalize_layout(str(d.get("layout", "grid")))
    lay_zh = app._layout_zh_for_layout_key(lay)
    app.var_layout_label.set(lay_zh)
    try:
        app._combo_layout.set(app._tr(lay_zh))
    except (tk.TclError, AttributeError):
        pass

    app.var_count.set(str(max(1, _gi("random_count", DEFAULT_RANDOM_COUNT))))
    app.var_seed.set(str(d.get("seed_base", DEFAULT_SEED_COUNT)).strip() or str(DEFAULT_SEED_COUNT))
    app.var_width.set(str(max(1, _gi("width", DEFAULT_WALLPAPER_WIDTH))))
    app.var_height.set(str(max(1, _gi("height", DEFAULT_WALLPAPER_HEIGHT))))
    app.var_batch_count.set(str(max(1, _gi("batch_count", 3))))
    app.var_margin.set(str(max(0, _gi("margin", 40))))
    app.var_gap.set(str(max(0, _gi("gap", 30))))
    try:
        app.var_rot.set(_gf("rotation_deg", 15.0))
    except (tk.TclError, ValueError, TypeError):
        app.var_rot.set(15.0)
    try:
        app.var_scatter_rot.set(str(_gf("rotation_deg", 15.0)))
    except (tk.TclError, ValueError, TypeError):
        pass

    app.var_scatter_bleed.set(str(_gf("scatter_bleed", 0.1)))
    app.var_scatter_smin.set(str(_gf("scatter_scale_min", 0.7)))
    app.var_scatter_smax.set(str(_gf("scatter_scale_max", 1.45)))
    try:
        app.var_scatter_shadow.set(bool(d.get("scatter_shadow", True)))
    except tk.TclError:
        pass

    if "bg_base_style" in d or "bg_overlay_style" in d:
        bbs = str(d.get("bg_base_style", DEFAULT_BG_BASE_STYLE)).strip().lower()
        bos = str(d.get("bg_overlay_style", DEFAULT_BG_OVERLAY_STYLE)).strip().lower()
    else:
        bbs, bos = app._legacy_bg_style_to_parts(str(d.get("bg_style", DEFAULT_BG_STYLE)))
    if bbs not in app._bg_base_style_zh_by_key:
        bbs = DEFAULT_BG_BASE_STYLE
    if bos not in app._bg_overlay_style_zh_by_key:
        bos = DEFAULT_BG_OVERLAY_STYLE
    app.var_bg_base_style.set(bbs)
    app.var_bg_overlay_style.set(bos)
    try:
        app._combo_bg_base_style.set(
            app._tr(app._bg_base_style_zh_by_key.get(bbs, "从所选图取色渐变（推荐）"))
        )
        app._combo_bg_overlay_style.set(
            app._tr(app._bg_overlay_style_zh_by_key.get(bos, "无叠层"))
        )
    except (tk.TclError, AttributeError):
        pass

    fs = str(d.get("filter_style", DEFAULT_FILTER_STYLE)).strip().lower()
    if fs not in app._filter_style_zh_by_key:
        fs = DEFAULT_FILTER_STYLE
    app.var_filter_style.set(fs)
    try:
        app._combo_filter_style.set(
            app._tr(app._filter_style_zh_by_key.get(fs, "无滤镜（原始质感）"))
        )
    except (tk.TclError, AttributeError):
        pass
    try:
        app.var_filter_strength.set(max(0, min(100, _gi("filter_strength", DEFAULT_FILTER_STRENGTH))))
    except tk.TclError:
        pass

    bt = str(d.get("bg_custom_top", "白色"))
    bb = str(d.get("bg_custom_bottom", "黑色"))
    if bt not in app.text_colors:
        bt = "白色"
    if bb not in app.text_colors:
        bb = "黑色"
    app.var_bg_custom_top.set(bt)
    app.var_bg_custom_bottom.set(bb)
    try:
        app.var_bg_overlay_strength.set(
            max(0, min(100, _gi("bg_overlay_strength", DEFAULT_BG_OVERLAY_STRENGTH)))
        )
    except tk.TclError:
        pass
    try:
        app._combo_bg_custom_top.set(app._tr(bt))
        app._combo_bg_custom_bottom.set(app._tr(bb))
    except (tk.TclError, AttributeError):
        pass

    app.var_text.set(str(d.get("custom_text", DEFAULT_TEXT)))
    app.var_text_size.set(str(max(1, _gi("text_size", DEFAULT_TEXT_SIZE))))
    app.var_stamp_size.set(str(max(1, _gi("stamp_size", DEFAULT_STAMP_SIZE))))

    tp = str(d.get("text_pos", DEFAULT_TEXT_POS))
    if tp not in app.text_positions:
        tp = _norm_corner_pos(tp)
    app.var_text_pos.set(tp)
    pos_by_zh = dict(zip(app.pos_labels, app.text_positions))
    zh_of_pos = {v: k for k, v in pos_by_zh.items()}
    try:
        app._combo_text_pos.set(app._tr(zh_of_pos.get(tp, "右下")))
    except (tk.TclError, AttributeError):
        pass

    sp = str(d.get("stamp_place", "same_above"))
    if sp not in app._stamp_place_zh_by_key:
        sp = "same_above"
    app.var_stamp_place.set(sp)
    try:
        app._combo_stamp_place.set(
            app._tr(app._stamp_place_zh_by_key.get(sp, "与格言同侧，格言再上"))
        )
    except (tk.TclError, AttributeError):
        pass

    tc = str(d.get("text_color_name", "白色"))
    if tc not in app.text_colors:
        tc = "白色"
    app.var_text_color.set(tc)
    sc = str(d.get("stroke_color_name", "黑色"))
    if sc not in app.text_colors:
        sc = "黑色"
    app.var_stroke_color.set(sc)
    try:
        app._combo_text_color.set(app._tr(tc))
        app._combo_stroke.set(app._tr(sc))
    except (tk.TclError, AttributeError):
        pass

    try:
        app.var_show_stamp.set(bool(d.get("show_stamp", True)))
    except tk.TclError:
        pass
    try:
        app.var_recursive.set(bool(d.get("recursive", False)))
    except tk.TclError:
        pass

    app.var_out_dir.set(str(d.get("output_dir", DEFAULT_OUTPUT_DIR)).strip() or DEFAULT_OUTPUT_DIR)

    fmt = _normalize_export_format(str(d.get("export_format", "png")))
    try:
        app._combo_export_fmt.set(app._export_label_for_fmt(fmt))
    except (tk.TclError, AttributeError):
        pass
    app.var_jpeg_quality.set(str(max(1, min(95, _gi("jpeg_quality", DEFAULT_JPEG_QUALITY)))))
    app.var_webp_quality.set(str(max(1, min(100, _gi("webp_quality", DEFAULT_WEBP_QUALITY)))))
    try:
        app.var_webp_lossless.set(bool(d.get("webp_lossless", False)))
        app.var_embed_srgb_icc.set(bool(d.get("embed_srgb_icc", True)))
        app.var_preview_batch_sync.set(bool(d.get("preview_batch_sync", True)))
        app.var_follow_preview_seed.set(bool(d.get("follow_preview_seed", False)))
        app.var_auto_show_gallery_on_preview.set(bool(d.get("auto_show_gallery_on_preview", True)))
        app.var_enable_aesthetic_rules.set(
            bool(d.get("enable_aesthetic_rules", DEFAULT_ENABLE_AESTHETIC_RULES))
        )
    except tk.TclError:
        pass
    app.var_preview_batch_count.set(str(max(1, _gi("preview_batch_count", 3))))
    tm = str(d.get("ui_theme_mode", DEFAULT_UI_THEME_MODE)).strip().lower()
    if tm not in app._theme_mode_zh_by_key:
        tm = DEFAULT_UI_THEME_MODE
    app.var_ui_theme_mode.set(tm)
    try:
        app._combo_ui_theme.set(app._tr(app._theme_mode_zh_by_key.get(tm, "跟随系统")))
    except (tk.TclError, AttributeError):
        pass
    st = str(d.get("style_intensity", DEFAULT_STYLE_INTENSITY)).strip().lower()
    if st not in app._style_intensity_zh_by_key:
        st = DEFAULT_STYLE_INTENSITY
    app.var_style_intensity.set(st)
    try:
        app._combo_style_intensity.set(app._tr(app._style_intensity_zh_by_key.get(st, "标准")))
    except (tk.TclError, AttributeError):
        pass
    sk = str(d.get("sampling_strategy", DEFAULT_SAMPLING_STRATEGY)).strip().lower()
    if sk not in app._sampling_mode_zh_by_key:
        sk = DEFAULT_SAMPLING_STRATEGY
    app.var_sampling_strategy.set(sk)
    try:
        app._combo_sampling_strategy.set(
            app._tr(app._sampling_mode_zh_by_key.get(sk, "按图片数量自然比例"))
        )
    except (tk.TclError, AttributeError):
        pass

    folders = d.get("source_folders")
    if isinstance(folders, list):
        norm: List[str] = []
        for p in folders:
            s = str(p).strip()
            if s:
                norm.append(os.path.abspath(os.path.expanduser(s)))
        if norm:
            app._source_folders[:] = norm
            app._sync_source_listbox()
        elif len(folders) == 0:
            messagebox.showwarning(
                "预设图源",
                "JSON 中 source_folders 为空，已保留当前图源列表。",
            )
    fw = d.get("source_folder_weights")
    app._source_folder_weight_by_path.clear()
    if isinstance(fw, dict):
        for k, v in fw.items():
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv > 0:
                app._source_folder_weight_by_path[app._norm_source_path(str(k))] = fv

    app._sync_bg_custom_controls()
    app._sync_export_controls_state()
    app._on_preview_batch_sync_toggle()
    app._apply_theme()

