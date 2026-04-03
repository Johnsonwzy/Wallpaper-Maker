"""Wallpaper Maker 模块化包。"""
from wallpaper_maker.config import APP_VERSION
from wallpaper_maker.app import WallPaperApp
from wallpaper_maker.core import create_wallpaper, run_cli

__version__ = APP_VERSION

__all__ = [
    "WallPaperApp",
    "create_wallpaper",
    "main",
    "run_cli",
    "__version__",
]


def __getattr__(name: str):
    """惰性导出 main，避免 `python -m wallpaper_maker.main` 触发 runpy 警告。"""
    if name == "main":
        from wallpaper_maker.main import main as _main

        return _main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
