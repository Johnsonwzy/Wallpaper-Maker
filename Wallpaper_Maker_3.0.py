"""兼容入口：等价于 `python -m wallpaper_maker.main`。
界面与渲染逻辑在 wallpaper_maker 包内（含高级背景与后期滤镜）。"""
from wallpaper_maker.main import main

if __name__ == "__main__":
    main()
