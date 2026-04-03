"""Wallpaper Maker 主界面（tkinter）。"""
from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 280_000_000
except Exception:
    pass

from wallpaper_maker.config import (
    BUILTIN_STYLE_PRESET_PLACEHOLDER,
    DEFAULT_BG_STYLE,
    DEFAULT_BG_BASE_STYLE,
    DEFAULT_BG_OVERLAY_STRENGTH,
    DEFAULT_BG_OVERLAY_STYLE,
    DEFAULT_ENABLE_AESTHETIC_RULES,
    DEFAULT_FILTER_STYLE,
    DEFAULT_FILTER_STRENGTH,
    DEFAULT_IMAGE_FOLDER,
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
    DEFAULT_UI_LANGUAGE,
    DEFAULT_WALLPAPER_HEIGHT,
    DEFAULT_WALLPAPER_WIDTH,
    DEFAULT_WEBP_QUALITY,
    PREVIEW_BATCH_CAP_DECOUPLED,
    UI_FONT_PT_MAIN,
    UI_WINDOW_MIN_H,
    UI_WINDOW_MIN_W,
)
from wallpaper_maker.i18n import LANG_LABEL_BY_CODE, tr, to_zh
from wallpaper_maker.app_params import (
    BG_BASE_STYLE_KEY_BY_ZH,
    BG_OVERLAY_RECOMMENDED_STRENGTH,
    BG_OVERLAY_STYLE_KEY_BY_ZH,
    FILTER_RECOMMENDED_STRENGTH,
    FILTER_STYLE_KEY_BY_ZH,
)
from wallpaper_maker.app_presets_io import apply_preset_data, collect_preset_data
from wallpaper_maker.app_task_scheduler import cancel_named_job, schedule_named_job
from wallpaper_maker.app_theme import (
    detect_macos_appearance,
    resolve_theme_mode,
    theme_palette,
)
from wallpaper_maker.app_export_jobs import (
    export_filtered_from_existing_previews as _ej_export_filtered,
    on_generate as _ej_on_generate,
)
from wallpaper_maker.app_preview_pipeline import (
    maybe_auto_open_preview_gallery_for_effect_job as _pp_maybe_auto_open,
    on_effect_preview as _pp_on_effect_preview,
    refresh_preview_base_live as _pp_refresh_base_live,
    refresh_preview_filter_live as _pp_refresh_filter_live,
    replace_preview_gallery as _pp_replace_gallery,
    update_preview as _pp_update_preview,
)
from wallpaper_maker.app_windowing import (
    debounced_sync_preview_geometry,
    ensure_preview_gallery,
    ensure_preview_gallery_instance,
    init_preview_gallery_window,
    initial_main_geometry,
    notify_preview_gallery_withdrawn,
    on_main_window_configure,
    on_main_window_map,
    refresh_preview_gallery_button_label,
    sync_preview_geometry,
    toggle_preview_gallery,
)
from wallpaper_maker.core import (
    _norm_corner_pos,
    _normalize_export_format,
    _normalize_layout,
)
from wallpaper_maker.gui_utils import (
    _parse_gui_float,
    _parse_gui_int,
    _read_double_var,
)
from wallpaper_maker.presets import (
    BUILTIN_STYLE_PRESETS,
    _empty_preset_template,
)
from wallpaper_maker.preview_gallery import PreviewGalleryToplevel

# ====================== 浅色清爽 Mac UI ======================
class WallPaperApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("✨ Wallpaper Maker")
        self.minsize(UI_WINDOW_MIN_W, UI_WINDOW_MIN_H)
        self.geometry(self._initial_main_geometry())
        # 预览相关
        self.preview_gallery: Optional[PreviewGalleryToplevel] = None
        self._preview_gallery_user_hidden: bool = True
        self._effect_preview_ready = False
        self._last_preview_seed: Optional[int] = None
        self._bg_live_preview_cache: Optional[Dict[str, Any]] = None
        self._bg_live_preview_inflight: bool = False
        self._preview_geom_job: Optional[str] = None
        self._task_cancel_event: Optional[threading.Event] = None
        self._theme_follow_job: Optional[str] = None
        self._last_system_appearance: str = "light"

        self._theme_mode_key_by_zh: Dict[str, str] = {
            "跟随系统": "system",
            "浅色": "light",
            "深色": "dark",
        }
        self._theme_mode_zh_by_key: Dict[str, str] = {
            v: k for k, v in self._theme_mode_key_by_zh.items()
        }
        self.var_ui_theme_mode = tk.StringVar(value=DEFAULT_UI_THEME_MODE)
        self.var_ui_language = tk.StringVar(value=DEFAULT_UI_LANGUAGE)
        self._lang_display_by_code: Dict[str, str] = dict(LANG_LABEL_BY_CODE)
        self._lang_code_by_display: Dict[str, str] = {
            v: k for k, v in self._lang_display_by_code.items()
        }
        self._theme_colors: Dict[str, str] = {}
        self._main_scroll_canvas: Optional[tk.Canvas] = None
        self._main_scroll_inner: Optional[tk.Frame] = None
        self._main_scroll_win: Optional[int] = None
        self._main_scroll_vsb: Optional[tk.Scrollbar] = None

        self.configure(bg="#FFFFFF")
        self.bind("<Configure>", self._on_main_window_configure)
        self.bind("<Map>", self._on_main_window_map, add="+")
        self.protocol("WM_DELETE_WINDOW", self._on_close_main_window)

        self._source_folders: list[str] = [
            os.path.abspath(os.path.expanduser(DEFAULT_IMAGE_FOLDER))
        ]
        self._source_folder_weight_by_path: Dict[str, float] = {}
        self._sampling_mode_key_by_zh: dict[str, str] = {
            "按图片数量自然比例": "natural",
            "按文件夹均衡抽样": "balanced",
            "按文件夹权重抽样": "weighted",
        }
        self._sampling_mode_zh_by_key = {
            v: k for k, v in self._sampling_mode_key_by_zh.items()
        }
        self.var_sampling_strategy = tk.StringVar(value=DEFAULT_SAMPLING_STRATEGY)
        self.var_enable_aesthetic_rules = tk.BooleanVar(
            value=DEFAULT_ENABLE_AESTHETIC_RULES
        )
        self._style_intensity_key_by_zh: dict[str, str] = {
            "保守": "conservative",
            "标准": "normal",
            "激进": "aggressive",
        }
        self._style_intensity_zh_by_key = {
            v: k for k, v in self._style_intensity_key_by_zh.items()
        }
        self.var_style_intensity = tk.StringVar(value=DEFAULT_STYLE_INTENSITY)
        self._preset_magazine_style = False
        self.var_out_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self._export_fmt_by_label: dict[str, str] = {
            "PNG（无损）": "png",
            "JPEG": "jpeg",
            "WebP（体积）": "webp",
        }
        self.var_jpeg_quality = tk.StringVar(value=str(DEFAULT_JPEG_QUALITY))
        self.var_webp_quality = tk.StringVar(value=str(DEFAULT_WEBP_QUALITY))
        self.var_webp_lossless = tk.BooleanVar(value=False)
        self.var_embed_srgb_icc = tk.BooleanVar(value=True)
        self.var_count = tk.StringVar(value=str(DEFAULT_RANDOM_COUNT))
        self.var_width = tk.StringVar(value=str(DEFAULT_WALLPAPER_WIDTH))
        self.var_height = tk.StringVar(value=str(DEFAULT_WALLPAPER_HEIGHT))
        self.var_text = tk.StringVar(value=DEFAULT_TEXT)
        # 👇 新增 3.0 文字变量
        self.var_text_size = tk.StringVar(value=str(DEFAULT_TEXT_SIZE))
        self.var_stamp_size = tk.StringVar(value=str(DEFAULT_STAMP_SIZE))
        
        self.text_positions = ["top_left", "top_right", "bottom_left", "bottom_right", "center"]
        self.pos_labels = ["左上", "右上", "左下", "右下", "居中"]
        self.var_text_pos = tk.StringVar(value="bottom_right")

        self.var_show_stamp = tk.BooleanVar(value=True)
        self._stamp_place_key_by_zh: dict[str, str] = {
            "与格言同侧，格言再上": "same_above",
            "与格言左右对侧": "opposite",
            "居中": "center",
        }
        self._stamp_place_zh_by_key = {
            v: k for k, v in self._stamp_place_key_by_zh.items()
        }
        self.var_stamp_place = tk.StringVar(value="same_above")
        self.var_recursive = tk.BooleanVar(value=False)
        self.var_margin = tk.StringVar(value="40")
        self.var_rot = tk.DoubleVar(value=15.0)
        self.var_gap = tk.StringVar(value="30")
        self._layout_choices: list[tuple[str, str]] = [
            ("grid", "标准网格"),
            ("seamless", "无缝铺满"),
            ("scatter", "重叠散落"),
            ("focus", "焦点大图"),
            ("diagonal", "斜向流"),
            ("masonry", "瀑布流"),
            ("fan", "扇形放射"),
            ("stack", "翻页堆叠"),
            ("split", "分屏对称"),
            ("w_shape", "W型波浪"),
            ("v_shape", "V型"),
            ("arc", "弧形"),
            ("cross", "十字扩散"),
            ("wing", "对称翼型"),
            ("heart", "心形"),
            ("circle", "圆形环绕"),
            ("s_shape", "S型"),
            ("text_flow", "斜排文字流"),
            ("centered", "极简居中对称"),
            ("left_white", "左对齐留白"),
            ("triangle", "三角稳定构图"),
            ("spiral", "螺旋环绕"),
            ("diag_two", "对角线双飞"),
            ("layer", "上下分层极简"),
            ("honeycomb", "六边形蜂窝"),
            ("fade", "渐隐散点"),
        ]
        self._layout_by_label = {b: a for a, b in self._layout_choices}
        self.var_layout_label = tk.StringVar(value="重叠散落")
        self.var_seed = tk.StringVar(value=str(DEFAULT_SEED_COUNT))
        self.var_scatter_rot = tk.StringVar(value="14")
        self.var_scatter_bleed = tk.StringVar(value="0.1")
        self.var_scatter_smin = tk.StringVar(value="0.7")
        self.var_scatter_smax = tk.StringVar(value="1.45")
        self.var_scatter_shadow = tk.BooleanVar(value=True)
        self._bg_base_style_key_by_zh: dict[str, str] = dict(BG_BASE_STYLE_KEY_BY_ZH)
        self._bg_base_style_zh_by_key = {
            v: k for k, v in self._bg_base_style_key_by_zh.items()
        }
        self._bg_overlay_style_key_by_zh: dict[str, str] = dict(
            BG_OVERLAY_STYLE_KEY_BY_ZH
        )
        self._bg_overlay_recommended_strength: dict[str, int] = dict(
            BG_OVERLAY_RECOMMENDED_STRENGTH
        )
        self._bg_overlay_style_zh_by_key = {
            v: k for k, v in self._bg_overlay_style_key_by_zh.items()
        }
        self.var_bg_base_style = tk.StringVar(value=DEFAULT_BG_BASE_STYLE)
        self.var_bg_overlay_style = tk.StringVar(value=DEFAULT_BG_OVERLAY_STYLE)
        self.var_bg_overlay_strength = tk.DoubleVar(
            value=float(DEFAULT_BG_OVERLAY_STRENGTH)
        )
        self.var_bg_custom_top = tk.StringVar(value="白色")
        self.var_bg_custom_bottom = tk.StringVar(value="黑色")
        self._filter_style_key_by_zh: dict[str, str] = dict(FILTER_STYLE_KEY_BY_ZH)
        self._filter_recommended_strength: dict[str, int] = dict(
            FILTER_RECOMMENDED_STRENGTH
        )
        self._filter_style_zh_by_key = {
            v: k for k, v in self._filter_style_key_by_zh.items()
        }
        self.var_filter_style = tk.StringVar(value=DEFAULT_FILTER_STYLE)
        self.var_filter_strength = tk.DoubleVar(value=float(DEFAULT_FILTER_STRENGTH))
        self.var_batch_count = tk.StringVar(value="3")
        self.var_preview_batch_sync = tk.BooleanVar(value=True)
        self.var_preview_batch_count = tk.StringVar(value="3")
        self.var_follow_preview_seed = tk.BooleanVar(value=False)
        self.var_auto_show_gallery_on_preview = tk.BooleanVar(value=True)
        self.var_live_bg_base_preview = tk.BooleanVar(value=True)
        self.var_preview_compare_boost = tk.BooleanVar(value=False)
        self.var_seed_status = tk.StringVar(
            value=self._tr("预览种子：—（成功生成效果图预览后显示）")
        )

        self._build_ui()
        self.after(120, self._init_preview_gallery_window)
        self.after(400, self._schedule_theme_follow)

    def _tr(self, text: str, **kwargs: Any) -> str:
        translated = tr(text, self.var_ui_language.get())
        if kwargs:
            try:
                return translated.format(**kwargs)
            except Exception:
                return translated
        return translated

    def _to_zh(self, text: str) -> str:
        return to_zh(text, self.var_ui_language.get())

    def _rebuild_ui_for_language(self) -> None:
        try:
            self.var_seed_status.set(self._tr(self._to_zh(self.var_seed_status.get())))
        except tk.TclError:
            pass
        wrap = getattr(self, "_root_wrap", None)
        if wrap is not None:
            try:
                wrap.destroy()
            except tk.TclError:
                pass
        self._build_ui()
        self._refresh_preview_gallery_button_label()

    def _detect_macos_appearance(self) -> str:
        return detect_macos_appearance()

    def _schedule_theme_follow(self) -> None:
        if self._theme_follow_job is not None:
            return
        schedule_named_job(
            self,
            attr_name="_theme_follow_job",
            delay_ms=900,
            callback=self._poll_system_theme_follow,
        )

    def _poll_system_theme_follow(self) -> None:
        self._theme_follow_job = None
        try:
            mode = (self.var_ui_theme_mode.get() or "system").strip().lower()
            if mode == "system":
                now = self._detect_macos_appearance()
                if now != self._last_system_appearance:
                    self._last_system_appearance = now
                    self._apply_theme()
            else:
                # 非跟随系统时仅更新缓存，避免切回 system 时首次状态不准。
                self._last_system_appearance = self._detect_macos_appearance()
        except Exception:
            pass
        finally:
            self._schedule_theme_follow()

    def _resolved_theme_mode(self) -> str:
        return resolve_theme_mode(
            self.var_ui_theme_mode.get(),
            detector=self._detect_macos_appearance,
        )

    def _theme_palette(self) -> Dict[str, str]:
        return theme_palette(self._resolved_theme_mode())

    def _on_main_canvas_configure(self, event: tk.Event) -> None:
        if self._main_scroll_canvas is None or self._main_scroll_win is None:
            return
        if event.widget is not self._main_scroll_canvas:
            return
        try:
            self._main_scroll_canvas.itemconfigure(
                self._main_scroll_win, width=max(1, int(event.width) - 28)
            )
        except tk.TclError:
            return

    def _on_main_inner_configure(self, _event: tk.Event) -> None:
        if self._main_scroll_canvas is None:
            return
        try:
            self._main_scroll_canvas.configure(
                scrollregion=self._main_scroll_canvas.bbox("all")
            )
        except tk.TclError:
            pass

    def _on_main_mousewheel(self, event: tk.Event) -> None:
        if self._main_scroll_canvas is None:
            return
        d = getattr(event, "delta", 0) or 0
        if d == 0:
            return
        step = 2 if abs(d) >= 120 else 1
        self._main_scroll_canvas.yview_scroll(-step if d > 0 else step, "units")

    def _on_main_mousewheel_linux(self, event: tk.Event) -> None:
        if self._main_scroll_canvas is None:
            return
        n = getattr(event, "num", 0)
        if n == 4:
            self._main_scroll_canvas.yview_scroll(-2, "units")
        elif n == 5:
            self._main_scroll_canvas.yview_scroll(2, "units")

    def _apply_theme_recursive(self, widget: tk.Widget, pal: Dict[str, str]) -> None:
        def _in_form_panel(w: tk.Widget) -> bool:
            try:
                p = w
                fp = getattr(self, "_form_panel", None)
                while p is not None:
                    if fp is not None and p is fp:
                        return True
                    p = p.master  # type: ignore[assignment]
            except Exception:
                return False
            return False

        base_bg = pal["panel"] if _in_form_panel(widget) else pal["bg"]
        try:
            if isinstance(widget, (tk.Frame, tk.LabelFrame)):
                widget.configure(
                    bg=base_bg,
                    highlightbackground=pal["divider"],
                    highlightcolor=pal["divider"],
                )
                if isinstance(widget, tk.LabelFrame):
                    widget.configure(
                        bd=1,
                        relief=tk.FLAT,
                        highlightthickness=1,
                    )
            elif isinstance(widget, tk.Label):
                fg = str(widget.cget("fg"))
                new_fg = pal["fg"] if fg in ("#000", "#000000", "#111111", "#222222", "#333333") else pal["muted"]
                if "©" in str(widget.cget("text")):
                    new_fg = pal["hint"]
                widget.configure(bg=base_bg, fg=new_fg)
            elif isinstance(widget, tk.Entry):
                widget.configure(
                    bg=pal["input_bg"],
                    fg=pal["fg"],
                    insertbackground=pal["fg"],
                )
            elif isinstance(widget, tk.Listbox):
                widget.configure(
                    bg=pal["input_bg"],
                    fg=pal["fg"],
                    selectbackground=pal["accent"],
                    selectforeground=pal["accent_fg"],
                )
            elif isinstance(widget, tk.Checkbutton):
                widget.configure(
                    bg=base_bg,
                    fg=pal["fg"],
                    selectcolor=pal["input_bg"],
                    activebackground=base_bg,
                    activeforeground=pal["fg"],
                )
            elif isinstance(widget, ttk.Combobox):
                try:
                    widget.configure(style="WM.TCombobox")
                except tk.TclError:
                    pass
            elif isinstance(widget, tk.Button):
                txt = str(widget.cget("text"))
                is_dark = self._resolved_theme_mode() == "dark"
                sec_bg = "#E5E5EA" if is_dark else base_bg
                sec_fg = "#1C1C1E" if is_dark else pal["accent"]
                sec_active_bg = "#D1D1D6" if is_dark else base_bg
                is_cancel_btn = widget is getattr(self, "btn_cancel_task", None)
                is_preview_action_btn = widget in (
                    getattr(self, "btn_effect_preview", None),
                    getattr(self, "btn_effect_preview_again", None),
                    getattr(self, "btn_export_filtered_preview", None),
                    getattr(self, "btn_go", None),
                )
                if is_cancel_btn:
                    cancel_bg = "#2A2A2E" if is_dark else base_bg
                    cancel_dis_fg = "#FF9F9F" if is_dark else "#AA5555"
                    widget.configure(
                        bg=cancel_bg,
                        fg=pal["danger"],
                        activebackground=cancel_bg,
                        activeforeground=pal["danger"],
                        disabledforeground=cancel_dis_fg,
                        highlightthickness=1,
                        highlightbackground=pal["divider"],
                    )
                elif is_preview_action_btn or widget is getattr(self, "btn_preview_gallery", None) or widget is getattr(self, "btn_open_output", None):
                    widget.configure(
                        bg=sec_bg,
                        fg=sec_fg,
                        activebackground=sec_active_bg,
                        activeforeground=sec_fg,
                        disabledforeground=pal["hint"],
                        highlightthickness=1,
                        highlightbackground=pal["divider"],
                    )
                else:
                    widget.configure(
                        bg=("#E5E5EA" if is_dark else (pal["panel"] if not _in_form_panel(widget) else base_bg)),
                        fg=("#1C1C1E" if is_dark else pal["fg"]),
                        activebackground=("#D1D1D6" if is_dark else pal["panel"]),
                        activeforeground=("#1C1C1E" if is_dark else pal["fg"]),
                        disabledforeground=pal["hint"],
                        highlightthickness=1,
                        highlightbackground=pal["divider"],
                    )
            elif isinstance(widget, tk.Canvas):
                widget.configure(bg=base_bg, highlightbackground=pal["divider"])
        except tk.TclError:
            pass

        for child in widget.winfo_children():
            self._apply_theme_recursive(child, pal)

    def _apply_theme(self) -> None:
        if (self.var_ui_theme_mode.get() or "system").strip().lower() == "system":
            self._last_system_appearance = self._detect_macos_appearance()
        pal = self._theme_palette()
        self._theme_colors = dict(pal)
        try:
            self.configure(bg=pal["bg"])
        except tk.TclError:
            pass
        try:
            sty_ttk = ttk.Style(self)
            try:
                names = set(sty_ttk.theme_names())
                if self._resolved_theme_mode() == "dark" and "clam" in names:
                    sty_ttk.theme_use("clam")
                elif self._resolved_theme_mode() != "dark" and "aqua" in names:
                    sty_ttk.theme_use("aqua")
            except tk.TclError:
                pass
            sty_ttk.configure(
                "WM.TCombobox",
                fieldbackground=pal["input_bg"],
                foreground=pal["fg"],
                background=pal["panel"],
                arrowcolor=pal["fg"],
                bordercolor=pal["divider"],
                lightcolor=pal["divider"],
                darkcolor=pal["divider"],
            )
            sty_ttk.map(
                "WM.TCombobox",
                fieldbackground=[
                    ("readonly", pal["input_bg"]),
                    ("disabled", pal["panel"]),
                ],
                foreground=[
                    ("readonly", pal["fg"]),
                    ("disabled", pal["hint"]),
                ],
                selectbackground=[("readonly", pal["accent"])],
                selectforeground=[("readonly", pal["accent_fg"])],
                bordercolor=[
                    ("focus", pal["accent"]),
                    ("!focus", pal["divider"]),
                ],
                lightcolor=[
                    ("focus", pal["accent"]),
                    ("!focus", pal["divider"]),
                ],
                darkcolor=[
                    ("focus", pal["accent"]),
                    ("!focus", pal["divider"]),
                ],
            )
        except tk.TclError:
            pass
        try:
            self.option_add("*TCombobox*Listbox.background", pal["input_bg"])
            self.option_add("*TCombobox*Listbox.foreground", pal["fg"])
            self.option_add("*TCombobox*Listbox.selectBackground", pal["accent"])
            self.option_add("*TCombobox*Listbox.selectForeground", pal["accent_fg"])
        except tk.TclError:
            pass
        self._apply_theme_recursive(self, pal)
        self._apply_preview_action_buttons_baseline(pal)
        self._apply_button_hover_states(pal)
        try:
            if hasattr(self, "_form_panel"):
                self._form_panel.configure(
                    bg=pal["panel"],
                    fg=pal["muted"],
                    highlightbackground=pal["divider"],
                    highlightcolor=pal["divider"],
                    highlightthickness=1,
                    bd=0,
                )
            if hasattr(self, "_preview_panel"):
                self._preview_panel.configure(
                    bg=pal["panel"],
                    fg=pal["muted"],
                    highlightbackground=pal["divider"],
                    highlightcolor=pal["divider"],
                    highlightthickness=1,
                    bd=0,
                )
            if hasattr(self, "_footer_rule"):
                self._footer_rule.configure(bg=pal["divider"])
        except tk.TclError:
            pass
        if self.preview_gallery is not None:
            try:
                self.preview_gallery._pal = dict(pal)  # type: ignore[attr-defined]
                self.preview_gallery.configure(bg=pal["panel"])
                self._apply_theme_recursive(self.preview_gallery, pal)
                self.preview_gallery._canvas.configure(bg=pal["panel"])  # type: ignore[attr-defined]
                self.preview_gallery._inner.configure(bg=pal["panel"])  # type: ignore[attr-defined]
                self.preview_gallery._schedule_relayout()  # type: ignore[attr-defined]
            except Exception:
                pass

    def _apply_button_hover_states(self, pal: Dict[str, str]) -> None:
        def _bind_hover(btn: Optional[tk.Button], normal_bg: str, hover_bg: str, fg: str) -> None:
            if btn is None:
                return
            try:
                btn.configure(bg=normal_bg, fg=fg, activebackground=hover_bg, activeforeground=fg)
            except tk.TclError:
                return
            def _on_enter(_e: tk.Event, b: tk.Button = btn, hb: str = hover_bg, tf: str = fg) -> None:
                try:
                    if str(b.cget("state")) != tk.DISABLED:
                        b.configure(bg=hb, fg=tf)
                except tk.TclError:
                    pass
            def _on_leave(_e: tk.Event, b: tk.Button = btn, nb: str = normal_bg, tf: str = fg) -> None:
                try:
                    b.configure(bg=nb, fg=tf)
                except tk.TclError:
                    pass
            btn.bind("<Enter>", _on_enter)
            btn.bind("<Leave>", _on_leave)

        is_dark = self._resolved_theme_mode() == "dark"
        accent_hover = "#6BB2FF" if is_dark else "#2E95FF"
        panel_hover = "#3A3A40" if is_dark else "#EDEDF2"
        sec_bg = "#E5E5EA" if is_dark else pal["bg"]
        sec_hover = "#D1D1D6" if is_dark else panel_hover
        sec_fg = "#1C1C1E" if is_dark else pal["accent"]
        _bind_hover(self.btn_effect_preview, sec_bg, sec_hover, sec_fg)
        _bind_hover(self.btn_effect_preview_again, sec_bg, sec_hover, sec_fg)
        _bind_hover(self.btn_export_filtered_preview, sec_bg, sec_hover, sec_fg)
        _bind_hover(self.btn_go, sec_bg, sec_hover, sec_fg)
        _bind_hover(self.btn_preview_gallery, sec_bg, sec_hover, sec_fg)
        cancel_bg = "#2A2A2E" if is_dark else pal["bg"]
        _bind_hover(self.btn_cancel_task, cancel_bg, panel_hover, pal["danger"])
        _bind_hover(getattr(self, "btn_open_output", None), sec_bg, sec_hover, sec_fg)

    def _apply_preview_action_buttons_baseline(self, pal: Dict[str, str]) -> None:
        is_dark = self._resolved_theme_mode() == "dark"
        sec_bg = "#E5E5EA" if is_dark else pal["bg"]
        sec_fg = "#1C1C1E" if is_dark else pal["accent"]
        sec_active = "#D1D1D6" if is_dark else pal["panel"]
        for b in (
            getattr(self, "btn_effect_preview", None),
            getattr(self, "btn_effect_preview_again", None),
            getattr(self, "btn_export_filtered_preview", None),
            getattr(self, "btn_go", None),
            getattr(self, "btn_open_output", None),
        ):
            if b is None:
                continue
            try:
                b.configure(
                    bg=sec_bg,
                    fg=sec_fg,
                    activebackground=sec_active,
                    activeforeground=sec_fg,
                    disabledforeground=pal["hint"],
                    font=("SF Pro Text", UI_FONT_PT_MAIN),
                    highlightthickness=1,
                    highlightbackground=pal["divider"],
                    relief=tk.FLAT,
                    bd=0,
                    padx=10,
                    pady=6,
                    cursor="hand2",
                )
            except tk.TclError:
                pass

    def _build_ui(self) -> None:
        from wallpaper_maker.app_build_ui import build_ui
        build_ui(self)

    def _gui_export_snapshot(
        self,
    ) -> Tuple[str, int, int, bool, bool]:
        fmt = self._export_fmt_by_label.get(
            self._to_zh(self._combo_export_fmt.get()), "png"
        )
        jq = max(1, min(95, _parse_gui_int(self.var_jpeg_quality.get(), DEFAULT_JPEG_QUALITY)))
        wq = max(1, min(100, _parse_gui_int(self.var_webp_quality.get(), DEFAULT_WEBP_QUALITY)))
        wl = bool(self.var_webp_lossless.get())
        emb = bool(self.var_embed_srgb_icc.get())
        return fmt, jq, wq, wl, emb

    def _sync_export_controls_state(self, _evt: Optional[object] = None) -> None:
        fmt = self._export_fmt_by_label.get(
            self._to_zh(self._combo_export_fmt.get()), "png"
        )
        wl = False
        try:
            wl = bool(self.var_webp_lossless.get())
        except (tk.TclError, AttributeError):
            pass
        try:
            self._ent_jpeg_q.config(state=tk.NORMAL if fmt == "jpeg" else tk.DISABLED)
            self._ent_webp_q.config(
                state=tk.NORMAL if fmt == "webp" and not wl else tk.DISABLED
            )
            self._chk_webp_lossless.config(
                state=tk.NORMAL if fmt == "webp" else tk.DISABLED
            )
        except (tk.TclError, AttributeError):
            pass

    def _layout_zh_for_layout_key(self, layout_key: str) -> str:
        nk = _normalize_layout(layout_key)
        for k, zh in self._layout_choices:
            if k == nk:
                return zh
        return "标准网格"

    def _legacy_bg_style_to_parts(self, bg_style: str) -> Tuple[str, str]:
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

    def _bg_parts_to_legacy_style(self, base_style: str, overlay_style: str) -> str:
        b = (base_style or DEFAULT_BG_BASE_STYLE).strip().lower()
        o = (overlay_style or DEFAULT_BG_OVERLAY_STYLE).strip().lower()
        if b == "from_covers" and o == "frosted_glass":
            return "frosted_glass"
        if b == "from_covers" and o == "edge_vignette":
            return "edge_vignette"
        if b == "from_covers" and o == "geo_texture":
            return "geo_texture"
        if b == "magazine_gradient":
            return "magazine_gradient"
        return b

    def _export_label_for_fmt(self, fmt: str) -> str:
        f = _normalize_export_format(fmt)
        for lab, v in self._export_fmt_by_label.items():
            if v == f:
                return self._tr(lab)
        return self._tr("PNG（无损）")

    def _snapshot_scatter_params(self) -> Dict[str, Any]:
        smin = _parse_gui_float(self.var_scatter_smin.get(), 0.7)
        smax = _parse_gui_float(self.var_scatter_smax.get(), 1.45)
        if smin > smax:
            smin, smax = smax, smin
        return {
            "scatter_rotation": _read_double_var(self.var_rot, 15.0),
            "scatter_scale_min": smin,
            "scatter_scale_max": smax,
            "scatter_bleed": max(
                0.0,
                min(0.35, _parse_gui_float(self.var_scatter_bleed.get(), 0.1)),
            ),
            "scatter_shadow": bool(self.var_scatter_shadow.get()),
        }

    def _preset_collect(self) -> Dict[str, Any]:
        return collect_preset_data(self)

    def _preset_apply_data(self, data: Dict[str, Any]) -> None:
        apply_preset_data(self, data)

    def _on_apply_builtin_style(self) -> None:
        choice = self._combo_builtin_style.get()
        choice_zh = self._to_zh(choice)
        if choice_zh == BUILTIN_STYLE_PRESET_PLACEHOLDER:
            messagebox.showinfo(
                self._tr("内置风格"),
                self._tr(
                    "请先在列表中选择一种风格，再点「应用此风格」。\n应用后仍可任意修改版式、分辨率、文字与导出选项，属于半定制。"
                ),
            )
            return
        frag: Optional[Dict[str, Any]] = None
        for name, fd in BUILTIN_STYLE_PRESETS:
            if name == choice_zh:
                frag = fd
                break
        if frag is None:
            return
        merged = {**_empty_preset_template(), **frag}
        self._preset_apply_data(merged)
        messagebox.showinfo(
            self._tr("内置风格"),
            self._tr("已应用：{choice}\n下方参数已同步，可继续微调后生成预览或导出。", choice=choice),
        )

    def _on_export_preset_json(self) -> None:
        name = simpledialog.askstring(
            self._tr("导出预设"),
            self._tr("预设名称（写入 JSON 的 preset_name）："),
            initialvalue=self._tr("我的壁纸预设"),
        )
        if name is None:
            return
        path = filedialog.asksaveasfilename(
            title=self._tr("导出预设 JSON"),
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), (self._tr("全部"), "*.*")],
        )
        if not path:
            return
        blob = self._preset_collect()
        blob["preset_name"] = (name.strip() or self._tr("WallpaperMaker 预设"))
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(blob, f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showerror(self._tr("导出失败"), str(e))
            return
        messagebox.showinfo(self._tr("导出预设"), self._tr("已保存：\n{path}", path=path))

    def _on_import_preset_json(self) -> None:
        path = filedialog.askopenfilename(
            title=self._tr("导入预设 JSON"),
            filetypes=[("JSON", "*.json"), (self._tr("全部"), "*.*")],
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror(self._tr("导入失败"), str(e))
            return
        if not isinstance(raw, dict):
            messagebox.showerror(self._tr("导入失败"), self._tr("JSON 根对象须为对象（字典）。"))
            return
        try:
            self._preset_apply_data(raw)
        except (TypeError, ValueError, tk.TclError) as e:
            messagebox.showerror(self._tr("应用预设"), str(e))
            return
        pname = str(raw.get("preset_name", os.path.basename(path)))
        messagebox.showinfo(self._tr("导入预设"), self._tr("已载入：{name}", name=pname))

    def _on_restore_default_options(self) -> None:
        if not messagebox.askyesno(
            self._tr("恢复默认选项"),
            self._tr(
                "将所有参数恢复为程序安装时的默认值？\n\n包含：图源文件夹、输出目录、版式/背景/文字/水印、数值、导出格式与质量、预览批次及「沿用种子」等。\n效果图预览状态与种子提示将一并重置。"
            ),
        ):
            return
        payload = dict(_empty_preset_template())
        payload["source_folders"] = [
            os.path.abspath(os.path.expanduser(DEFAULT_IMAGE_FOLDER))
        ]
        payload["magazine_style"] = False
        try:
            self._preset_apply_data(payload)
        except (TypeError, ValueError, tk.TclError) as e:
            messagebox.showerror(self._tr("恢复默认"), str(e))
            return
        try:
            self.var_scatter_rot.set("14")
        except tk.TclError:
            pass
        try:
            self._combo_builtin_style.set(self._tr(BUILTIN_STYLE_PRESET_PLACEHOLDER))
        except (tk.TclError, AttributeError):
            pass
        self._effect_preview_ready = False
        self._last_preview_seed = None
        self._bg_live_preview_cache = None
        self.var_seed_status.set(
            self._tr("预览种子：—（成功生成效果图预览后显示）"),
        )
        try:
            self.btn_effect_preview_again.config(state=tk.DISABLED)
        except tk.TclError:
            pass
        try:
            self.lbl_status.config(
                text=self._tr("✅ 已恢复默认选项，可重新生成预览")
            )
        except tk.TclError:
            pass

    def _refresh_perf_hint(self) -> None:
        try:
            w = max(1, _parse_gui_int(self.var_width.get(), DEFAULT_WALLPAPER_WIDTH))
            h = max(1, _parse_gui_int(self.var_height.get(), DEFAULT_WALLPAPER_HEIGHT))
            count = max(1, _parse_gui_int(self.var_count.get(), DEFAULT_RANDOM_COUNT))
            batch = max(1, _parse_gui_int(self.var_batch_count.get(), 3))
            from wallpaper_maker.gui_utils import estimate_perf_hint
            text, color = estimate_perf_hint(w, h, count, batch)
            self._lbl_perf_hint.config(text=text, fg=color if color else "#999999")
        except (tk.TclError, AttributeError, ValueError):
            pass

    def _sync_bg_custom_controls(self) -> None:
        show = self.var_bg_base_style.get() in (
            "custom_gradient",
            "custom_gradient_radial",
        )
        st = "readonly" if show else "disabled"
        try:
            self._combo_bg_custom_top.configure(state=st)
            self._combo_bg_custom_bottom.configure(state=st)
        except (tk.TclError, AttributeError):
            pass

    def _on_preview_batch_sync_toggle(self) -> None:
        if self.var_preview_batch_sync.get():
            self.ent_preview_batch.config(state=tk.DISABLED)
        else:
            self.ent_preview_batch.config(state=tk.NORMAL)

    def _preview_batch_effective(self) -> Tuple[int, int]:
        """(效果图预览张数, 正式导出张数)。解绑时预览不超过 PREVIEW_BATCH_CAP_DECOUPLED。"""
        formal = max(1, _parse_gui_int(self.var_batch_count.get(), 3))
        if self.var_preview_batch_sync.get():
            return formal, formal
        pv = max(
            1,
            min(
                PREVIEW_BATCH_CAP_DECOUPLED,
                _parse_gui_int(self.var_preview_batch_count.get(), 3),
            ),
        )
        return pv, formal

    def _sync_source_listbox(self) -> None:
        self._list_source_folders.delete(0, tk.END)
        for p in self._source_folders:
            self._list_source_folders.insert(tk.END, p)

    def _norm_source_path(self, p: str) -> str:
        return os.path.normcase(os.path.abspath(os.path.expanduser(p.strip())))

    def _folder_weight(self, folder: str) -> float:
        key = self._norm_source_path(folder)
        return float(self._source_folder_weight_by_path.get(key, 1.0))

    def _add_source_folder(self) -> None:
        p = filedialog.askdirectory()
        if not p:
            return
        p = os.path.abspath(os.path.expanduser(p))
        norms = {self._norm_source_path(x) for x in self._source_folders}
        if self._norm_source_path(p) in norms:
            messagebox.showinfo(self._tr("图源"), self._tr("该文件夹已在列表中。"))
            return
        self._source_folders.append(p)
        self._sync_source_listbox()

    def _remove_selected_sources(self) -> None:
        sel = list(self._list_source_folders.curselection())
        if not sel:
            messagebox.showinfo(
                self._tr("图源"),
                self._tr("请在列表中选中要移除的文件夹（可多选）。"),
            )
            return
        if len(self._source_folders) <= 1:
            messagebox.showwarning(self._tr("图源"), self._tr("至少保留一个图源文件夹。"))
            return
        for i in reversed(sel):
            if 0 <= i < len(self._source_folders):
                key = self._norm_source_path(self._source_folders[i])
                del self._source_folders[i]
                self._source_folder_weight_by_path.pop(key, None)
        self._sync_source_listbox()

    def _set_selected_source_weight(self) -> None:
        sel = list(self._list_source_folders.curselection())
        if not sel:
            messagebox.showinfo(
                self._tr("图源权重"),
                self._tr("请先在列表中选中要设置权重的图源（可多选）。"),
            )
            return
        first_folder = self._source_folders[sel[0]]
        first_w = self._folder_weight(first_folder)
        val = simpledialog.askfloat(
            self._tr("图源权重"),
            self._tr("输入权重（>0）。\n示例：2.0 表示该文件夹被抽中的机会约为默认的 2 倍。"),
            initialvalue=max(0.01, float(first_w)),
            minvalue=0.0001,
        )
        if val is None:
            return
        v = max(0.0001, float(val))
        for i in sel:
            if 0 <= i < len(self._source_folders):
                key = self._norm_source_path(self._source_folders[i])
                self._source_folder_weight_by_path[key] = v
        self.lbl_status.config(
            text=self._tr("✅ 已设置 {n} 个图源权重为 {w}", n=len(sel), w=f"{v:.3g}")
        )

    def _reset_source_weights(self) -> None:
        self._source_folder_weight_by_path.clear()
        self.lbl_status.config(text=self._tr("✅ 图源权重已重置为默认 1.0"))

    def _browse_out_dir(self):
        p = filedialog.askdirectory()
        if p: self.var_out_dir.set(p)

    def _open_output_dir(self) -> None:
        import subprocess
        import sys

        raw = self.var_out_dir.get().strip()
        d = os.path.abspath(os.path.expanduser(raw)) if raw else ""
        if not d or not os.path.isdir(d):
            messagebox.showwarning(
                self._tr("打开输出目录"),
                self._tr("请先在参数「输出」中填写有效的文件夹路径。"),
            )
            return
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", d], check=False)
            elif sys.platform == "win32":
                os.startfile(d)  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", d], check=False)
        except OSError as e:
            messagebox.showerror(self._tr("打开输出目录"), str(e))

    def _notify_preview_gallery_withdrawn(self) -> None:
        notify_preview_gallery_withdrawn(self)

    def _refresh_preview_gallery_button_label(self) -> None:
        refresh_preview_gallery_button_label(self)

    def _init_preview_gallery_window(self) -> None:
        init_preview_gallery_window(self)

    def _ensure_preview_gallery_instance(self) -> None:
        ensure_preview_gallery_instance(self)

    def _ensure_preview_gallery(self) -> None:
        ensure_preview_gallery(self)

    def _toggle_preview_gallery(self) -> None:
        toggle_preview_gallery(self)

    def _initial_main_geometry(self) -> str:
        return initial_main_geometry(self)

    def _sync_preview_geometry(self) -> None:
        sync_preview_geometry(self)

    def _on_main_window_map(self, event: tk.Event) -> None:
        on_main_window_map(self, event)

    def _on_main_window_configure(self, event: tk.Event) -> None:
        on_main_window_configure(self, event)

    def _debounced_sync_preview_geometry(self) -> None:
        debounced_sync_preview_geometry(self)

    def _on_close_main_window(self) -> None:
        for job_name in ("_preview_geom_job", "_theme_follow_job"):
            cancel_named_job(self, attr_name=job_name)
        try:
            if self.preview_gallery is not None and self.preview_gallery.winfo_exists():
                self.preview_gallery.destroy()
        except Exception:
            pass
        self.destroy()

    def _update_preview(self, image_path: str) -> None:
        _pp_update_preview(self, image_path)

    def _replace_preview_gallery(self, paths: Sequence[str]) -> None:
        _pp_replace_gallery(self, paths)

    def _refresh_preview_filter_live(self) -> None:
        _pp_refresh_filter_live(self)

    def _refresh_preview_base_live(self) -> None:
        _pp_refresh_base_live(self)

    def _export_filtered_from_existing_previews(self) -> None:
        _ej_export_filtered(self)

    def _request_cancel_task(self) -> None:
        ev = self._task_cancel_event
        if ev is not None and not ev.is_set():
            ev.set()
            try:
                self.btn_cancel_task.config(
                    state=tk.DISABLED, text=self._tr("正在停止…")
                )
            except tk.TclError:
                pass

    def _task_bind_cancel(self, ev: threading.Event) -> None:
        self._task_cancel_event = ev
        try:
            self.btn_cancel_task.config(
                state=tk.NORMAL, text=self._tr("取消任务")
            )
        except tk.TclError:
            pass

    def _task_reset_after_job(self) -> None:
        self._task_cancel_event = None
        try:
            self.btn_cancel_task.config(
                state=tk.DISABLED, text=self._tr("取消任务")
            )
            self._progress.configure(value=0, maximum=100)
            self.lbl_task_phase.config(text="")
        except tk.TclError:
            pass

    def _maybe_auto_open_preview_gallery_for_effect_job(self) -> None:
        _pp_maybe_auto_open(self)

    def _on_effect_preview(self, is_regenerate: bool) -> None:
        _pp_on_effect_preview(self, is_regenerate)

    def _on_generate(self):
        _ej_on_generate(self)
