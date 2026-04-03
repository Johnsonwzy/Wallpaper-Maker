# Wallpaper Maker

[中文 README](README.md) | [English README](README_EN.md) | [中文评估报告](项目评估报告.md) | [English Evaluation Report](PROJECT_EVALUATION_REPORT_EN.md)

An open-source wallpaper batch generator built with Python + tkinter + Pillow. It supports multi-source sampling, 30+ layout templates, background overlays, post-processing filters, real-time preview, and batch export.

## Highlights

- **Multi-source sampling**: Multi-folder scan with natural / balanced / weighted strategies and automatic corrupted-image filtering
- **30+ layout templates**: grid / seamless / scatter / masonry / spiral / fan / heart / honeycomb, with three aesthetic intensity levels
- **Background blending**: Dual-layer architecture via `bg_base_style` + `bg_overlay_style`, 7+ overlay types, independent intensity control
- **12 filters**: Includes Lomo series, with intensity control and recommended intensity autofill
- **Real-time preview**: Switching filters/overlays/base color does not trigger relayout; contrast-enhanced mode is preview-only
- **Preview gallery**: Zoom, prev/next/first/last navigation, 1:1 view, and quick compare via spacebar
- **Batch export**: Standard generation and "apply current filter to existing previews" flow, with PNG / JPEG / WebP output
- **Theme support**: Light / dark / follow-system (automatic macOS dark-mode detection)
- **Preset management**: Built-in presets + custom save/load/delete with compatibility fallback for legacy payloads
- **Custom text overlay**: Text rendering with font detection

## Project Structure

```text
Wallpaper_Maker_3.0.py              # Compatibility entry
wallpaper_maker/                    # Main package (25 modules, ~8,360 LOC)
│
├── main.py                         # Main entry (GUI / CLI / self-test)
├── __main__.py                     # python -m wallpaper_maker support
├── __init__.py                     # Package initialization
│
├── app.py                          # Main GUI framework and event binding (~1,068 LOC)
├── app_build_ui.py                 # Complete UI construction
├── app_preview_pipeline.py         # Preview refresh and cache pipeline
├── app_export_jobs.py              # Export orchestration
├── app_presets_io.py               # Preset read/write and payload merge
├── app_windowing.py                # Window geometry and preview window sync
├── app_params.py                   # Param panel mapping and recommended intensity
├── app_theme.py                    # Theme resolution and system detection
├── app_task_scheduler.py           # Tk scheduled-task deduplication
├── preview_gallery.py              # Single-image preview gallery
│
├── core.py                         # Render orchestration, gradients, color utilities
├── core_layouts.py                 # 30+ layout renderers and drawing helpers
├── core_filters.py                 # 12 post-processing filters
├── core_overlays.py                # Background overlays
├── core_export.py                  # Export format normalization and encoding
│
├── config.py                       # Default config constants
├── presets.py                      # Preset templates and built-in presets
├── sampling.py                     # Source scan and sampling strategies
├── image_filter.py                 # Source filtering (corruption/size checks)
├── gui_utils.py                    # GUI common utilities
├── style_intensity.py              # Style intensity mapping
└── skip_stats.py                   # Skip/corrupted-image stats

tests/
├── test_sampling_presets_core_utils.py  # Sampling/params/presets/export logic
├── test_core_snapshot.py                # Core rendering snapshot regression
└── snapshots/
    └── core_render_snapshot_v1.json     # Rendering baseline snapshot
```

## Requirements

- Python 3.10+ (official Python distribution recommended)
- Pillow
- tkinter (usually bundled with official Python installers)

## Install and Launch

```bash
# Install Pillow (if missing)
python3 -m pip install Pillow

# Launch GUI (recommended)
python3 -m wallpaper_maker.main

# Or shorthand form
python3 -m wallpaper_maker

# Compatibility entry
python3 Wallpaper_Maker_3.0.py
```

## Common Commands

```bash
# CLI mode (built-in minimal command-line entry)
python3 -m wallpaper_maker.main --cli

# GUI smoke test
python3 -m wallpaper_maker.main --self-test

# GUI smoke test with per-step timing
python3 -m wallpaper_maker.main --self-test --self-test-verbose

# Minimal smoke test (skip preview window path)
python3 -m wallpaper_maker.main --self-test --self-test-no-preview

# Automated tests
python3 -m pytest -q
```

## 30-Second Quick Regression Checklist

Run in project root:

```bash
# 1) Minimal GUI smoke test (fastest)
python3 -m wallpaper_maker.main --self-test --self-test-no-preview

# 2) Full GUI smoke test + timings
python3 -m wallpaper_maker.main --self-test --self-test-verbose

# 3) Core automated regression (pytest)
python3 -m pytest -q
```

### Pass Criteria

- First two steps return code `0` and print `RESULT: PASS`
- Third step prints `passed` with no failed tests
- Stop on first failure and inspect logs from that step first

> Note: GUI self-test may fail in headless environments (for example, CI sandboxes).

## Usage Guide

### Basic Workflow

1. Launch app and choose source folders
2. Adjust layout type, base background color, overlays, and style intensity
3. Click "Generate Preview" to inspect results
4. In preview gallery, switch filters/overlays live without relayout
5. Export once satisfied

### Tuning Tips

- Enable "Contrast Enhanced Mode (preview-only)" while tuning to amplify visible differences without affecting final export
- Recommended intensities for filters/overlays are auto-filled; use them as practical starting points
- For reproducible results, set a fixed seed and enable "reuse preview seed"

### Batch Export

- "Apply current filter to existing previews and export" applies your tuned post-process style to all already-generated previews
- Output formats: PNG, JPEG, WebP

## Window Strategy

- Default theme: `system` (follows macOS light/dark mode automatically)
- Studio Display tuning is included: main and preview windows default to same size, symmetric alignment, and edge-locked sync

## Architecture Overview

After 10 rounds of functional-domain slicing, the project now has a clear layered structure:

| Layer | Modules | Description |
| ------ | ------- | ----------- |
| Entry | `main.py` / `__main__.py` | Startup and dispatch |
| GUI framework | `app.py` | Main UI, events, thin delegation |
| GUI submodules | `app_build_ui` / `app_preview_pipeline` / `app_export_jobs` ... | Domain-specific GUI responsibilities |
| Core rendering | `core.py` | Render orchestration entry |
| Rendering submodules | `core_layouts` / `core_filters` / `core_overlays` / `core_export` | Layouts/filters/overlays/export |
| Config and utilities | `config` / `presets` / `sampling` / `image_filter` ... | Infrastructure and shared utilities |

No circular dependencies are present. GUI submodules stay loosely coupled by receiving the `app` instance.

## Troubleshooting

| Issue | Fix |
| ----- | --- |
| `No module named PIL` | Run `python3 -m pip install Pillow` |
| Preview window does not appear | Generate preview first, then check preview gallery button/state |
| GUI-related exceptions | Run `--self-test` first and locate the failing step in logs |
| Empty export output | Check source folders contain valid images (jpg/png/webp/bmp/tiff) |

## Testing Notes

- Pytest regression suite covers sampling normalization, parameter mapping, preset merging, and export path logic
- `test_core_snapshot.py` uses fixed seed + fixed input for render drift detection
- In headless environments, GUI self-test may be restricted by system display constraints; run on desktop when possible

## Author / Version / License

- Author: `ZY Wei`
- Version: `v3.0.0`
- License: `Apache-2.0` ([LICENSE](LICENSE))

## Related Documents

- 中文 README: [README.md](README.md)
- Chinese evaluation report: [项目评估报告.md](项目评估报告.md)
- English evaluation report: [PROJECT_EVALUATION_REPORT_EN.md](PROJECT_EVALUATION_REPORT_EN.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
