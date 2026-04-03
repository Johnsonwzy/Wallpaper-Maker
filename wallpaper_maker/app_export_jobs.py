"""导出任务编排 —— 从 app.py 抽取的正式导出与滤镜批量导出逻辑。

所有公开函数的第一个参数均为 ``app`` (WallPaperApp 实例)，
app.py 中对应方法只需转调即可。
"""
from __future__ import annotations

import os
import random
import threading
import time
import tkinter as tk
import zlib
from tkinter import messagebox
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from wallpaper_maker.config import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RANDOM_COUNT,
    DEFAULT_STAMP_SIZE,
    DEFAULT_TEXT_SIZE,
    DEFAULT_WALLPAPER_HEIGHT,
    DEFAULT_WALLPAPER_WIDTH,
)
from wallpaper_maker.core import apply_post_filter, create_wallpaper
from wallpaper_maker.gui_utils import _parse_gui_int
from wallpaper_maker.image_filter import filter_readable_image_paths
from wallpaper_maker.sampling import get_image_paths_from_folders, pick_paths_by_strategy
from wallpaper_maker.skip_stats import ImageSourceSkipStats

# ---------------------------------------------------------------------------
# 滤镜批量导出
# ---------------------------------------------------------------------------


def export_filtered_from_existing_previews(app: Any) -> None:  # noqa: C901
    """将当前滤镜批量应用到现有预览并导出（不重排版）。"""
    _tr = app._tr
    try:
        app._ensure_preview_gallery_instance()
    except Exception:
        pass
    if app.preview_gallery is None:
        messagebox.showinfo(_tr("滤镜批量导出"), _tr("当前没有可用的预览画廊。"))
        return
    try:
        src_paths = list(getattr(app.preview_gallery, "_paths", []) or [])
    except Exception:
        src_paths = []
    src_paths = [p for p in src_paths if os.path.isfile(p)]
    if not src_paths:
        messagebox.showinfo(
            _tr("滤镜批量导出"),
            _tr("请先成功生成一组效果图预览，再执行该操作。"),
        )
        return

    out_dir = app.var_out_dir.get().strip() or DEFAULT_OUTPUT_DIR
    fs = (app.var_filter_style.get() or "none").strip().lower()
    fmt, jq, wq, wl, emb = app._gui_export_snapshot()
    ext = ".jpg" if fmt == "jpeg" else f".{fmt}"
    filter_strength_snap = max(
        0, min(100, int(round(float(app.var_filter_strength.get()))))
    )

    app.btn_effect_preview.config(state=tk.DISABLED)
    app.btn_effect_preview_again.config(state=tk.DISABLED)
    app.btn_export_filtered_preview.config(state=tk.DISABLED)
    app.btn_go.config(state=tk.DISABLED)
    app.lbl_status.config(
        text=(
            _tr("⏳ 正在导出滤镜版预览（{n} 张）…", n=len(src_paths))
            if fs not in ("none", "off", "")
            else _tr("⏳ 正在导出现有预览（{n} 张）…", n=len(src_paths))
        )
    )

    def work() -> None:
        cancel_ev = threading.Event()
        app.after(0, lambda: app._task_bind_cancel(cancel_ev))
        generated: List[str] = []
        err = ""
        cancelled = False
        total = len(src_paths)
        try:
            os.makedirs(out_dir, exist_ok=True)

            def phase_ui() -> None:
                app.lbl_task_phase.config(
                    text=_tr("阶段 1/1：预览后处理导出 · 第 0/{total} 张", total=total)
                )
                app._progress.configure(maximum=max(1, total), value=0)

            app.after(0, phase_ui)

            for i, p in enumerate(src_paths, start=1):
                if cancel_ev.is_set():
                    cancelled = True
                    break
                with Image.open(p) as im0:
                    im = im0.convert("RGB")
                if fs not in ("none", "off", ""):
                    seed = int(zlib.crc32(os.path.abspath(p).encode("utf-8")) & 0x7FFFFFFF)
                    im = apply_post_filter(
                        im, fs, seed=seed, strength=filter_strength_snap
                    )

                ts_ms = int(time.time() * 1000)
                out_name = f"Wallpaper_Filtered_{ts_ms}_{i:02d}{ext}"
                save_path = os.path.join(out_dir, out_name)
                if fmt == "png":
                    kw: Dict[str, Any] = {"format": "PNG", "compress_level": 6}
                    if emb:
                        try:
                            from PIL import ImageCms

                            prof = ImageCms.createProfile("sRGB")
                            kw["icc_profile"] = ImageCms.ImageCmsProfile(prof).tobytes()
                        except Exception:
                            pass
                    im.save(save_path, **kw)
                elif fmt == "jpeg":
                    im.save(
                        save_path,
                        format="JPEG",
                        quality=max(1, min(95, int(jq))),
                        optimize=True,
                        subsampling=0,
                    )
                else:
                    kw2: Dict[str, Any] = {"format": "WEBP", "method": 6}
                    if wl:
                        kw2["lossless"] = True
                    else:
                        kw2["quality"] = max(1, min(100, int(wq)))
                    im.save(save_path, **kw2)
                generated.append(save_path)

                def _progress_ui(n: int = i, t: int = total, path: str = save_path) -> None:
                    app._progress.configure(value=n)
                    app.lbl_task_phase.config(
                        text=_tr("阶段 1/1：预览后处理导出 · 第 {n}/{t} 张", n=n, t=t)
                    )
                    app.lbl_status.config(
                        text=_tr("⏳ 已导出 {n}/{t} 张：{name}", n=n, t=t, name=os.path.basename(path))
                    )

                app.after(0, _progress_ui)
        except Exception as e:
            err = str(e)

        def done() -> None:
            app._task_reset_after_job()
            app.btn_go.config(state=tk.NORMAL)
            app.btn_effect_preview.config(state=tk.NORMAL)
            app.btn_export_filtered_preview.config(state=tk.NORMAL)
            if app._effect_preview_ready:
                app.btn_effect_preview_again.config(state=tk.NORMAL)
            if err:
                app.lbl_status.config(text=_tr("❌ 预览后处理导出失败"))
                messagebox.showerror(_tr("滤镜批量导出"), err)
            elif cancelled:
                app.lbl_status.config(
                    text=_tr("⏹ 已取消，已导出 {n}/{t} 张", n=len(generated), t=total)
                )
            else:
                app.lbl_status.config(
                    text=_tr("✅ 已导出 {n} 张滤镜版预览", n=len(generated))
                )
                if generated:
                    app._update_preview(generated[-1])

        app.after(0, done)

    threading.Thread(target=work, daemon=True).start()


# ---------------------------------------------------------------------------
# 正式导出壁纸
# ---------------------------------------------------------------------------


def on_generate(app: Any) -> None:  # noqa: C901
    """正式批量导出壁纸（全分辨率）。"""
    _tr = app._tr
    if app.var_follow_preview_seed.get() and app._last_preview_seed is None:
        messagebox.showwarning(
            _tr("沿用预览种子"),
            _tr("请先在下方成功执行一次「生成效果图预览」，再勾选此项；否则没有可用的预览种子。"),
        )
        return
    app.btn_effect_preview.config(state=tk.DISABLED)
    app.btn_effect_preview_again.config(state=tk.DISABLED)
    app.btn_go.config(state=tk.DISABLED, text=_tr("生成中..."))
    app.lbl_status.config(text=_tr("⏳ 正在正式导出..."))
    try:
        app._ensure_preview_gallery()
        app.preview_gallery.clear()
    except Exception:
        pass

    count = max(1, _parse_gui_int(app.var_count.get(), DEFAULT_RANDOM_COUNT))
    w = max(1, _parse_gui_int(app.var_width.get(), DEFAULT_WALLPAPER_WIDTH))
    h = max(1, _parse_gui_int(app.var_height.get(), DEFAULT_WALLPAPER_HEIGHT))
    out_dir = app.var_out_dir.get()
    custom_text = app.var_text.get()
    layout = app._layout_by_label[app.var_layout_label.get()]
    bg_base_style_snap = app.var_bg_base_style.get()
    bg_overlay_style_snap = app.var_bg_overlay_style.get()
    bg_overlay_strength_snap = max(
        0, min(100, int(round(float(app.var_bg_overlay_strength.get()))))
    )
    filter_style_snap = app.var_filter_style.get()
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
    batch_count = max(1, _parse_gui_int(app.var_batch_count.get(), 3))
    follow_seed = app.var_follow_preview_seed.get()
    base_preview_seed = app._last_preview_seed if follow_seed else None
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
    show_stamp_snap = app.var_show_stamp.get()
    stamp_place_snap = app.var_stamp_place.get()
    exp_fmt, exp_jq, exp_wq, exp_wl, exp_emb = app._gui_export_snapshot()
    gen_manual_seed_str = app.var_seed.get().strip()
    gen_manual_seed: Optional[int] = None
    if gen_manual_seed_str:
        try:
            gen_manual_seed = int(gen_manual_seed_str)
        except ValueError:
            pass
    if gen_manual_seed is not None and base_preview_seed is None:
        base_preview_seed = gen_manual_seed

    def work() -> None:
        cancel_ev = threading.Event()
        app.after(0, lambda: app._task_bind_cancel(cancel_ev))

        generated: List[str] = []
        err_msg = ""
        user_cancelled = False
        total = max(0, int(batch_count))
        image_paths: List[str] = []
        pool_skip_stats = ImageSourceSkipStats()

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
                pf_counts2: List[Tuple[str, int]] = []
                pf_paths2: List[Tuple[str, List[str]]] = []
                raw_paths = get_image_paths_from_folders(
                    folders_snap,
                    recursive=recursive_snap,
                    per_folder_counts=pf_counts2,
                    per_folder_paths=pf_paths2,
                )
                if cancel_ev.is_set():
                    user_cancelled = True
                else:
                    image_paths, pre_drop = filter_readable_image_paths(raw_paths)
                    pool_skip_stats.pre_filter_skipped += pre_drop
                good_set2 = set(image_paths)
                group_paths_good2: List[Tuple[str, List[str]]] = []
                for folder_abs, plist in pf_paths2:
                    keep = [p for p in plist if p in good_set2]
                    group_paths_good2.append((folder_abs, keep))

                pool_detail2 = "　|　".join(
                    f"{name}: {cnt}" for name, cnt in pf_counts2
                ) if pf_counts2 else ""

                def _pool_ui2(
                    d: str = pool_detail2,
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

                app.after(0, _pool_ui2)

            if cancel_ev.is_set():
                user_cancelled = True
            elif not image_paths:
                err_msg = _tr("未找到任何图片，请检查图源文件夹与「递归子目录」设置。")
                if pool_skip_stats.pre_filter_skipped:
                    err_msg += (
                        _tr("（扫描到 {n} 个路径但均不可读或过大）", n=pool_skip_stats.pre_filter_skipped)
                    )
            else:

                def phase2_ui() -> None:
                    app.lbl_task_phase.config(
                        text=(
                            _tr("阶段 2/2：正式导出壁纸 · 第 0/{total} 张（{w}×{h}）", total=total, w=w, h=h)
                        ),
                    )
                    app._progress.configure(maximum=max(1, total), value=0)

                app.after(0, phase2_ui)

                for i in range(batch_count):
                    if cancel_ev.is_set():
                        user_cancelled = True
                        break
                    seed_kw: Optional[int] = None
                    if base_preview_seed is not None:
                        seed_kw = (int(base_preview_seed) + i) % (2**30)
                    if seed_kw is not None:
                        rng_snap = random.getstate()
                        try:
                            picked = pick_paths_by_strategy(
                                image_paths,
                                count,
                                strategy=sampling_strategy_snap,
                                per_folder_paths=group_paths_good2,
                                folder_weight_by_path=weight_snap,
                                seed=seed_kw,
                            )
                            if not picked:
                                raise ValueError(_tr("按当前抽样策略未选到可用图源。"))
                            path = create_wallpaper(
                                picked,
                                len(picked),
                                w,
                                h,
                                out_dir,
                                custom_text=custom_text,
                                layout=layout,
                                bg_base_style=bg_base_style_snap,
                                bg_overlay_style=bg_overlay_style_snap,
                                bg_overlay_strength=bg_overlay_strength_snap,
                                bg_style=app._bg_parts_to_legacy_style(
                                    bg_base_style_snap, bg_overlay_style_snap
                                ),
                                filter_style=filter_style_snap,
                                filter_strength=filter_strength_snap,
                                custom_bg_gradient=custom_bg_snap,
                                text_size=max(
                                    1,
                                    _parse_gui_int(
                                        app.var_text_size.get(),
                                        DEFAULT_TEXT_SIZE,
                                    ),
                                ),
                                stamp_size=max(
                                    1,
                                    _parse_gui_int(
                                        app.var_stamp_size.get(),
                                        DEFAULT_STAMP_SIZE,
                                    ),
                                ),
                                text_pos=app.var_text_pos.get(),
                                text_color=app.text_colors[
                                    app.var_text_color.get()
                                ],
                                stroke_color=app.text_colors[
                                    app.var_stroke_color.get()
                                ],
                                seed=seed_kw,
                                show_stamp=show_stamp_snap,
                                stamp_place=stamp_place_snap,
                                export_format=exp_fmt,
                                jpeg_quality=exp_jq,
                                webp_quality=exp_wq,
                                webp_lossless=exp_wl,
                                embed_srgb_icc=exp_emb,
                                style_intensity=style_intensity_snap,
                                enable_aesthetic_rules=enable_aesthetic_rules_snap,
                                skip_stats=pool_skip_stats,
                                skip_path_validation=True,
                                **scatter_snap,
                            )
                        finally:
                            random.setstate(rng_snap)
                    else:
                        picked = pick_paths_by_strategy(
                            image_paths,
                            count,
                            strategy=sampling_strategy_snap,
                            per_folder_paths=group_paths_good2,
                            folder_weight_by_path=weight_snap,
                            seed=None,
                        )
                        if not picked:
                            raise ValueError(_tr("按当前抽样策略未选到可用图源。"))
                        path = create_wallpaper(
                            picked,
                            len(picked),
                            w,
                            h,
                            out_dir,
                            custom_text=custom_text,
                            layout=layout,
                            bg_base_style=bg_base_style_snap,
                            bg_overlay_style=bg_overlay_style_snap,
                            bg_overlay_strength=bg_overlay_strength_snap,
                            bg_style=app._bg_parts_to_legacy_style(
                                bg_base_style_snap, bg_overlay_style_snap
                            ),
                            filter_style=filter_style_snap,
                            filter_strength=filter_strength_snap,
                            custom_bg_gradient=custom_bg_snap,
                            text_size=max(
                                1,
                                _parse_gui_int(
                                    app.var_text_size.get(),
                                    DEFAULT_TEXT_SIZE,
                                ),
                            ),
                            stamp_size=max(
                                1,
                                _parse_gui_int(
                                    app.var_stamp_size.get(),
                                    DEFAULT_STAMP_SIZE,
                                ),
                            ),
                            text_pos=app.var_text_pos.get(),
                            text_color=app.text_colors[
                                app.var_text_color.get()
                            ],
                            stroke_color=app.text_colors[
                                app.var_stroke_color.get()
                            ],
                            show_stamp=show_stamp_snap,
                            stamp_place=stamp_place_snap,
                            export_format=exp_fmt,
                            jpeg_quality=exp_jq,
                            webp_quality=exp_wq,
                            webp_lossless=exp_wl,
                            embed_srgb_icc=exp_emb,
                            style_intensity=style_intensity_snap,
                            enable_aesthetic_rules=enable_aesthetic_rules_snap,
                            skip_stats=pool_skip_stats,
                            skip_path_validation=True,
                            **scatter_snap,
                        )
                    generated.append(path)
                    done_n = len(generated)

                    def on_piece_ready(
                        p: str = path,
                        n: int = done_n,
                        t: int = total,
                        fw: int = w,
                        fh: int = h,
                        sk: str = pool_skip_stats.summary(app.var_ui_language.get()),
                    ) -> None:
                        app._update_preview(p)
                        app._progress.configure(value=n)
                        app.lbl_task_phase.config(
                            text=(
                                _tr("阶段 2/2：正式导出 · 第 {n}/{t} 张（{w}×{h}）", n=n, t=t, w=fw, h=fh)
                            ),
                        )
                        app.lbl_status.config(
                            text=(
                                _tr("⏳ 正式导出 {n}/{t} · {w}×{h} · 阶段 2/2{sk}", n=n, t=t, w=fw, h=fh, sk=sk)
                            ),
                        )

                    app.after(0, on_piece_ready)
        except Exception as e:
            err_msg = str(e)

        def finalize_ui() -> None:
            app._task_reset_after_job()
            app.btn_go.config(state=tk.NORMAL, text=_tr("🚀 正式生成壁纸"))
            app.btn_effect_preview.config(state=tk.NORMAL)
            if app._effect_preview_ready:
                app.btn_effect_preview_again.config(state=tk.NORMAL)
            if err_msg:
                app.lbl_status.config(text=_tr("❌ 生成失败"))
                messagebox.showerror(_tr("生成壁纸"), err_msg)
            elif user_cancelled:
                app.lbl_status.config(
                    text=_tr("⏹ 已取消导出，已保存 {n}/{t} 张", n=len(generated), t=total),
                )
                messagebox.showinfo(
                    _tr("导出已取消"),
                    (
                        _tr("已停止批量导出。\n已成功写入磁盘 {n} 张，其余未生成。", n=len(generated))
                    ),
                )
            else:
                app.lbl_status.config(
                    text=_tr("✅ 全部 {n} 张壁纸完成！", n=len(generated)),
                )

        app.after(0, finalize_ui)

    threading.Thread(target=work, daemon=True).start()
