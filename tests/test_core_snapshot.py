from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat

from wallpaper_maker.core import create_wallpaper


def _build_fixture_images(folder: str, n: int = 10) -> list[str]:
    os.makedirs(folder, exist_ok=True)
    out: list[str] = []
    for i in range(n):
        p = os.path.join(folder, f"im_{i}.png")
        im = Image.new(
            "RGB",
            (640 + i * 7, 960 + i * 5),
            (30 + i * 12, 70 + i * 9, 110 + i * 6),
        )
        d = ImageDraw.Draw(im)
        d.rectangle((20, 20, 220, 260), outline=(240, 240, 240), width=6)
        d.ellipse((260, 120, 520, 420), outline=(255, 180, 80), width=5)
        d.text((48, 68), f"T{i}", fill=(255, 255, 180))
        im.save(p)
        out.append(p)
    return out


def _render_stats() -> dict:
    with tempfile.TemporaryDirectory(prefix="wm_core_snapshot_") as td:
        src = os.path.join(td, "src")
        out = os.path.join(td, "out")
        os.makedirs(out, exist_ok=True)
        paths = _build_fixture_images(src, 10)
        save = os.path.join(out, "snap.png")
        create_wallpaper(
            image_paths=paths,
            count=8,
            w=960,
            h=540,
            out_dir=out,
            custom_text="",
            seed=20260403,
            layout="scatter",
            bg_base_style="from_covers",
            bg_overlay_style="cinematic_grade",
            bg_overlay_strength=74,
            filter_style="cool_tone",
            filter_strength=76,
            show_stamp=False,
            save_path_override=save,
        )
        with Image.open(save).convert("RGB") as im:
            st = ImageStat.Stat(im)
            return {
                "size": [im.width, im.height],
                "mean": [round(x, 4) for x in st.mean],
                "stddev": [round(x, 4) for x in st.stddev],
                "samples": {
                    "p00": list(im.getpixel((0, 0))),
                    "p_center": list(im.getpixel((im.width // 2, im.height // 2))),
                    "p_br": list(im.getpixel((im.width - 1, im.height - 1))),
                    "p_q1": list(im.getpixel((im.width // 4, im.height // 4))),
                    "p_q3": list(
                        im.getpixel((im.width * 3 // 4, im.height * 3 // 4))
                    ),
                },
            }


def test_core_snapshot_statistics_stable() -> None:
    snap_path = (
        Path(__file__).resolve().parent / "snapshots" / "core_render_snapshot_v1.json"
    )
    baseline = json.loads(snap_path.read_text(encoding="utf-8"))
    got = _render_stats()

    assert got["size"] == baseline["size"]
    for i in range(3):
        assert abs(float(got["mean"][i]) - float(baseline["mean"][i])) <= 0.8
        assert abs(float(got["stddev"][i]) - float(baseline["stddev"][i])) <= 0.8
    for k, px in baseline["samples"].items():
        assert got["samples"][k] == px

