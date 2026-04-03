"""独立预览窗（单张可缩放 + 导航）。"""
from __future__ import annotations

import os
import zlib
from typing import Dict, List, Optional, Sequence

import tkinter as tk

from wallpaper_maker.core import apply_bg_overlay, apply_post_filter
from wallpaper_maker.config import (
    UI_FONT_PT_MAIN,
    UI_FONT_PT_SMALL,
    UI_FONT_PT_ZH_CAPTION,
    UI_WINDOW_MIN_H,
    UI_WINDOW_MIN_W,
)
from wallpaper_maker.gui_utils import _open_image_external, _popup_image_menu


class PreviewGalleryToplevel(tk.Toplevel):
    """单张预览模式：支持缩放、首末/前后翻页，适合精修底色与滤镜。"""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self._tr = getattr(master, "_tr", lambda s, **_k: s)
        self.title(self._tr("预览画廊"))
        self._owner = master
        self._pal: Dict[str, str] = dict(getattr(master, "_theme_colors", {}) or {})
        if not self._pal:
            self._pal = {
                "bg": "#FFFFFF",
                "panel": "#F5F5F7",
                "fg": "#111111",
                "muted": "#666666",
                "divider": "#E5E5EA",
                "danger": "#CC0000",
            }
        self.configure(bg=self._pal["panel"])
        try:
            # tkinter 没有 winfo_minsize()；应使用 minsize() 读取当前最小尺寸
            mw, mh = master.minsize()
            if int(mw) >= UI_WINDOW_MIN_W and int(mh) >= UI_WINDOW_MIN_H:
                self.minsize(int(mw), int(mh))
            else:
                self.minsize(UI_WINDOW_MIN_W, UI_WINDOW_MIN_H)
        except Exception:
            self.minsize(UI_WINDOW_MIN_W, UI_WINDOW_MIN_H)
        # 外框尺寸由主窗口同步，保证与主窗同大、左右对称；不在此窗单独拖拽改尺寸
        self.resizable(False, False)

        self._paths: List[str] = []
        self._index: int = 0
        self._photo: Optional[object] = None
        self._debounce_id: Optional[str] = None
        self._zoom_pct = tk.DoubleVar(value=100.0)
        self._pixel_exact: bool = False
        self._img_item: Optional[int] = None
        self._render_token: int = 0
        self._space_compare_active: bool = False
        self._space_compare_origin_idx: Optional[int] = None

        head = tk.Frame(self, bg=self._pal["bg"])
        head.pack(fill=tk.X, side=tk.TOP)
        tk.Label(
            head,
            text=self._tr("单张精修：切底色/叠层/滤镜可实时查看；支持缩放、翻页，空格可临时对比下一张。"),
            bg=self._pal["bg"],
            fg=self._pal["fg"],
            font=("SF Pro Text", UI_FONT_PT_SMALL),
            justify=tk.LEFT,
            wraplength=760,
        ).pack(anchor="w", padx=12, pady=(8, 4))

        toolbar = tk.Frame(head, bg=self._pal["bg"])
        toolbar.pack(fill=tk.X, padx=12, pady=(0, 8))
        self._btn_first = tk.Button(toolbar, text="|<", width=3, command=self._go_first)
        self._btn_prev = tk.Button(toolbar, text="<", width=3, command=self._go_prev)
        self._btn_next = tk.Button(toolbar, text=">", width=3, command=self._go_next)
        self._btn_last = tk.Button(toolbar, text=">|", width=3, command=self._go_last)
        self._btn_fit = tk.Button(toolbar, text=self._tr("适应"), command=self._set_zoom_fit)
        self._btn_100 = tk.Button(toolbar, text="100%", command=lambda: self._set_zoom(100.0))
        self._btn_px = tk.Button(toolbar, text=self._tr("1:1 像素"), command=self._set_zoom_pixel_exact)
        for b in (
            self._btn_first,
            self._btn_prev,
            self._btn_next,
            self._btn_last,
            self._btn_fit,
            self._btn_100,
            self._btn_px,
        ):
            b.pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(toolbar, text=self._tr("缩放"), bg=self._pal["bg"], fg=self._pal["muted"], font=("SF Pro Text", UI_FONT_PT_ZH_CAPTION)).pack(side=tk.LEFT, padx=(8, 4))
        self._zoom_scale = tk.Scale(
            toolbar,
            from_=20,
            to=300,
            orient=tk.HORIZONTAL,
            resolution=1,
            length=200,
            showvalue=True,
            variable=self._zoom_pct,
            command=lambda _v: self._schedule_relayout(),
            bg=self._pal["bg"],
            fg=self._pal["fg"],
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT,
        )
        self._zoom_scale.pack(side=tk.LEFT)

        self._lbl_index = tk.Label(
            toolbar, text="0/0", bg=self._pal["bg"], fg=self._pal["muted"], font=("SF Pro Text", UI_FONT_PT_ZH_CAPTION)
        )
        self._lbl_index.pack(side=tk.RIGHT, padx=(8, 0))
        self._lbl_name = tk.Label(
            toolbar, text="—", bg=self._pal["bg"], fg=self._pal["fg"], font=("SF Pro Text", UI_FONT_PT_ZH_CAPTION)
        )
        self._lbl_name.pack(side=tk.RIGHT, padx=(0, 8))

        wrap = tk.Frame(self, bg=self._pal["panel"])
        wrap.pack(fill=tk.BOTH, expand=True)
        self._hsb = tk.Scrollbar(wrap, orient=tk.HORIZONTAL)
        self._vsb = tk.Scrollbar(wrap, orient=tk.VERTICAL)
        self._canvas = tk.Canvas(
            wrap,
            bg=self._pal["panel"],
            highlightthickness=0,
            xscrollcommand=self._hsb.set,
            yscrollcommand=self._vsb.set,
        )
        self._hsb.config(command=self._canvas.xview)
        self._vsb.config(command=self._canvas.yview)
        self._hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._inner = tk.Frame(self._canvas, bg=self._pal["panel"])  # 供外部主题刷新兼容

        self._canvas.bind("<Configure>", lambda _e: self._schedule_relayout())
        self._canvas.bind("<MouseWheel>", self._on_wheel)
        self._canvas.bind("<Button-4>", self._on_wheel_linux)
        self._canvas.bind("<Button-5>", self._on_wheel_linux)
        self._canvas.bind("<Button-1>", lambda _e: self._open_current())
        self._canvas.bind("<ButtonRelease-3>", self._popup_current_menu)
        self._canvas.bind("<ButtonRelease-2>", self._popup_current_menu)
        self.bind("<Left>", lambda _e: self._go_prev())
        self.bind("<Right>", lambda _e: self._go_next())
        self.bind("<KeyPress-space>", self._on_space_press)
        self.bind("<KeyRelease-space>", self._on_space_release)

        try:
            self.transient(master)
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self._on_user_close)
        try:
            self.withdraw()
        except tk.TclError:
            pass

    def _on_user_close(self) -> None:
        self.withdraw()
        try:
            cb = getattr(self._owner, "_notify_preview_gallery_withdrawn", None)
            if callable(cb):
                cb()
        except Exception:
            pass

    def show_again(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_set()

    def clear(self) -> None:
        self._paths.clear()
        self._index = 0
        self._space_compare_active = False
        self._space_compare_origin_idx = None
        self._schedule_relayout()

    def set_paths(self, paths: Sequence[str]) -> None:
        self._paths = list(paths)
        if not self._paths:
            self._index = 0
        else:
            self._index = max(0, min(self._index, len(self._paths) - 1))
        self._space_compare_active = False
        self._space_compare_origin_idx = None
        self._schedule_relayout()

    def add_path(self, path: str) -> None:
        self._paths.append(path)
        self._index = max(0, len(self._paths) - 1)
        self._schedule_relayout()

    def _go_first(self) -> None:
        if self._paths:
            self._index = 0
            self._schedule_relayout()

    def _go_last(self) -> None:
        if self._paths:
            self._index = len(self._paths) - 1
            self._schedule_relayout()

    def _go_prev(self) -> None:
        if self._paths:
            self._index = (self._index - 1) % len(self._paths)
            self._schedule_relayout()

    def _go_next(self) -> None:
        if self._paths:
            self._index = (self._index + 1) % len(self._paths)
            self._schedule_relayout()

    def _set_zoom(self, value: float) -> None:
        try:
            self._pixel_exact = False
            self._zoom_pct.set(max(20.0, min(300.0, float(value))))
        except tk.TclError:
            pass
        self._schedule_relayout()

    def _set_zoom_fit(self) -> None:
        self._pixel_exact = False
        self._set_zoom(100.0)

    def _set_zoom_pixel_exact(self) -> None:
        self._pixel_exact = True
        self._schedule_relayout()

    def _on_wheel(self, event: tk.Event) -> None:
        d = getattr(event, "delta", 0) or 0
        if d == 0:
            return
        if bool(getattr(event, "state", 0) & 0x0004):  # Ctrl
            self._pixel_exact = False
            self._set_zoom(self._zoom_pct.get() + (8 if d > 0 else -8))
            return
        self._canvas.yview_scroll(-3 if d > 0 else 3, "units")

    def _on_space_press(self, _event: tk.Event) -> str:
        if self._space_compare_active or not self._paths or len(self._paths) <= 1:
            return "break"
        self._space_compare_active = True
        self._space_compare_origin_idx = self._index
        self._index = (self._index + 1) % len(self._paths)
        self._schedule_relayout()
        return "break"

    def _on_space_release(self, _event: tk.Event) -> str:
        if not self._space_compare_active:
            return "break"
        self._space_compare_active = False
        if self._space_compare_origin_idx is not None:
            self._index = self._space_compare_origin_idx
        self._space_compare_origin_idx = None
        self._schedule_relayout()
        return "break"

    def _on_wheel_linux(self, event: tk.Event) -> None:
        n = getattr(event, "num", 0)
        self._canvas.yview_scroll(-3 if n == 4 else 3, "units")

    def _open_current(self) -> None:
        if not self._paths:
            return
        p = self._paths[self._index]
        _open_image_external(p)

    def _popup_current_menu(self, event: tk.Event) -> str:
        if self._paths:
            _popup_image_menu(self, event, self._paths[self._index])
        return "break"

    def _schedule_relayout(self) -> None:
        if self._debounce_id is not None:
            try:
                self.after_cancel(self._debounce_id)
            except tk.TclError:
                pass
            self._debounce_id = None
        self._debounce_id = self.after(60, self._render_current)

    def _render_current(self) -> None:
        self._debounce_id = None
        self._render_token += 1
        if not self._paths:
            self._canvas.delete("all")
            self._canvas.configure(scrollregion=(0, 0, 1, 1))
            self._lbl_index.config(text="0/0")
            self._lbl_name.config(text="—")
            return
        idx = max(0, min(self._index, len(self._paths) - 1))
        self._index = idx
        path = self._paths[idx]
        self._lbl_index.config(text=f"{idx + 1}/{len(self._paths)}")
        self._lbl_name.config(text=os.path.basename(path))

        from PIL import Image, ImageEnhance, ImageTk

        try:
            with Image.open(path) as im0:
                im = im0.convert("RGB")
            bo = str(getattr(getattr(self._owner, "var_bg_overlay_style", None), "get", lambda: "none")()).strip().lower()
            bo_strength = float(getattr(getattr(self._owner, "var_bg_overlay_strength", None), "get", lambda: 70.0)())
            fs = str(getattr(getattr(self._owner, "var_filter_style", None), "get", lambda: "none")()).strip().lower()
            fs_strength = float(getattr(getattr(self._owner, "var_filter_strength", None), "get", lambda: 70.0)())
            compare_boost = bool(
                getattr(
                    getattr(self._owner, "var_preview_compare_boost", None),
                    "get",
                    lambda: False,
                )()
            )

            def _boost_strength(v: float) -> float:
                vv = max(0.0, min(100.0, float(v)))
                if not compare_boost or vv <= 0.0:
                    return vv
                # 仅预览增强：中高强度拉开差异，低强度保留细腻过渡。
                return min(100.0, vv * 1.35 + 12.0)

            bo_strength_eff = _boost_strength(bo_strength)
            fs_strength_eff = _boost_strength(fs_strength)
            has_effect = False
            if bo and bo not in ("none", "off"):
                seed_bo = int(zlib.crc32((os.path.abspath(path) + "_bo").encode("utf-8")) & 0x7FFFFFFF)
                im = apply_bg_overlay(im, bo, seed=seed_bo, strength=bo_strength_eff)
                has_effect = True
            if fs and fs not in ("none", "off"):
                seed_fs = int(zlib.crc32(os.path.abspath(path).encode("utf-8")) & 0x7FFFFFFF)
                im = apply_post_filter(im, fs, seed=seed_fs, strength=fs_strength_eff)
                has_effect = True
            if compare_boost and has_effect:
                # 预览局部对比补偿，让风格切换更易感知；不进入导出链路。
                im = ImageEnhance.Contrast(im).enhance(1.08)
                im = ImageEnhance.Color(im).enhance(1.04)
        except Exception:
            self._canvas.delete("all")
            self._canvas.create_text(20, 20, anchor="nw", text=self._tr("无法加载预览"), fill=self._pal["danger"], font=("SF Pro Text", UI_FONT_PT_MAIN))
            return

        cw = max(1, self._canvas.winfo_width())
        ch = max(1, self._canvas.winfo_height())
        fit = min(cw / max(1, im.width), ch / max(1, im.height))
        fit = max(0.02, min(8.0, fit))
        if self._pixel_exact:
            scale = 1.0
        else:
            zoom = max(0.2, min(3.0, float(self._zoom_pct.get()) / 100.0))
            scale = fit * zoom
        nw = max(1, int(round(im.width * scale)))
        nh = max(1, int(round(im.height * scale)))
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.BICUBIC
        im = im.resize((nw, nh), resample)
        ph = ImageTk.PhotoImage(im)
        self._photo = ph

        self._canvas.delete("all")
        x = max(0, (cw - nw) // 2)
        y = max(0, (ch - nh) // 2)
        self._img_item = self._canvas.create_image(x, y, image=ph, anchor="nw")
        self._canvas.configure(scrollregion=(0, 0, max(cw, nw), max(ch, nh)))

