from __future__ import annotations

from wallpaper_maker.core import _export_save_path_resolved, _norm_strength, _normalize_export_format
from wallpaper_maker.gui_utils import estimate_perf_hint
from wallpaper_maker.presets import _empty_preset_template, _merge_preset_payload
from wallpaper_maker.sampling import pick_paths_by_strategy


def test_pick_paths_natural_basic_properties() -> None:
    pool = [f"p{i}" for i in range(10)]
    out = pick_paths_by_strategy(pool, 5, strategy="natural", seed=42)
    assert len(out) == 5
    assert len(set(out)) == 5
    assert set(out).issubset(set(pool))


def test_pick_paths_balanced_prefers_each_folder() -> None:
    g1 = [f"a{i}" for i in range(4)]
    g2 = [f"b{i}" for i in range(4)]
    g3 = [f"c{i}" for i in range(4)]
    pool = g1 + g2 + g3
    out = pick_paths_by_strategy(
        pool,
        6,
        strategy="balanced",
        per_folder_paths=[("A", g1), ("B", g2), ("C", g3)],
        seed=7,
    )
    assert len(out) == 6
    assert any(x in out for x in g1)
    assert any(x in out for x in g2)
    assert any(x in out for x in g3)


def test_pick_paths_weighted_respects_zero_weight_folder() -> None:
    g1 = [f"a{i}" for i in range(8)]
    g2 = [f"b{i}" for i in range(8)]
    pool = g1 + g2
    out = pick_paths_by_strategy(
        pool,
        6,
        strategy="weighted",
        per_folder_paths=[("A", g1), ("B", g2)],
        folder_weight_by_path={"A": 1.0, "B": 0.0},
        seed=11,
    )
    # B 组权重为 0，正常情况下应只从 A 组抽取（若实现回退变动，此断言可提示行为漂移）
    assert all(x in g1 for x in out)


def test_preset_merge_compatible_and_filters_unknown_keys() -> None:
    payload = {
        "layout": "grid",
        "random_count": 99,
        "preset_file_version": 3,
        "unknown_new_key": "ignore_me",
    }
    merged = _merge_preset_payload(payload)
    template = _empty_preset_template()

    assert merged["layout"] == "grid"
    assert merged["random_count"] == 99
    assert merged["preset_version"] == 3
    assert "unknown_new_key" not in merged
    assert set(merged.keys()) == set(template.keys())


def test_export_format_normalization_and_save_path_resolution() -> None:
    assert _normalize_export_format("jpg") == "jpeg"
    assert _normalize_export_format("jpeg") == "jpeg"
    assert _normalize_export_format("webp") == "webp"
    assert _normalize_export_format("unknown") == "png"

    assert _export_save_path_resolved("/tmp/a.png", "jpg").endswith(".jpg")
    assert _export_save_path_resolved("/tmp/a.any", "jpeg").endswith(".jpg")
    assert _export_save_path_resolved("/tmp/a.jpeg", "webp").endswith(".webp")
    assert _export_save_path_resolved("/tmp/a.webp", "png").endswith(".png")


def test_norm_strength_curve_behavior() -> None:
    assert _norm_strength(0) == 0.0
    assert 0.0 < _norm_strength(30) < _norm_strength(60) < _norm_strength(100) <= 1.0
    # 非法值容错
    assert _norm_strength("bad") == 1.0


def test_perf_hint_safe_params_returns_empty() -> None:
    text, color = estimate_perf_hint(1920, 1080, 12, 3)
    assert text == ""
    assert color == ""


def test_perf_hint_extreme_params_returns_warning() -> None:
    text, color = estimate_perf_hint(7680, 4320, 40, 10)
    assert text != ""
    assert color != ""
    assert "⚡" in text


def test_perf_hint_ultra_high_res_warns_memory() -> None:
    text, _color = estimate_perf_hint(10240, 5760, 18, 6)
    assert "内存" in text or "超高分辨率" in text

