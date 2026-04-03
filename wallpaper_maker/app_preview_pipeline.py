"""预览刷新与画廊缓存管道 —— 从 app.py 抽取的预览相关业务逻辑。

所有公开函数的第一个参数均为 ``app`` (WallPaperApp 实例)，
app.py 中对应方法只需转调即可。
"""
from __future__ import annotations

import os
import random
import tempfile
import threading
import tkinter as tk
from typing import Any, Dict, List, Optional, Sequence, Tuple

from wallpaper_maker.config import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RANDOM_COUNT,
    DEFAULT_STAMP_SIZE,
    DEFAULT_TEXT_SIZE,
    DEFAULT_WALLPAPER_HEIGHT,
    DEFAULT_WALLPAPER_WIDTH,
)
from wallpaper_maker.core import create_wallpaper
from wallpaper_maker.gui_utils import _parse_gui_int, _preview_render_params
from wallpaper_maker.image_filter import filter_readable_image_paths
from wallpaper_maker.sampling import get_image_paths_from_folders, pick_paths_by_strategy
from wallpaper_maker.skip_stats import ImageSourceSkipStats

# ---------------------------------------------------------------------------
# 画廊更新小函数
# ---------------------------------------------------------------------------


def update_preview(app: Any, image_path: str) -> None:
    """向画廊追加一张预览路径，若画廊当前未被用户隐藏则自动显示。"""
    try:
        app._ensure_preview_gallery_instance()
        if app.preview_gallery is None:
            return
        app.preview_gallery.add_path(image_path)
        if not app._preview_gallery_user_hidden:
            app.preview_gallery.show_again()
            app._sync_preview_geometry()
    except Exception:
        pass


def replace_preview_gallery(app: Any, paths: Sequence[str]) -> None:
    """用一组新路径替换画廊全部预览，若画廊未隐藏则自动显示。"""
    try:
        app._ensure_preview_gallery_instance()
        if app.preview_gallery is None:
            return
        app.preview_gallery.set_paths(paths)
        if not app._preview_gallery_user_hidden:
            app.preview_gallery.show_again()
            app._sync_preview_geometry()
    except Exception:
        pass


def refresh_preview_filter_live(app: Any) -> None:
    """切换滤镜时，对已生成预览图做实时缩略图重渲染（不重排版、不重抽样）。"""
    try:
        app._ensure_preview_gallery_instance()
        if app.preview_gallery is not None:
            app.preview_gallery._schedule_relayout()  # type: ignore[attr-defined]
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 底色实时重渲染
# ---------------------------------------------------------------------------


def refresh_preview_base_live(app: Any) -> None:
    """切换背景底色时，基于缓存的抽样结果快速重渲染现有效果图预览。"""
    _tr = app._tr
    if not app.var_live_bg_base_preview.get():
        return
    if app._task_cancel_event is not None or app._bg_live_preview_inflight:
        return
    cache = app._bg_live_preview_cache or {}
    picked_batches = list(cache.get("picked_batches") or [])
    seeds = list(cache.get("seeds") or [])
    slot_paths = list(cache.get("slot_paths") or [])
    if not picked_batches or not slot_paths:
        return
    if not app._effect_preview_ready:
        return

    meta = dict(cache.get("meta") or {})
    if not meta:
        return

    bg_base_style_snap = app.var_bg_base_style.get()
    custom_bg_snap: Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = None
    if bg_base_style_snap in ("custom_gradient", "custom_gradient_radial"):
        custom_bg_snap = (
            app.text_colors[app.var_bg_custom_top.get()],
            app.text_colors[app.var_bg_custom_bottom.get()],
        )

    app._bg_live_preview_inflight = True
    app.btn_effect_preview.config(state=tk.DISABLED)
    app.btn_effect_preview_again.config(state=tk.DISABLED)
    app.btn_export_filtered_preview.config(state=tk.DISABLED)
    app.btn_go.config(state=tk.DISABLED)
    app.lbl_status.config(text=_tr("⏳ 正在实时重渲染底色预览…"))

    def work() -> None:
        cancel_ev = threading.Event()
        app.after(0, lambda: app._task_bind_cancel(cancel_ev))
        err_msg = ""
        done_count = 0
        total = min(len(picked_batches), len(seeds), len(slot_paths))
        try:
            app.after(
                0,
                lambda: app._progress.configure(maximum=max(1, total), value=0),
            )
            for i in range(total):
                if cancel_ev.is_set():
                    break
                picked = list(picked_batches[i])
                if not picked:
                    continue
                seed_i = int(seeds[i])
                slot = str(slot_paths[i])
                create_wallpaper(
                    picked,
                    len(picked),
                    int(meta["pw"]),
                    int(meta["ph"]),
                    str(meta["out_dir"]),
                    str(meta["custom_text"]),
                    layout=str(meta["layout"]),
                    bg_base_style=bg_base_style_snap,
                    bg_overlay_style="none",
                    bg_overlay_strength=0,
                    bg_style=app._bg_parts_to_legacy_style(bg_base_style_snap, "none"),
                    custom_bg_gradient=custom_bg_snap,
                    text_size=int(meta["ts"]),
                    stamp_size=int(meta["ss"]),
                    text_pos=str(meta["text_pos"]),
                    text_color=tuple(meta["text_color"]),
                    stroke_color=tuple(meta["stroke_color"]),
                    margin=int(meta["m"]),
                    gap=int(meta["g"]),
                    seed=seed_i,
                    save_path_override=slot,
                    show_stamp=bool(meta["show_stamp"]),
                    stamp_place=str(meta["stamp_place"]),
                    export_format="png",
                    embed_srgb_icc=False,
                    style_intensity=str(meta["style_intensity"]),
                    enable_aesthetic_rules=bool(meta["enable_rules"]),
                    skip_path_validation=True,
                    **dict(meta["scatter_snap"]),
                )
                done_count = i + 1
                app.after(
                    0,
                    lambda n=done_count, t=total: (
                        app._progress.configure(value=n),
                        app.lbl_task_phase.config(
                            text=_tr("阶段 1/1：底色实时重渲染 · 第 {n}/{t} 张", n=n, t=t)
                        ),
                    ),
                )
        except Exception as e:
            err_msg = str(e)

        def done() -> None:
            app._task_reset_after_job()
            app._bg_live_preview_inflight = False
            app.btn_go.config(state=tk.NORMAL)
            app.btn_effect_preview.config(state=tk.NORMAL)
            app.btn_export_filtered_preview.config(state=tk.NORMAL)
            if app._effect_preview_ready:
                app.btn_effect_preview_again.config(state=tk.NORMAL)
            if err_msg:
                app.lbl_status.config(text=_tr("❌ 底色实时预览失败"))
                from tkinter import messagebox
                messagebox.showerror(_tr("底色实时预览"), err_msg)
                return
            replace_preview_gallery(app, slot_paths[:total])
            app.lbl_status.config(
                text=_tr("✅ 底色实时预览已更新（{n}/{t} 张）", n=done_count, t=total)
            )

        app.after(0, done)

    threading.Thread(target=work, daemon=True).start()


# ---------------------------------------------------------------------------
# 效果图预览入口
# ---------------------------------------------------------------------------


def maybe_auto_open_preview_gallery_for_effect_job(app: Any) -> None:
    if not app.var_auto_show_gallery_on_preview.get():
        return
    app._preview_gallery_user_hidden = False
    app._ensure_preview_gallery_instance()
    if app.preview_gallery is not None:
        try:
            app.preview_gallery.show_again()
            app._sync_preview_geometry()
        except tk.TclError:
            pass
    app._refresh_preview_gallery_button_label()


def on_effect_preview(app: Any, is_regenerate: bool) -> None:  # noqa: C901
    """渲染效果图预览（低分辨率）。"""
    _tr = app._tr
    app.btn_effect_preview.config(state=tk.DISABLED)
    app.btn_effect_preview_again.config(state=tk.DISABLED)
    app.btn_go.config(state=tk.DISABLED)
    app.lbl_status.config(
        text=_tr("⏳ 正在换一版预览…") if is_regenerate else _tr("⏳ 正在渲染效果图预览…")
    )

    count = max(1, _parse_gui_int(app.var_count.get(), DEFAULT_RANDOM_COUNT))
    w = max(1, _parse_gui_int(app.var_width.get(), DEFAULT_WALLPAPER_WIDTH))
    h = max(1, _parse_gui_int(app.var_height.get(), DEFAULT_WALLPAPER_HEIGHT))
    out_dir = app.var_out_dir.get()
    margin = max(0, _parse_gui_int(app.var_margin.get(), 40))
    gap = max(0, _parse_gui_int(app.var_gap.get(), 30))
    custom_text = app.var_text.get()
    layout = app._layout_by_label[app.var_layout_label.get()]
    bg_base_style_snap = app.var_bg_base_style.get()
    bg_overlay_style_snap = app.var_bg_overlay_style.get()
    bg_overlay_strength_snap = max(
        0, min(100, int(round(float(app.var_bg_overlay_strength.get()))))
    )
    filter_strength_snap = max(
        0, min(100, int(round(float(app.var_filter_strength.get()))))
    )
    custom_bg_snap: Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = None
    if bg_base_style_snap in ("custom_gradient", "custom_gradient_radial"):
        custom_bg_snap = (
            app.text_colors[app.var_bg_custom_top.get()],
            app.text_colors[app.var_bg_custom_bottom.get()],
        )
    scatter_snap = app._snapshot_scatter_params()
    text_sz = max(1, _parse_gui_int(app.var_text_size.get(), DEFAULT_TEXT_SIZE))
    stamp_sz = max(1, _parse_gui_int(app.var_stamp_size.get(), DEFAULT_STAMP_SIZE))
    text_pos = app.var_text_pos.get()
    text_color = app.text_colors[app.var_text_color.get()]
    stroke_color = app.text_colors[app.var_stroke_color.get()]
    show_stamp_snap = app.var_show_stamp.get()
    stamp_place_snap = app.var_stamp_place.get()

    preview_batch, formal_n = app._preview_batch_effective()
    folders_snap = list(app._source_folders)
    recursive_snap = app.var_recursive.get()
    style_intensity_snap = app.var_style_intensity.get()
    enable_aesthetic_rules_snap = bool(app.var_enable_aesthetic_rules.get())
    sampling_strategy_snap = app.var_sampling_strategy.get()
    weight_snap = {
        app._norm_source_path(k): float(v)
        for k, v in app._source_folder_weight_by_path.items()
        if float(v) > 0
    }
    manual_seed_str = app.var_seed.get().strip()
    manual_seed: Optional[int] = None
    if manual_seed_str:
        try:
            manual_seed = int(manual_seed_str)
        except ValueError:
            pass

    maybe_auto_open_preview_gallery_for_effect_job(app)
    try:
        app._ensure_preview_gallery_instance()
        if app.preview_gallery is not None:
            app.preview_gallery.clear()
    except Exception:
        pass

    def work() -> None:
        cancel_ev = threading.Event()
        app.after(0, lambda: app._task_bind_cancel(cancel_ev))

        err_msg = ""
        pvw, phw = 0, 0
        base_seed = 0
        total = preview_batch
        regen = is_regenerate
        user_cancelled = False
        done_count = 0
        image_paths: List[str] = []
        pool_skip_stats = ImageSourceSkipStats()
        cached_picked_batches: List[List[str]] = []
        cached_seeds: List[int] = []
        cached_slots: List[str] = []

        try:

            def phase1_ui() -> None:
                app.lbl_task_phase.config(
                    text=_tr("阶段 1/2：扫描图源并建立图片池（可随时取消）…"),
                )
                app._progress.configure(maximum=100, value=0)

            app.after(0, phase1_ui)

            if cancel_ev.is_set():
                user_cancelled = True
            else:
                pf_counts: List[Tuple[str, int]] = []
                pf_paths: List[Tuple[str, List[str]]] = []
                raw_paths = get_image_paths_from_folders(
                    folders_snap,
                    recursive=recursive_snap,
                    per_folder_counts=pf_counts,
                    per_folder_paths=pf_paths,
                )
                if cancel_ev.is_set():
                    user_cancelled = True
                else:
                    image_paths, pre_drop = filter_readable_image_paths(raw_paths)
                    pool_skip_stats.pre_filter_skipped += pre_drop
                good_set = set(image_paths)
                group_paths_good: List[Tuple[str, List[str]]] = []
                for folder_abs, plist in pf_paths:
                    keep = [p for p in plist if p in good_set]
                    group_paths_good.append((folder_abs, keep))

                pool_detail = "　|　".join(
                    f"{name}: {cnt}" for name, cnt in pf_counts
                ) if pf_counts else ""

                def _pool_ui(
                    d: str = pool_detail,
                    n: int = len(image_paths),
                    s: str = app._sampling_mode_zh_by_key.get(
                        sampling_strategy_snap, "按图片数量自然比例"
                    ),
                ) -> None:
                    s_disp = _tr(s)
                    app.lbl_task_phase.config(
                        text=(
                            _tr("图源池 {n} 张 · {s}（{d}）", n=n, s=s_disp, d=d)
                            if d
                            else _tr("图源池 {n} 张 · {s}", n=n, s=s_disp)
                        ),
                    )

                app.after(0, _pool_ui)

            if cancel_ev.is_set():
                user_cancelled = True
            elif not image_paths:
                err_msg = _tr("未找到任何图片，请检查图源文件夹与「递归子目录」设置。")
                if pool_skip_stats.pre_filter_skipped:
                    err_msg += (
                        _tr("（扫描到 {n} 个路径但均不可读或过大）", n=pool_skip_stats.pre_filter_skipped)
                    )
            else:
                pvw, phw, m, g, ts, ss, _ = _preview_render_params(
                    w, h, margin, gap, text_sz, stamp_sz
                )
                if manual_seed is not None:
                    if regen and app._last_preview_seed is not None:
                        base_seed = (int(app._last_preview_seed) + 10007) % (2**30)
                    else:
                        base_seed = manual_seed
                else:
                    base_seed = random.randrange(1, 2**30)

                def phase2_ui() -> None:
                    app.lbl_task_phase.config(
                        text=(
                            _tr("阶段 2/2：效果图渲染 · 第 0/{total} 张（约 {w}×{h}）", total=total, w=pvw, h=phw)
                        ),
                    )
                    app._progress.configure(maximum=max(1, total), value=0)

                app.after(0, phase2_ui)

                for i in range(total):
                    if cancel_ev.is_set():
                        user_cancelled = True
                        break
                    seed_i = (base_seed + i) % (2**30)
                    slot_path = os.path.join(
                        tempfile.gettempdir(),
                        f"WallpaperMaker_effect_preview_{i}.png",
                    )
                    rng_snap = random.getstate()
                    try:
                        picked = pick_paths_by_strategy(
                            image_paths,
                            count,
                            strategy=sampling_strategy_snap,
                            per_folder_paths=group_paths_good,
                            folder_weight_by_path=weight_snap,
                            seed=seed_i,
                        )
                        if not picked:
                            raise ValueError(_tr("按当前抽样策略未选到可用图源。"))
                        path = create_wallpaper(
                            picked,
                            len(picked),
                            pvw,
                            phw,
                            out_dir,
                            custom_text,
                            layout=layout,
                            bg_base_style=bg_base_style_snap,
                            bg_overlay_style="none",
                            bg_overlay_strength=0,
                            bg_style=app._bg_parts_to_legacy_style(
                                bg_base_style_snap, "none"
                            ),
                            filter_style="none",
                            filter_strength=filter_strength_snap,
                            custom_bg_gradient=custom_bg_snap,
                            text_size=ts,
                            stamp_size=ss,
                            text_pos=text_pos,
                            text_color=text_color,
                            stroke_color=stroke_color,
                            margin=m,
                            gap=g,
                            seed=seed_i,
                            save_path_override=slot_path,
                            show_stamp=show_stamp_snap,
                            stamp_place=stamp_place_snap,
                            export_format="png",
                            embed_srgb_icc=False,
                            style_intensity=style_intensity_snap,
                            enable_aesthetic_rules=enable_aesthetic_rules_snap,
                            skip_stats=pool_skip_stats,
                            skip_path_validation=True,
                            **scatter_snap,
                        )
                        cached_picked_batches.append(list(picked))
                        cached_seeds.append(int(seed_i))
                        cached_slots.append(str(path))
                    finally:
                        random.setstate(rng_snap)

                    done_count = i + 1

                    def progress(
                        p: str = path,
                        n: int = done_count,
                        t: int = total,
                        pw: int = pvw,
                        ph: int = phw,
                        sk: str = pool_skip_stats.summary(app.var_ui_language.get()),
                    ) -> None:
                        update_preview(app, p)
                        app._progress.configure(value=n)
                        app.lbl_task_phase.config(
                            text=(
                                _tr("阶段 2/2：效果图渲染 · 第 {n}/{t} 张（约 {w}×{h}）", n=n, t=t, w=pw, h=ph)
                            ),
                        )
                        app.lbl_status.config(
                            text=(
                                _tr("⏳ 效果图预览 {n}/{t} · 约 {w}×{h} · 阶段 2/2{sk}", n=n, t=t, w=pw, h=ph, sk=sk)
                            ),
                        )

                    app.after(0, progress)
        except Exception as e:
            err_msg = str(e)

        def done() -> None:
            app._task_reset_after_job()
            if err_msg:
                app._bg_live_preview_cache = None
                app.lbl_status.config(text=_tr("❌ 效果图预览失败"))
                from tkinter import messagebox
                messagebox.showerror(_tr("效果图预览"), err_msg)
            elif user_cancelled:
                app._effect_preview_ready = done_count > 0
                if done_count < total:
                    app._last_preview_seed = None
                    app._bg_live_preview_cache = None
                    app.var_seed_status.set(
                        _tr("预览曾中断：未完成有效整套预览前，请勿勾选「沿用预览种子」。")
                    )
                tag = _tr("换版") if regen else _tr("效果图")
                dim = _tr("（约 {w}×{h}）", w=pvw, h=phw) if pvw and phw else ""
                app.lbl_status.config(
                    text=_tr("⏹ 已取消{tag}预览，完成 {n}/{t} 张{dim}", tag=tag, n=done_count, t=total, dim=dim),
                )
            else:
                app._effect_preview_ready = True
                app._last_preview_seed = base_seed
                app._bg_live_preview_cache = {
                    "picked_batches": cached_picked_batches[:done_count],
                    "seeds": cached_seeds[:done_count],
                    "slot_paths": cached_slots[:done_count],
                    "meta": {
                        "pw": pvw,
                        "ph": phw,
                        "m": m,
                        "g": g,
                        "ts": ts,
                        "ss": ss,
                        "out_dir": out_dir,
                        "custom_text": custom_text,
                        "layout": layout,
                        "text_pos": text_pos,
                        "text_color": text_color,
                        "stroke_color": stroke_color,
                        "show_stamp": show_stamp_snap,
                        "stamp_place": stamp_place_snap,
                        "style_intensity": style_intensity_snap,
                        "enable_rules": enable_aesthetic_rules_snap,
                        "scatter_snap": dict(scatter_snap),
                    },
                }
                if formal_n == total:
                    seed_hint = (
                        _tr("预览基准种子：{seed} | 预览与正式均为 {n} 张，勾选「沿用预览种子」后导出与预览 1:1 对齐。", seed=base_seed, n=total)
                    )
                else:
                    m_part = min(total, formal_n)
                    seed_hint = (
                        _tr("预览基准种子：{seed} | 预览 {pn} 张 / 正式 {fn} 张。沿用种子时第 1-{m} 张与预览一一对应；其余正式图继续 +seed。", seed=base_seed, pn=total, fn=formal_n, m=m_part)
                    )
                app.var_seed_status.set(seed_hint)
                tag = _tr("换版") if regen else _tr("效果图")
                sk_done = pool_skip_stats.summary(app.var_ui_language.get())
                app.lbl_status.config(
                    text=(
                        _tr(
                            "✅ {tag}预览 {n} 张完成（低清约 {pw}×{ph}）；需要高清可勾选种子后点「🚀 正式生成壁纸」导出 {w}×{h}{sk}",
                            tag=tag,
                            n=total,
                            pw=pvw,
                            ph=phw,
                            w=w,
                            h=h,
                            sk=sk_done,
                        )
                    ),
                )
            app.btn_go.config(state=tk.NORMAL)
            app.btn_effect_preview.config(state=tk.NORMAL)
            if app._effect_preview_ready:
                app.btn_effect_preview_again.config(state=tk.NORMAL)

        app.after(0, done)

    threading.Thread(target=work, daemon=True).start()
