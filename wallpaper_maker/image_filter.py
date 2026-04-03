"""图源可读性快速校验与并行过滤。"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Sequence, Tuple

from PIL import Image

from wallpaper_maker.config import MAX_SOURCE_IMAGE_FILE_BYTES
def _filter_single_image_path_quick(p: str) -> Tuple[Optional[str], bool]:
    """
    快速校验单路径是否可作为图源：只做 stat + 解码（load），不做 RGB 转换。
    convert("RGB") 与怪异 ICC 的冲突留到实际绘制时捕获，避免前置扫描对整库双倍全图解码。
    返回 (path, is_bad)；is_bad 为 True 时计入剔除数。
    """
    try:
        if not os.path.isfile(p):
            return None, True
        sz = os.path.getsize(p)
        if sz <= 0 or sz > MAX_SOURCE_IMAGE_FILE_BYTES:
            return None, True
    except OSError:
        return None, True
    try:
        with Image.open(p) as im:
            im.load()
    except Exception:
        return None, True
    return p, False


def filter_readable_image_paths(
    paths: Sequence[str],
    *,
    max_workers: Optional[int] = None,
) -> Tuple[List[str], int]:
    """
    剔除零字节、非文件、过大及无法完整解码的路径，返回 (可用列表, 剔除数)。
    大批量时并行校验以缩短扫描时间；单路仍保持顺序。
    """
    if not paths:
        return [], 0
    good: List[str] = []
    bad = 0
    plist = list(paths)
    n = len(plist)
    if n < 12:
        for p in plist:
            g, is_bad = _filter_single_image_path_quick(p)
            if is_bad:
                bad += 1
            elif g:
                good.append(g)
        return good, bad

    if max_workers is None:
        # 限制并发，避免同时 decode 多张大图占满内存
        max_workers = min(8, max(2, (os.cpu_count() or 4)))
    else:
        max_workers = max(1, int(max_workers))

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_filter_single_image_path_quick, p) for p in plist]
        for fut in as_completed(futs):
            g, is_bad = fut.result()
            if is_bad:
                bad += 1
            elif g:
                good.append(g)
    return good, bad
