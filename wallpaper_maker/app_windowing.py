"""窗口与预览画廊几何逻辑（从 app.py 切分）。"""
from __future__ import annotations

import tkinter as tk
from typing import Any

from wallpaper_maker.app_task_scheduler import schedule_named_job
from wallpaper_maker.config import (
    UI_STUDIO_DEFAULT_WINDOW_H,
    UI_STUDIO_DEFAULT_WINDOW_W,
    UI_STUDIO_DISPLAY_LOGIC_W,
    UI_WINDOW_FALLBACK_MAX_H,
    UI_WINDOW_FALLBACK_MAX_W,
    UI_WINDOW_MIN_H,
    UI_WINDOW_MIN_W,
    UI_WINDOW_PREVIEW_GAP,
    UI_WINDOW_SCREEN_MARGIN,
)
from wallpaper_maker.preview_gallery import PreviewGalleryToplevel


def notify_preview_gallery_withdrawn(app: Any) -> None:
    app._preview_gallery_user_hidden = True
    refresh_preview_gallery_button_label(app)


def refresh_preview_gallery_button_label(app: Any) -> None:
    try:
        hide_mode = app._preview_gallery_user_hidden
        app.btn_preview_gallery.config(
            text=(
                app._tr("显示预览画廊")
                if hide_mode
                else app._tr("隐藏预览画廊")
            ),
        )
    except (tk.TclError, AttributeError):
        pass


def init_preview_gallery_window(app: Any) -> None:
    try:
        ensure_preview_gallery_instance(app)
        refresh_preview_gallery_button_label(app)
    except tk.TclError:
        pass


def ensure_preview_gallery_instance(app: Any) -> None:
    if app.preview_gallery is None:
        app.preview_gallery = PreviewGalleryToplevel(app)
        if app._preview_gallery_user_hidden:
            app.preview_gallery.withdraw()
        return
    try:
        if not app.preview_gallery.winfo_exists():
            app.preview_gallery = PreviewGalleryToplevel(app)
            if app._preview_gallery_user_hidden:
                app.preview_gallery.withdraw()
    except tk.TclError:
        app.preview_gallery = PreviewGalleryToplevel(app)
        if app._preview_gallery_user_hidden:
            app.preview_gallery.withdraw()


def ensure_preview_gallery(app: Any) -> None:
    ensure_preview_gallery_instance(app)
    if app.preview_gallery is None:
        return
    if not app._preview_gallery_user_hidden:
        try:
            app.preview_gallery.show_again()
            sync_preview_geometry(app)
        except tk.TclError:
            pass


def toggle_preview_gallery(app: Any) -> None:
    ensure_preview_gallery_instance(app)
    if app.preview_gallery is None:
        return
    app._preview_gallery_user_hidden = not app._preview_gallery_user_hidden
    if app._preview_gallery_user_hidden:
        try:
            app.preview_gallery.withdraw()
        except tk.TclError:
            pass
    else:
        try:
            app.preview_gallery.show_again()
            sync_preview_geometry(app)
        except tk.TclError:
            pass
    refresh_preview_gallery_button_label(app)


def initial_main_geometry(app: Any) -> str:
    """首次启动：以 Studio Display 典型逻辑分辨率为基准；其它屏幕则安全回退。"""
    sw = max(800, int(app.winfo_screenwidth()))
    sh = max(600, int(app.winfo_screenheight()))
    margin = UI_WINDOW_SCREEN_MARGIN
    gap = UI_WINDOW_PREVIEW_GAP
    reserved_top = 36
    reserved_bottom = 56
    max_h = max(UI_WINDOW_MIN_H, sh - reserved_top - reserved_bottom)
    max_w_each = max(UI_WINDOW_MIN_W, (sw - 2 * margin - gap) // 2)
    # Studio Display：用固定半屏宽 + 舒适高度，双窗与预览同宽同高、左右对称
    if sw >= UI_STUDIO_DISPLAY_LOGIC_W - 32:
        win_w = max(UI_WINDOW_MIN_W, min(UI_STUDIO_DEFAULT_WINDOW_W, max_w_each))
        win_h = max(UI_WINDOW_MIN_H, min(UI_STUDIO_DEFAULT_WINDOW_H, max_h))
    else:
        win_w = max(UI_WINDOW_MIN_W, min(UI_WINDOW_FALLBACK_MAX_W, max_w_each))
        win_h = max(UI_WINDOW_MIN_H, min(UI_WINDOW_FALLBACK_MAX_H, max_h))
    win_h = min(win_h, max_h)
    x = margin
    y = reserved_top
    return f"{win_w}x{win_h}+{x}+{y}"


def sync_preview_geometry(app: Any) -> None:
    if app.preview_gallery is None:
        return
    try:
        if not app.preview_gallery.winfo_exists():
            return
        if not app.preview_gallery.winfo_viewable():
            return
    except tk.TclError:
        return
    app.update_idletasks()
    ox, oy = app.winfo_rootx(), app.winfo_rooty()
    w = max(app.winfo_width(), UI_WINDOW_MIN_W)
    h = max(app.winfo_height(), UI_WINDOW_MIN_H)
    gap = UI_WINDOW_PREVIEW_GAP
    vw, vh = w, h
    tx, ty = ox + w + gap, oy
    try:
        g = app.preview_gallery
        g.geometry(f"{vw}x{vh}+{tx}+{ty}")
        g.update_idletasks()
        gx, gy = g.winfo_rootx(), g.winfo_rooty()
        dx, dy = tx - gx, ty - gy
        # macOS 等平台上外层窗口坐标与 geometry 意图常有 1 次偏差，按实测再平移对齐顶边/贴边
        if dx or dy:
            if abs(dx) <= 400 and abs(dy) <= 400:
                g.geometry(f"{vw}x{vh}+{tx + dx}+{ty + dy}")
    except tk.TclError:
        pass


def on_main_window_map(app: Any, event: tk.Event) -> None:
    if event.widget is not app:
        return
    app.after_idle(app._sync_preview_geometry)


def on_main_window_configure(app: Any, event: tk.Event) -> None:
    if event.widget is not app:
        return
    schedule_named_job(
        app,
        attr_name="_preview_geom_job",
        delay_ms=50,
        callback=app._debounced_sync_preview_geometry,
    )


def debounced_sync_preview_geometry(app: Any) -> None:
    app._preview_geom_job = None
    sync_preview_geometry(app)

