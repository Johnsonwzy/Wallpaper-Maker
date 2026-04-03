# Wallpaper Maker

[中文 README](README.md) | [English README](README_EN.md) | [中文评估报告](项目评估报告.md) | [English Evaluation Report](PROJECT_EVALUATION_REPORT_EN.md)

An open-source wallpaper batch generator built with Python + tkinter + Pillow.  
It supports multi-source sampling, 30+ layout templates, real-time preview, filters/overlays, and batch export (PNG/JPEG/WebP).

基于 Python + tkinter + Pillow 的壁纸批量生成工具。支持多图源抽样、30+ 版式构图、背景叠层、后期滤镜、实时预览与批量导出。

## 功能亮点

- **多图源抽样**：多文件夹扫描，natural / balanced / weighted 三种策略，自动过滤损坏图
- **30+ 布局模板**：grid / seamless / scatter / masonry / spiral / fan / heart / honeycomb 等，支持审美强度三档
- **背景混合**：`bg_base_style` + `bg_overlay_style` 双层架构，7+ 叠层类型，独立强度控制
- **12 类滤镜**：含 Lomo 系列，支持强度控制与推荐强度自动回填
- **实时预览**：切换滤镜/叠层/底色不重排版，对比增强模式辅助调参（仅预览生效）
- **预览画廊**：单图缩放、前后/首末导航、1:1 查看、空格快速对比
- **批量导出**：标准生成、"应用当前滤镜到现有预览"批量导出，支持 PNG / JPEG / WebP
- **主题**：浅色 / 深色 / 跟随系统（自动检测 macOS 暗色模式）
- **预设管理**：内置预设 + 自定义保存/加载/删除，兼容旧格式自动迁移
- **自定义文字**：文本叠加与字体检测

## 项目结构

```text
Wallpaper_Maker_3.0.py              # 兼容入口
wallpaper_maker/                     # 主包（25 模块，~8 360 行）
│
├── main.py                          # 主入口（GUI / CLI / self-test）
├── __main__.py                      # python -m wallpaper_maker 支持
├── __init__.py                      # 包初始化
│
├── app.py                           # 主界面框架与事件绑定（1 068 行）
├── app_build_ui.py                  # 完整 UI 构建
├── app_preview_pipeline.py          # 预览刷新与缓存流程
├── app_export_jobs.py               # 导出任务编排
├── app_presets_io.py                # 预设读写与数据合并
├── app_windowing.py                 # 窗口几何与预览窗同步
├── app_params.py                    # 参数面板映射与推荐强度
├── app_theme.py                     # 主题解析与系统检测
├── app_task_scheduler.py            # Tk 定时任务调度
├── preview_gallery.py               # 单图预览画廊
│
├── core.py                          # 渲染编排、渐变、色彩工具（863 行）
├── core_layouts.py                  # 30+ 布局渲染器与辅助绘图
├── core_filters.py                  # 12 类后期滤镜
├── core_overlays.py                 # 背景叠层
├── core_export.py                   # 导出格式归一化与保存编码
│
├── config.py                        # 默认配置常量
├── presets.py                       # 预设模板与内置预设
├── sampling.py                      # 图源扫描与抽样策略
├── image_filter.py                  # 图源过滤（损坏/尺寸检测）
├── gui_utils.py                     # GUI 通用工具
├── style_intensity.py               # 风格强度映射
└── skip_stats.py                    # 跳过/损坏图统计

tests/
├── test_sampling_presets_core_utils.py   # 抽样/参数/预设/导出逻辑
├── test_core_snapshot.py                 # 核心渲染快照回归
└── snapshots/
    └── core_render_snapshot_v1.json      # 渲染统计基线
```

## 环境要求

- Python 3.10+（建议官方 Python）
- Pillow
- tkinter（官方 Python 安装通常自带）

## 安装与启动

```bash
# 安装 Pillow（若未安装）
python3 -m pip install Pillow

# GUI 启动（推荐）
python3 -m wallpaper_maker.main

# 也可使用 python -m 简写
python3 -m wallpaper_maker

# 兼容入口
python3 Wallpaper_Maker_3.0.py
```

## 常用命令

```bash
# CLI 模式（内置极简命令行入口）
python3 -m wallpaper_maker.main --cli

# GUI 冒烟自检
python3 -m wallpaper_maker.main --self-test

# 带每步耗时
python3 -m wallpaper_maker.main --self-test --self-test-verbose

# 最小自检（跳过预览窗路径）
python3 -m wallpaper_maker.main --self-test --self-test-no-preview

# 自动化测试
python3 -m pytest -q
```

## 30 秒快速回归清单

在项目根目录依次执行：

```bash
# 1) 最小 GUI 冒烟（跳过预览窗，最快）
python3 -m wallpaper_maker.main --self-test --self-test-no-preview

# 2) 完整 GUI 冒烟 + 每步耗时
python3 -m wallpaper_maker.main --self-test --self-test-verbose

# 3) 核心自动化回归（pytest）
python3 -m pytest -q
```

**判定规则**：

- 前两步返回码为 `0` 且输出 `RESULT: PASS`
- 第三步输出 `passed` 且无失败用例
- 任一步失败即停止并优先排查该步日志

> 注意：在无图形显示环境（例如 CI 沙箱）运行 GUI 自检可能无法正常拉起窗口。

## 使用指南

### 基本工作流

1. 启动应用，选择图源文件夹
2. 调整布局类型、背景底色与叠层、风格强度等参数
3. 点击"生成效果图预览"查看结果
4. 在预览画廊中实时切换滤镜/叠层，效果立即可见（无需重新排版）
5. 满意后正式导出

### 调参技巧

- 调参阶段可开启"对比增强模式（仅预览）"，放大参数差异的可见性，不影响正式导出
- 滤镜与叠层的推荐强度会自动回填，可作为起点微调
- 若需复现结果，请固定 seed 并启用"沿用预览种子"

### 批量导出

- "应用当前滤镜到现有预览并导出"可将调好的后期效果批量应用到已生成的全部预览
- 支持 PNG、JPEG、WebP 三种格式

## 窗口策略

- 默认主题：`system`（自动跟随 macOS 明暗模式切换）
- Apple Studio Display 参数已优化：主窗与预览窗默认同尺寸、对称、紧贴同步

## 架构说明

项目经过 10 轮功能域切片，形成清晰的分层架构：

| 层级 | 模块 | 说明 |
|------|------|------|
| 入口层 | `main.py` / `__main__.py` | 启动调度 |
| GUI 框架层 | `app.py` | 主界面、事件绑定、薄委托 |
| GUI 子模块层 | `app_build_ui` / `app_preview_pipeline` / `app_export_jobs` 等 | 各功能域独立模块 |
| 核心渲染层 | `core.py` | 渲染编排入口 |
| 渲染子模块层 | `core_layouts` / `core_filters` / `core_overlays` / `core_export` | 布局/滤镜/叠层/导出 |
| 配置与工具层 | `config` / `presets` / `sampling` / `image_filter` 等 | 基础设施 |

模块间无循环依赖，GUI 子模块通过 `app` 实例参数松耦合。

## 故障排查

| 问题 | 解决方案 |
|------|---------|
| `No module named PIL` | `python3 -m pip install Pillow` |
| 预览窗未显示 | 先确认已生成预览，再检查"预览画廊"按钮状态 |
| GUI 相关异常 | 先执行 `--self-test`，根据输出定位失败步骤 |
| 导出文件为空 | 检查图源文件夹是否有有效图片（支持 jpg/png/webp/bmp/tiff） |

## 测试说明

- pytest 回归集覆盖：抽样策略归一化、参数映射、preset 合并、导出路径逻辑
- `test_core_snapshot.py` 使用固定 seed 与固定输入生成统计快照，监测核心渲染漂移
- 当前 7 项测试全部通过（~0.4s）
- 在无图形显示环境中，GUI 自检可能受系统限制；建议在本机桌面环境执行

## Author / Version / License

- Author: `ZY Wei`
- Version: `v3.0.0`
- License: `Apache-2.0` ([LICENSE](LICENSE))

## 相关文档

- 详细评估报告：[项目评估报告.md](项目评估报告.md)
- Evaluation report (English): [PROJECT_EVALUATION_REPORT_EN.md](PROJECT_EVALUATION_REPORT_EN.md)
- 变更日志：[CHANGELOG.md](CHANGELOG.md)
