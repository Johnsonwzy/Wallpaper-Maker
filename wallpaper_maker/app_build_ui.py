"""UI 构建 —— 从 app.py 抽取的 _build_ui 方法体。

公开函数 ``build_ui(app)`` 的参数为 WallPaperApp 实例，
app.py 中 ``_build_ui`` 只需转调即可。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Optional

from wallpaper_maker.config import (
    APP_AUTHOR,
    APP_COPYRIGHT_YEAR,
    APP_NAME,
    APP_VERSION,
    BUILTIN_STYLE_PRESET_PLACEHOLDER,
    DEFAULT_BG_BASE_STYLE,
    DEFAULT_BG_OVERLAY_STYLE,
    DEFAULT_SAMPLING_STRATEGY,
    DEFAULT_STYLE_INTENSITY,
    PREVIEW_BATCH_CAP_DECOUPLED,
    UI_FONT_PT_MAIN,
    UI_FONT_PT_MICRO,
    UI_FONT_PT_SMALL,
    UI_FONT_PT_TITLE,
    UI_FONT_PT_ZH_CAPTION,
)
from wallpaper_maker.presets import BUILTIN_STYLE_PRESETS


def build_ui(app: Any) -> None:  # noqa: C901
    """构建完整的主界面 UI —— 对应原 WallPaperApp._build_ui。"""
    root_wrap = tk.Frame(app, bg="#FFFFFF")
    app._root_wrap = root_wrap
    root_wrap.pack(fill=tk.BOTH, expand=True)
    app._main_scroll_canvas = tk.Canvas(
        root_wrap,
        bg="#FFFFFF",
        highlightthickness=0,
        bd=0,
    )
    app._main_scroll_vsb = tk.Scrollbar(
        root_wrap, orient=tk.VERTICAL, command=app._main_scroll_canvas.yview
    )
    app._main_scroll_canvas.configure(yscrollcommand=app._main_scroll_vsb.set)
    app._main_scroll_vsb.pack(side=tk.RIGHT, fill=tk.Y)
    app._main_scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    main = tk.Frame(app._main_scroll_canvas, bg="white")
    app._main_scroll_inner = main
    app._main_scroll_win = app._main_scroll_canvas.create_window(
        14, 10, window=main, anchor="nw"
    )
    main.bind("<Configure>", app._on_main_inner_configure)
    app._main_scroll_canvas.bind("<Configure>", app._on_main_canvas_configure)
    app._main_scroll_canvas.bind("<MouseWheel>", app._on_main_mousewheel)
    app._main_scroll_canvas.bind("<Button-4>", app._on_main_mousewheel_linux)
    app._main_scroll_canvas.bind("<Button-5>", app._on_main_mousewheel_linux)

    _f = ("SF Pro Text", UI_FONT_PT_MAIN)
    _f_sm = ("SF Pro Text", UI_FONT_PT_SMALL)
    _bg_e = "#F5F5F7"
    _tr = app._tr

    sty_ttk = ttk.Style()
    try:
        sty_ttk.configure("TCombobox", font=_f)
    except tk.TclError:
        pass

    # 文字颜色（色名 → RGB，供渲染使用）
    app.text_colors = {
        "白色": (255, 255, 255),
        "黑色": (0, 0, 0),
        "红色": (255, 0, 0),
        "黄色": (255, 255, 0),
        "蓝色": (0, 100, 255),
    }
    app.var_text_color = tk.StringVar(value="白色")
    app.var_stroke_color = tk.StringVar(value="黑色")

    tk.Label(
        main,
        text="Wallpaper Maker",
        font=("SF Pro Display", UI_FONT_PT_TITLE, "bold"),
        bg="white",
        fg="#222222",
    ).pack(anchor=tk.W, pady=(0, 8))

    preset_bar = tk.Frame(main, bg="white")
    preset_bar.pack(fill=tk.X, pady=(0, 8))
    preset_row_top = tk.Frame(preset_bar, bg="white")
    preset_row_top.pack(fill=tk.X)
    preset_row_bottom = tk.Frame(preset_bar, bg="white")
    preset_row_bottom.pack(fill=tk.X, pady=(6, 0))

    tk.Label(
        preset_row_top,
        text=_tr("内置风格"),
        bg="white",
        font=_f,
        fg="#333333",
    ).pack(side=tk.LEFT, padx=(0, 8))
    _style_combo_vals = [BUILTIN_STYLE_PRESET_PLACEHOLDER] + [
        n for n, _ in BUILTIN_STYLE_PRESETS
    ]
    _style_combo_vals = [_tr(x) for x in _style_combo_vals]
    app._combo_builtin_style = ttk.Combobox(
        preset_row_top,
        values=_style_combo_vals,
        state="readonly",
        width=26,
    )
    app._combo_builtin_style.set(_tr(BUILTIN_STYLE_PRESET_PLACEHOLDER))
    app._combo_builtin_style.pack(side=tk.LEFT, padx=(0, 8))
    app.btn_apply_builtin_style = tk.Button(
        preset_row_top,
        text=_tr("应用此风格"),
        command=app._on_apply_builtin_style,
        bg="white",
        fg="#000",
        relief=tk.FLAT,
        bd=0,
        font=_f,
    )
    app.btn_apply_builtin_style.pack(side=tk.LEFT, padx=(0, 10))

    left_ops = tk.Frame(preset_row_bottom, bg="white")
    left_ops.pack(side=tk.LEFT)
    app.btn_export_preset = tk.Button(
        left_ops,
        text=_tr("导出 JSON…"),
        command=app._on_export_preset_json,
        bg="white",
        fg="#000",
        relief=tk.FLAT,
        bd=0,
        font=_f,
    )
    app.btn_export_preset.pack(side=tk.LEFT, padx=(0, 8))
    app.btn_import_preset = tk.Button(
        left_ops,
        text=_tr("导入 JSON…"),
        command=app._on_import_preset_json,
        bg="white",
        fg="#000",
        relief=tk.FLAT,
        bd=0,
        font=_f,
    )
    app.btn_import_preset.pack(side=tk.LEFT, padx=(0, 8))
    app.btn_restore_defaults = tk.Button(
        left_ops,
        text=_tr("恢复默认选项"),
        command=app._on_restore_default_options,
        bg="#F5F5F7",
        fg="#000",
        relief=tk.FLAT,
        bd=0,
        font=_f,
        padx=10,
        pady=2,
    )
    app.btn_restore_defaults.pack(side=tk.LEFT, padx=(0, 0))

    right_ops = tk.Frame(preset_row_bottom, bg="white")
    right_ops.pack(side=tk.RIGHT)
    tk.Label(
        right_ops,
        text=_tr("主题"),
        bg="white",
        font=_f_sm,
        fg="#555555",
    ).pack(side=tk.LEFT, padx=(14, 6))
    app._combo_ui_theme = ttk.Combobox(
        right_ops,
        values=[_tr(x) for x in app._theme_mode_key_by_zh.keys()],
        state="readonly",
        width=8,
    )
    app._combo_ui_theme.set(
        _tr(app._theme_mode_zh_by_key.get(app.var_ui_theme_mode.get(), "跟随系统"))
    )
    app._combo_ui_theme.pack(side=tk.LEFT)

    tk.Label(
        right_ops,
        text=_tr("语言"),
        bg="white",
        font=_f_sm,
        fg="#555555",
    ).pack(side=tk.LEFT, padx=(10, 6))
    app._combo_ui_lang = ttk.Combobox(
        right_ops,
        values=list(app._lang_display_by_code.values()),
        state="readonly",
        width=8,
    )
    app._combo_ui_lang.set(
        app._lang_display_by_code.get(app.var_ui_language.get(), "中文")
    )
    app._combo_ui_lang.pack(side=tk.LEFT)

    def _on_ui_theme_change(_e: Optional[tk.Event] = None) -> None:
        z = app._to_zh(app._combo_ui_theme.get())
        app.var_ui_theme_mode.set(app._theme_mode_key_by_zh.get(z, "system"))
        app._apply_theme()

    app._combo_ui_theme.bind("<<ComboboxSelected>>", _on_ui_theme_change)

    def _on_ui_lang_change(_e: Optional[tk.Event] = None) -> None:
        display = app._combo_ui_lang.get()
        lang = app._lang_code_by_display.get(display, "zh")
        if lang == app.var_ui_language.get():
            return
        app.var_ui_language.set(lang)
        app._rebuild_ui_for_language()

    app._combo_ui_lang.bind("<<ComboboxSelected>>", _on_ui_lang_change)

    form = tk.LabelFrame(
        main,
        text="  ",
        font=("SF Pro Text", UI_FONT_PT_SMALL),
        fg="#666666",
        bg="white",
        bd=0,
        relief=tk.FLAT,
        labelanchor="nw",
        padx=10,
        pady=8,
        highlightthickness=0,
    )
    app._form_panel = form
    form.pack(fill=tk.X)
    form.columnconfigure(1, weight=1)
    form.columnconfigure(3, weight=0)

    def _section_title(row_idx: int, text: str) -> int:
        tk.Label(
            form,
            text=text,
            bg="white",
            fg="#555555",
            font=("SF Pro Text", UI_FONT_PT_SMALL, "bold"),
        ).grid(row=row_idx, column=0, columnspan=4, sticky=tk.W, pady=(8, 4))
        return row_idx + 1

    def _e_bg(**kwargs):
        return dict(
            font=_f,
            bg=_bg_e,
            fg="#000",
            relief=tk.FLAT,
            bd=0,
            insertbackground="#000",
            highlightthickness=0,
            **kwargs,
        )

    pos_by_zh = dict(zip(app.pos_labels, app.text_positions))
    zh_by_pos = {v: k for k, v in pos_by_zh.items()}
    layout_names = [_tr(b) for a, b in app._layout_choices]

    r = 0
    tk.Label(form, text=_tr("图源"), bg="white", font=_f, fg="#333333").grid(
        row=r, column=0, sticky=tk.NE, padx=(0, 8), pady=2
    )
    src_wrap = tk.Frame(form, bg="white")
    src_wrap.grid(row=r, column=1, columnspan=2, sticky=tk.EW, pady=2)
    lb_row = tk.Frame(src_wrap, bg="white")
    lb_row.pack(fill=tk.BOTH, expand=True)
    src_scroll = tk.Scrollbar(lb_row)
    app._list_source_folders = tk.Listbox(
        lb_row,
        height=3,
        font=_f,
        bg=_bg_e,
        fg="#000",
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        selectmode=tk.EXTENDED,
        yscrollcommand=src_scroll.set,
        activestyle="dotbox",
    )
    src_scroll.config(command=app._list_source_folders.yview)
    src_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    app._list_source_folders.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tk.Label(
        src_wrap,
        text=_tr("多个文件夹合并为图片池，生成时从中随机抽图"),
        bg="white",
        fg="#888888",
        font=_f_sm,
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=(4, 0))
    src_sampling_row = tk.Frame(src_wrap, bg="white")
    src_sampling_row.pack(fill=tk.X, pady=(4, 0))
    tk.Label(
        src_sampling_row,
        text=_tr("抽样策略"),
        bg="white",
        fg="#555555",
        font=_f_sm,
    ).pack(side=tk.LEFT, padx=(0, 6))
    app._combo_sampling_strategy = ttk.Combobox(
        src_sampling_row,
        values=[_tr(x) for x in app._sampling_mode_key_by_zh.keys()],
        state="readonly",
        width=24,
    )
    app._combo_sampling_strategy.set(
        _tr(
            app._sampling_mode_zh_by_key.get(
                app.var_sampling_strategy.get(),
                "按图片数量自然比例",
            )
        )
    )
    app._combo_sampling_strategy.pack(side=tk.LEFT)

    def _on_sampling_strategy(_e: Optional[tk.Event] = None) -> None:
        z = app._to_zh(app._combo_sampling_strategy.get())
        app.var_sampling_strategy.set(
            app._sampling_mode_key_by_zh.get(z, DEFAULT_SAMPLING_STRATEGY)
        )

    app._combo_sampling_strategy.bind("<<ComboboxSelected>>", _on_sampling_strategy)
    src_btns = tk.Frame(form, bg="white")
    src_btns.grid(row=r, column=3, padx=(8, 0), pady=2, sticky=tk.NE)
    app.btn_add_source = tk.Button(
        src_btns,
        text=_tr("增加图源"),
        command=app._add_source_folder,
        bg="white",
        fg="#000",
        relief=tk.FLAT,
        bd=0,
        font=_f,
    )
    app.btn_add_source.pack(fill=tk.X, pady=(0, 6))
    app.btn_remove_source = tk.Button(
        src_btns,
        text=_tr("移除所选"),
        command=app._remove_selected_sources,
        bg="white",
        fg="#000",
        relief=tk.FLAT,
        bd=0,
        font=_f,
    )
    app.btn_remove_source.pack(fill=tk.X)
    app.btn_set_weight = tk.Button(
        src_btns,
        text=_tr("设置权重"),
        command=app._set_selected_source_weight,
        bg="white",
        fg="#000",
        relief=tk.FLAT,
        bd=0,
        font=_f_sm,
    )
    app.btn_set_weight.pack(fill=tk.X, pady=(6, 0))
    app.btn_reset_weight = tk.Button(
        src_btns,
        text=_tr("重置权重"),
        command=app._reset_source_weights,
        bg="white",
        fg="#666666",
        relief=tk.FLAT,
        bd=0,
        font=_f_sm,
    )
    app.btn_reset_weight.pack(fill=tk.X, pady=(2, 0))
    app._sync_source_listbox()

    r += 1
    tk.Label(form, text=_tr("输出"), bg="white", font=_f, fg="#333333").grid(
        row=r, column=0, sticky=tk.E, padx=(0, 8), pady=2
    )
    tk.Entry(form, textvariable=app.var_out_dir, **_e_bg()).grid(
        row=r, column=1, columnspan=2, sticky=tk.EW, pady=2
    )
    app.btn_browse_out = tk.Button(
        form,
        text=_tr("浏览…"),
        command=app._browse_out_dir,
        bg="white",
        fg="#000",
        relief=tk.FLAT,
        bd=0,
        font=_f,
    )
    app.btn_browse_out.grid(row=r, column=3, padx=(8, 0), pady=2)

    r += 1
    tk.Label(form, text=_tr("导出"), bg="white", font=_f, fg="#333333").grid(
        row=r, column=0, sticky=tk.NE, padx=(0, 8), pady=2
    )
    ex = tk.Frame(form, bg="white")
    ex.grid(row=r, column=1, columnspan=3, sticky=tk.W, pady=2)
    app._combo_export_fmt = ttk.Combobox(
        ex,
        values=[_tr(x) for x in app._export_fmt_by_label.keys()],
        state="readonly",
        width=11,
    )
    app._combo_export_fmt.set(_tr("PNG（无损）"))
    app._combo_export_fmt.pack(side=tk.LEFT)
    app._combo_export_fmt.bind(
        "<<ComboboxSelected>>", app._sync_export_controls_state
    )
    tk.Label(ex, text=_tr("JPEG质"), bg="white", font=_f_sm, fg="#555555").pack(
        side=tk.LEFT, padx=(10, 0)
    )
    app._ent_jpeg_q = tk.Entry(ex, textvariable=app.var_jpeg_quality, width=4, **_e_bg())
    app._ent_jpeg_q.pack(side=tk.LEFT, padx=(4, 0))
    tk.Label(ex, text=_tr("WebP质"), bg="white", font=_f_sm, fg="#555555").pack(
        side=tk.LEFT, padx=(8, 0)
    )
    app._ent_webp_q = tk.Entry(ex, textvariable=app.var_webp_quality, width=4, **_e_bg())
    app._ent_webp_q.pack(side=tk.LEFT, padx=(4, 0))
    app._chk_webp_lossless = tk.Checkbutton(
        ex,
        text=_tr("WebP无损"),
        variable=app.var_webp_lossless,
        bg="white",
        fg="#333333",
        font=_f_sm,
        selectcolor="white",
        activebackground="white",
        command=app._sync_export_controls_state,
    )
    app._chk_webp_lossless.pack(side=tk.LEFT, padx=(8, 0))
    app._chk_embed_icc = tk.Checkbutton(
        ex,
        text=_tr("嵌入sRGB ICC"),
        variable=app.var_embed_srgb_icc,
        bg="white",
        fg="#333333",
        font=_f_sm,
        selectcolor="white",
        activebackground="white",
    )
    app._chk_embed_icc.pack(side=tk.LEFT, padx=(8, 0))

    r += 1
    tk.Label(form, text="", bg="white").grid(row=r, column=0, pady=0)
    ex_note = tk.Frame(form, bg="white")
    ex_note.grid(row=r, column=1, columnspan=3, sticky=tk.W, pady=(0, 4))
    tk.Label(
        ex_note,
        text=_tr("全流程按 sRGB 合成；勾选 ICC 则写入标准 sRGB 特征文件，异屏/印刷更易一致。效果图预览固定 PNG、不占 ICC。"),
        bg="white",
        font=("PingFang SC", UI_FONT_PT_ZH_CAPTION),
        fg="#888888",
        justify=tk.LEFT,
        wraplength=880,
    ).pack(anchor=tk.W)

    r += 1
    r = _section_title(r, _tr("文案与尺寸"))
    tk.Label(form, text=_tr("格言"), bg="white", font=_f, fg="#333333").grid(
        row=r, column=0, sticky=tk.NE, padx=(0, 8), pady=2
    )
    tk.Entry(form, textvariable=app.var_text, **_e_bg()).grid(
        row=r, column=1, columnspan=3, sticky=tk.EW, pady=2
    )

    r += 1
    tk.Label(form, text=_tr("外观"), bg="white", font=_f, fg="#333333").grid(
        row=r, column=0, sticky=tk.NE, padx=(0, 8), pady=2
    )
    sty_row = tk.Frame(form, bg="white")
    sty_row.grid(row=r, column=1, columnspan=3, sticky=tk.W, pady=2)
    tk.Label(sty_row, text=_tr("字号"), bg="white", font=_f_sm, fg="#555555").pack(
        side=tk.LEFT
    )
    tk.Entry(
        sty_row, textvariable=app.var_text_size, width=4, **_e_bg()
    ).pack(side=tk.LEFT, padx=(4, 14))
    tk.Label(sty_row, text=_tr("位置"), bg="white", font=_f_sm, fg="#555555").pack(
        side=tk.LEFT
    )
    app._combo_text_pos = ttk.Combobox(
        sty_row,
        values=[_tr(x) for x in app.pos_labels],
        state="readonly",
        width=6,
    )
    app._combo_text_pos.set(_tr(zh_by_pos.get(app.var_text_pos.get(), "右下")))
    app._combo_text_pos.pack(side=tk.LEFT, padx=(4, 14))

    def _on_text_pos(_e: Optional[tk.Event] = None) -> None:
        z = app._to_zh(app._combo_text_pos.get())
        if z in pos_by_zh:
            app.var_text_pos.set(pos_by_zh[z])

    app._combo_text_pos.bind("<<ComboboxSelected>>", _on_text_pos)

    tk.Label(sty_row, text=_tr("字色"), bg="white", font=_f_sm, fg="#555555").pack(
        side=tk.LEFT
    )
    app._combo_text_color = ttk.Combobox(
        sty_row,
        values=[_tr(x) for x in app.text_colors.keys()],
        state="readonly",
        width=5,
    )
    app._combo_text_color.set(_tr(app.var_text_color.get()))
    app._combo_text_color.pack(side=tk.LEFT, padx=(4, 14))
    app._combo_text_color.bind(
        "<<ComboboxSelected>>",
        lambda _e: app.var_text_color.set(app._to_zh(app._combo_text_color.get())),
    )

    tk.Label(sty_row, text=_tr("描边"), bg="white", font=_f_sm, fg="#555555").pack(
        side=tk.LEFT
    )
    app._combo_stroke = ttk.Combobox(
        sty_row,
        values=[_tr(x) for x in app.text_colors.keys()],
        state="readonly",
        width=5,
    )
    app._combo_stroke.set(_tr(app.var_stroke_color.get()))
    app._combo_stroke.pack(side=tk.LEFT, padx=(4, 0))
    app._combo_stroke.bind(
        "<<ComboboxSelected>>",
        lambda _e: app.var_stroke_color.set(app._to_zh(app._combo_stroke.get())),
    )

    r += 1
    tk.Label(form, text=_tr("数值"), bg="white", font=_f, fg="#333333").grid(
        row=r, column=0, sticky=tk.NE, padx=(0, 8), pady=4
    )
    nums = tk.Frame(form, bg="white")
    nums.grid(row=r, column=1, columnspan=3, sticky=tk.W, pady=4)
    num_pairs = [
        (_tr("随机张"), app.var_count),
        (_tr("宽"), app.var_width),
        (_tr("高"), app.var_height),
        (_tr("正式数"), app.var_batch_count),
        (_tr("边距"), app.var_margin),
        (_tr("间距"), app.var_gap),
        (_tr("旋转°"), app.var_rot),
        (_tr("种子"), app.var_seed),
    ]
    for i, (lab, var) in enumerate(num_pairs):
        cell = tk.Frame(nums, bg="white")
        cell.grid(row=i // 4, column=i % 4, padx=(0, 14), pady=2, sticky=tk.W)
        tk.Label(cell, text=lab, bg="white", font=_f_sm, fg="#555555").pack(
            side=tk.LEFT
        )
        tk.Entry(cell, textvariable=var, width=6, **_e_bg()).pack(
            side=tk.LEFT, padx=(4, 0)
        )

    app._lbl_perf_hint = tk.Label(
        nums, text="", bg="white", font=_f_sm, fg="#999999", anchor=tk.W,
    )
    app._lbl_perf_hint.grid(
        row=2, column=0, columnspan=4, sticky=tk.W, pady=(4, 0),
    )
    for _pv in (app.var_count, app.var_width, app.var_height, app.var_batch_count):
        _pv.trace_add("write", lambda *_a: app._refresh_perf_hint())

    r += 1
    tk.Label(form, text=_tr("水印"), bg="white", font=_f, fg="#333333").grid(
        row=r, column=0, sticky=tk.NE, padx=(0, 8), pady=2
    )
    wm = tk.Frame(form, bg="white")
    wm.grid(row=r, column=1, columnspan=3, sticky=tk.W, pady=2)
    tk.Checkbutton(
        wm,
        text=_tr("时间戳"),
        variable=app.var_show_stamp,
        bg="white",
        fg="#000",
        selectcolor=_bg_e,
        font=_f,
        relief=tk.FLAT,
    ).pack(side=tk.LEFT, padx=(0, 10))
    tk.Label(wm, text=_tr("戳字号"), bg="white", font=_f_sm, fg="#555555").pack(
        side=tk.LEFT
    )
    tk.Entry(wm, textvariable=app.var_stamp_size, width=4, **_e_bg()).pack(
        side=tk.LEFT, padx=(4, 12)
    )
    tk.Label(wm, text=_tr("戳位置"), bg="white", font=_f_sm, fg="#555555").pack(
        side=tk.LEFT
    )
    app._combo_stamp_place = ttk.Combobox(
        wm,
        values=[_tr(x) for x in app._stamp_place_key_by_zh.keys()],
        state="readonly",
        width=22,
    )
    app._combo_stamp_place.set(
        app._stamp_place_zh_by_key.get(
            app.var_stamp_place.get(), "与格言同侧，格言再上"
        )
    )
    app._combo_stamp_place.set(_tr(app._combo_stamp_place.get()))
    app._combo_stamp_place.pack(side=tk.LEFT, padx=(4, 0))

    def _on_stamp_place(_e: Optional[tk.Event] = None) -> None:
        z = app._to_zh(app._combo_stamp_place.get())
        app.var_stamp_place.set(app._stamp_place_key_by_zh.get(z, "same_above"))

    app._combo_stamp_place.bind("<<ComboboxSelected>>", _on_stamp_place)

    r += 1
    r = _section_title(r, _tr("排版与风格"))
    tk.Label(form, text=_tr("选项"), bg="white", font=_f, fg="#333333").grid(
        row=r, column=0, sticky=tk.NE, padx=(0, 8), pady=4
    )
    opt = tk.Frame(form, bg="white")
    opt.grid(row=r, column=1, columnspan=3, sticky=tk.EW, pady=4)
    opt.columnconfigure(3, weight=1)
    tk.Checkbutton(
        opt,
        text=_tr("递归子目录"),
        variable=app.var_recursive,
        bg="white",
        fg="#000",
        selectcolor=_bg_e,
        font=_f,
        relief=tk.FLAT,
    ).grid(row=0, column=0, sticky=tk.W, padx=(0, 12))
    tk.Label(opt, text=_tr("排版"), bg="white", font=_f, fg="#333333").grid(
        row=0, column=1, sticky=tk.W, padx=(0, 6)
    )
    app._combo_layout = ttk.Combobox(
        opt, values=layout_names, state="readonly", width=22
    )
    app._combo_layout.set(_tr(app.var_layout_label.get()))
    app._combo_layout.grid(row=0, column=2, columnspan=2, sticky=tk.EW)
    app._combo_layout.bind(
        "<<ComboboxSelected>>",
        lambda _e: app.var_layout_label.set(app._to_zh(app._combo_layout.get())),
    )
    tk.Label(opt, text=_tr("背景底色"), bg="white", font=_f, fg="#333333").grid(
        row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(6, 0)
    )
    app._combo_bg_base_style = ttk.Combobox(
        opt,
        values=[_tr(x) for x in app._bg_base_style_key_by_zh.keys()],
        state="readonly",
        width=20,
    )
    app._combo_bg_base_style.set(
        app._bg_base_style_zh_by_key.get(
            app.var_bg_base_style.get(), "从所选图取色渐变（推荐）"
        )
    )
    app._combo_bg_base_style.set(_tr(app._combo_bg_base_style.get()))
    app._combo_bg_base_style.grid(row=1, column=1, sticky=tk.W, pady=(6, 0))

    def _on_bg_base_style(_e: Optional[tk.Event] = None) -> None:
        z = app._to_zh(app._combo_bg_base_style.get())
        app.var_bg_base_style.set(
            app._bg_base_style_key_by_zh.get(z, DEFAULT_BG_BASE_STYLE)
        )
        app._sync_bg_custom_controls()
        app._refresh_preview_base_live()

    app._combo_bg_base_style.bind("<<ComboboxSelected>>", _on_bg_base_style)

    tk.Label(opt, text=_tr("叠层"), bg="white", font=_f_sm, fg="#555555").grid(
        row=1, column=2, sticky=tk.W, padx=(8, 6), pady=(6, 0)
    )
    app._combo_bg_overlay_style = ttk.Combobox(
        opt,
        values=[_tr(x) for x in app._bg_overlay_style_key_by_zh.keys()],
        state="readonly",
        width=12,
    )
    app._combo_bg_overlay_style.set(
        app._bg_overlay_style_zh_by_key.get(
            app.var_bg_overlay_style.get(), "无叠层"
        )
    )
    app._combo_bg_overlay_style.set(_tr(app._combo_bg_overlay_style.get()))
    app._combo_bg_overlay_style.grid(row=1, column=3, sticky=tk.W, pady=(6, 0))

    def _on_bg_overlay_style(_e: Optional[tk.Event] = None) -> None:
        z = app._to_zh(app._combo_bg_overlay_style.get())
        k = app._bg_overlay_style_key_by_zh.get(z, DEFAULT_BG_OVERLAY_STYLE)
        app.var_bg_overlay_style.set(k)
        # 切换叠层时应用建议强度，减少手动试错成本。
        rec = app._bg_overlay_recommended_strength.get(k)
        if rec is not None:
            try:
                app.var_bg_overlay_strength.set(float(rec))
            except tk.TclError:
                pass
        app._refresh_preview_filter_live()

    app._combo_bg_overlay_style.bind(
        "<<ComboboxSelected>>", _on_bg_overlay_style
    )

    tk.Label(opt, text=_tr("叠层强度"), bg="white", font=_f_sm, fg="#555555").grid(
        row=2, column=0, sticky=tk.W, padx=(0, 8), pady=(6, 0)
    )
    app._scale_bg_overlay_strength = tk.Scale(
        opt,
        from_=0,
        to=100,
        orient=tk.HORIZONTAL,
        resolution=1,
        length=220,
        showvalue=True,
        variable=app.var_bg_overlay_strength,
        bg="white",
        fg="#333333",
        highlightthickness=0,
        bd=0,
        relief=tk.FLAT,
        command=lambda _v: app._refresh_preview_filter_live(),
    )
    app._scale_bg_overlay_strength.grid(
        row=2, column=1, columnspan=3, sticky=tk.W, pady=(4, 0)
    )

    tk.Label(opt, text=_tr("滤镜"), bg="white", font=_f, fg="#333333").grid(
        row=3, column=0, sticky=tk.W, padx=(0, 8), pady=(8, 0)
    )
    app._combo_filter_style = ttk.Combobox(
        opt,
        values=[_tr(x) for x in app._filter_style_key_by_zh.keys()],
        state="readonly",
        width=30,
    )
    app._combo_filter_style.set(
        app._filter_style_zh_by_key.get(
            app.var_filter_style.get(), "无滤镜（原始质感）"
        )
    )
    app._combo_filter_style.set(_tr(app._combo_filter_style.get()))
    app._combo_filter_style.grid(
        row=3, column=1, columnspan=3, sticky=tk.W, pady=(8, 0)
    )

    def _on_filter_style(_e: Optional[tk.Event] = None) -> None:
        z = app._to_zh(app._combo_filter_style.get())
        k = app._filter_style_key_by_zh.get(z, "none")
        app.var_filter_style.set(k)
        rec = app._filter_recommended_strength.get(k)
        if rec is not None:
            try:
                app.var_filter_strength.set(float(rec))
            except tk.TclError:
                pass
        app._refresh_preview_filter_live()

    app._combo_filter_style.bind("<<ComboboxSelected>>", _on_filter_style)

    tk.Label(opt, text=_tr("滤镜强度"), bg="white", font=_f_sm, fg="#555555").grid(
        row=4, column=0, sticky=tk.W, padx=(0, 8), pady=(6, 0)
    )
    app._scale_filter_strength = tk.Scale(
        opt,
        from_=0,
        to=100,
        orient=tk.HORIZONTAL,
        resolution=1,
        length=220,
        showvalue=True,
        variable=app.var_filter_strength,
        bg="white",
        fg="#333333",
        highlightthickness=0,
        bd=0,
        relief=tk.FLAT,
        command=lambda _v: app._refresh_preview_filter_live(),
    )
    app._scale_filter_strength.grid(
        row=4, column=1, columnspan=3, sticky=tk.W, pady=(4, 0)
    )

    tk.Label(
        opt,
        text=_tr("自定双色（竖直：上→下；径向：心→边）"),
        bg="white",
        font=_f_sm,
        fg="#555555",
    ).grid(row=5, column=0, sticky=tk.W, padx=(0, 6), pady=(6, 0))
    app._combo_bg_custom_top = ttk.Combobox(
        opt,
        values=[_tr(x) for x in app.text_colors.keys()],
        state="readonly",
        width=7,
    )
    app._combo_bg_custom_top.set(_tr(app.var_bg_custom_top.get()))
    app._combo_bg_custom_top.grid(row=5, column=1, sticky=tk.W, pady=(6, 0))

    def _on_cbt(_e: Optional[tk.Event] = None) -> None:
        app.var_bg_custom_top.set(app._to_zh(app._combo_bg_custom_top.get()))
        app._refresh_preview_base_live()

    app._combo_bg_custom_top.bind("<<ComboboxSelected>>", _on_cbt)
    tk.Label(opt, text="→", bg="white", font=_f_sm, fg="#888888").grid(
        row=5, column=2, padx=6, pady=(6, 0)
    )
    app._combo_bg_custom_bottom = ttk.Combobox(
        opt,
        values=[_tr(x) for x in app.text_colors.keys()],
        state="readonly",
        width=7,
    )
    app._combo_bg_custom_bottom.set(_tr(app.var_bg_custom_bottom.get()))
    app._combo_bg_custom_bottom.grid(row=5, column=3, sticky=tk.W, pady=(6, 0))

    def _on_cbb(_e: Optional[tk.Event] = None) -> None:
        app.var_bg_custom_bottom.set(app._to_zh(app._combo_bg_custom_bottom.get()))
        app._refresh_preview_base_live()

    app._combo_bg_custom_bottom.bind("<<ComboboxSelected>>", _on_cbb)

    app._sync_bg_custom_controls()

    r += 1
    tk.Label(form, text=_tr("散落"), bg="white", font=_f, fg="#333333").grid(
        row=r, column=0, sticky=tk.NE, padx=(0, 8), pady=4
    )
    sc_row = tk.Frame(form, bg="white")
    sc_row.grid(row=r, column=1, columnspan=3, sticky=tk.W, pady=4)
    sc_pairs = [
        (_tr("溢出"), app.var_scatter_bleed, 5),
        (_tr("缩放下限"), app.var_scatter_smin, 5),
        (_tr("缩放上限"), app.var_scatter_smax, 5),
    ]
    for sc_lab, sc_var, sc_w in sc_pairs:
        tk.Label(sc_row, text=sc_lab, bg="white", font=_f_sm, fg="#555555").pack(
            side=tk.LEFT
        )
        tk.Entry(sc_row, textvariable=sc_var, width=sc_w, **_e_bg()).pack(
            side=tk.LEFT, padx=(4, 14)
        )
    tk.Checkbutton(
        sc_row,
        text=_tr("阴影"),
        variable=app.var_scatter_shadow,
        bg="white",
        fg="#000",
        selectcolor=_bg_e,
        font=_f,
        relief=tk.FLAT,
    ).pack(side=tk.LEFT, padx=(0, 8))
    tk.Checkbutton(
        sc_row,
        text=_tr("审美规则"),
        variable=app.var_enable_aesthetic_rules,
        bg="white",
        fg="#000",
        selectcolor=_bg_e,
        font=_f,
        relief=tk.FLAT,
    ).pack(side=tk.LEFT, padx=(0, 10))
    tk.Label(
        sc_row,
        text=_tr("（影响主次排序 / 留白 / 文本安全区）"),
        bg="white",
        fg="#888888",
        font=_f_sm,
    ).pack(side=tk.LEFT)
    tk.Label(
        sc_row,
        text=_tr("风格强度"),
        bg="white",
        fg="#555555",
        font=_f_sm,
    ).pack(side=tk.LEFT, padx=(12, 4))
    app._combo_style_intensity = ttk.Combobox(
        sc_row,
        values=[_tr(x) for x in app._style_intensity_key_by_zh.keys()],
        state="readonly",
        width=4,
    )
    app._combo_style_intensity.set(
        app._style_intensity_zh_by_key.get(
            app.var_style_intensity.get(), "标准"
        )
    )
    app._combo_style_intensity.set(_tr(app._combo_style_intensity.get()))
    app._combo_style_intensity.pack(side=tk.LEFT)

    def _on_style_intensity(_e: Optional[tk.Event] = None) -> None:
        z = app._to_zh(app._combo_style_intensity.get())
        app.var_style_intensity.set(
            app._style_intensity_key_by_zh.get(z, DEFAULT_STYLE_INTENSITY)
        )

    app._combo_style_intensity.bind("<<ComboboxSelected>>", _on_style_intensity)

    preview_panel = tk.LabelFrame(
        main,
        text=_tr("生成与预览"),
        font=("SF Pro Text", UI_FONT_PT_SMALL),
        fg="#666666",
        bg="white",
        bd=0,
        relief=tk.FLAT,
        labelanchor="nw",
        padx=10,
        pady=8,
        highlightthickness=0,
    )
    app._preview_panel = preview_panel
    preview_panel.pack(fill=tk.X, pady=(8, 0))

    tk.Label(
        preview_panel,
        text=(
            _tr(
                "  流程：先「生成效果图预览」；满意后可勾选「沿用预览种子」，成品在「输出」目录，可用「打开输出目录」）"
            )
        ),
        bg="white",
        fg="#777777",
        font=("SF Pro Text", UI_FONT_PT_SMALL),
        justify=tk.LEFT,
        wraplength=900,
    ).pack(anchor=tk.W, pady=(0, 8))

    row_follow = tk.Frame(preview_panel, bg="white")
    row_follow.pack(fill=tk.X, pady=(0, 10))
    tk.Checkbutton(
        row_follow,
        text=_tr("正式生成沿用当前预览种子（多张时与预览相同：基准、+1、+2 …）"),
        variable=app.var_follow_preview_seed,
        bg="white",
        fg="#000000",
        selectcolor="#F5F5F7",
        relief=tk.FLAT,
        font=("SF Pro Text", UI_FONT_PT_MAIN),
    ).pack(anchor=tk.W)

    preview_opts = tk.Frame(preview_panel, bg="white")
    preview_opts.pack(fill=tk.X, pady=(4, 4))
    tk.Label(
        preview_opts,
        text=_tr("预览设置"),
        bg="white",
        fg="#555555",
        font=("SF Pro Text", UI_FONT_PT_MAIN, "bold"),
    ).pack(anchor=tk.W)
    tk.Checkbutton(
        preview_opts,
        text=_tr("开始「生成效果图预览 / 重新生成预览」时自动打开预览画廊"),
        variable=app.var_auto_show_gallery_on_preview,
        bg="white",
        fg="#000000",
        selectcolor="#F5F5F7",
        relief=tk.FLAT,
        font=("SF Pro Text", UI_FONT_PT_MAIN),
    ).pack(anchor=tk.W, pady=(4, 0))
    tk.Checkbutton(
        preview_opts,
        text=_tr("底色切换实时预览（不重抽样，仅重渲染现有效果图）"),
        variable=app.var_live_bg_base_preview,
        bg="white",
        fg="#000000",
        selectcolor="#F5F5F7",
        relief=tk.FLAT,
        font=("SF Pro Text", UI_FONT_PT_MAIN),
    ).pack(anchor=tk.W, pady=(4, 0))
    tk.Checkbutton(
        preview_opts,
        text=_tr("对比增强模式（仅预览生效，不影响最终导出）"),
        variable=app.var_preview_compare_boost,
        command=app._refresh_preview_filter_live,
        bg="white",
        fg="#000000",
        selectcolor="#F5F5F7",
        relief=tk.FLAT,
        font=("SF Pro Text", UI_FONT_PT_MAIN),
    ).pack(anchor=tk.W, pady=(4, 0))
    row_prev_n = tk.Frame(preview_panel, bg="white")
    row_prev_n.pack(fill=tk.X, pady=(0, 2))
    tk.Checkbutton(
        row_prev_n,
        text=_tr("与正式同"),
        variable=app.var_preview_batch_sync,
        command=app._on_preview_batch_sync_toggle,
        bg="white",
        fg="#000000",
        selectcolor="#F5F5F7",
        relief=tk.FLAT,
        font=("SF Pro Text", UI_FONT_PT_MAIN),
    ).pack(side=tk.LEFT, padx=(0, 10))
    tk.Label(
        row_prev_n,
        text=_tr("独立预览张数"),
        bg="white",
        fg="#333333",
        font=("SF Pro Text", UI_FONT_PT_MAIN),
    ).pack(side=tk.LEFT, padx=(0, 8))
    app.ent_preview_batch = tk.Entry(
        row_prev_n,
        textvariable=app.var_preview_batch_count,
        width=5,
        bg="#F5F5F7",
        fg="#000000",
        font=("SF Pro Text", UI_FONT_PT_MAIN),
        relief=tk.FLAT,
    )
    app.ent_preview_batch.pack(side=tk.LEFT, padx=(0, 10))
    tk.Label(
        row_prev_n,
        text=_tr("（解绑后上限 {cap}，用于快速试错）", cap=PREVIEW_BATCH_CAP_DECOUPLED),
        bg="white",
        fg="#888888",
        font=("SF Pro Text", UI_FONT_PT_SMALL),
    ).pack(side=tk.LEFT)

    preview_btn_row = tk.Frame(preview_panel, bg="white")
    preview_btn_row.pack(fill=tk.X, pady=(2, 4))
    app.btn_effect_preview = tk.Button(
        preview_btn_row,
        text=_tr("生成效果图预览"),
        command=lambda: app._on_effect_preview(is_regenerate=False),
        bg="white",
        fg="#0066CC",
        font=("SF Pro Text", UI_FONT_PT_MAIN),
        relief=tk.FLAT,
        padx=10,
        pady=6,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    app.btn_effect_preview.pack(side=tk.LEFT, padx=(0, 10))
    app.btn_effect_preview_again = tk.Button(
        preview_btn_row,
        text=_tr("重新生成预览"),
        command=lambda: app._on_effect_preview(is_regenerate=True),
        bg="white",
        fg="#0066CC",
        font=("SF Pro Text", UI_FONT_PT_MAIN),
        relief=tk.FLAT,
        padx=10,
        pady=6,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    app.btn_effect_preview_again.pack(side=tk.LEFT, padx=(0, 10))
    app.btn_preview_gallery = tk.Button(
        preview_btn_row,
        text=_tr("显示预览画廊"),
        command=app._toggle_preview_gallery,
        bg="white",
        fg="#0066CC",
        font=("SF Pro Text", UI_FONT_PT_MAIN),
        relief=tk.FLAT,
        padx=10,
        pady=4,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    app.btn_preview_gallery.pack(side=tk.LEFT, padx=(0, 10))
    app.btn_export_filtered_preview = tk.Button(
        preview_btn_row,
        text=_tr("将当前滤镜批量应用到现有预览并导出"),
        command=app._export_filtered_from_existing_previews,
        bg="white",
        fg="#0066CC",
        font=("SF Pro Text", UI_FONT_PT_MAIN),
        relief=tk.FLAT,
        padx=10,
        pady=6,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    app.btn_export_filtered_preview.pack(side=tk.LEFT, padx=(0, 10))
    app.btn_go = tk.Button(
        preview_btn_row,
        text=_tr("🚀 正式生成壁纸"),
        command=app._on_generate,
        bg="white",
        fg="#0066CC",
        font=("SF Pro Text", UI_FONT_PT_MAIN),
        relief=tk.FLAT,
        padx=10,
        pady=6,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    app.btn_go.pack(side=tk.LEFT, padx=(0, 10))
    app.btn_open_output = tk.Button(
        preview_btn_row,
        text=_tr("打开输出目录"),
        command=app._open_output_dir,
        bg="white",
        fg="#0066CC",
        font=("SF Pro Text", UI_FONT_PT_MAIN),
        relief=tk.FLAT,
        padx=10,
        pady=6,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    app.btn_open_output.pack(side=tk.LEFT)

    # 底栏先 pack（贴窗底），再 pack 分隔线，分隔线在状态栏上方
    bottom_bar = tk.Frame(main, bg="white")
    bottom_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 5))
    footer_rule = tk.Frame(main, bg="#E5E5EA", height=1, bd=0, highlightthickness=0)
    app._footer_rule = footer_rule
    footer_rule.pack_propagate(False)
    footer_rule.pack(side=tk.BOTTOM, fill=tk.X)
    status_col = tk.Frame(bottom_bar, bg="white")
    status_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor=tk.W)
    prog_wrap = tk.Frame(status_col, bg="white")
    prog_wrap.pack(anchor=tk.W, fill=tk.X, pady=(0, 4))
    app._progress = ttk.Progressbar(
        prog_wrap,
        mode="determinate",
        maximum=100,
        value=0,
        length=320,
    )
    app._progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
    app.btn_cancel_task = tk.Button(
        prog_wrap,
        text=_tr("取消任务"),
        state=tk.DISABLED,
        command=app._request_cancel_task,
        bg="white",
        fg="#CC0000",
        font=("SF Pro Text", UI_FONT_PT_SMALL, "bold"),
        relief=tk.FLAT,
        padx=10,
        pady=2,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    app.btn_cancel_task.pack(side=tk.RIGHT, padx=(10, 0))
    app.lbl_task_phase = tk.Label(
        status_col,
        text="",
        bg="white",
        fg="#666666",
        font=("SF Pro Text", UI_FONT_PT_SMALL),
        justify=tk.LEFT,
        anchor=tk.W,
    )
    app.lbl_task_phase.pack(anchor=tk.W, fill=tk.X)
    app.lbl_status = tk.Label(
        status_col,
        text=_tr("✅ 就绪"),
        bg="white",
        fg="#000000",
        font=("SF Pro Text", UI_FONT_PT_SMALL),
        justify=tk.LEFT,
    )
    app.lbl_status.pack(anchor=tk.W)
    app.lbl_seed_status = tk.Label(
        status_col,
        textvariable=app.var_seed_status,
        bg="white",
        fg="#555555",
        font=("SF Pro Text", UI_FONT_PT_SMALL),
        wraplength=720,
        justify=tk.LEFT,
    )
    app.lbl_seed_status.pack(anchor=tk.W, pady=(2, 0))
    tk.Label(
        bottom_bar,
        text=f"© {APP_COPYRIGHT_YEAR} {APP_NAME} v{APP_VERSION} by {APP_AUTHOR}",
        font=("SF Pro Text", UI_FONT_PT_MICRO),
        bg="white",
        fg="#8E8E93",
    ).pack(side=tk.RIGHT, padx=(8, 0), anchor=tk.SE)

    app._on_preview_batch_sync_toggle()
    app._sync_export_controls_state()
    app._apply_theme()

