"""多文件夹图源扫描与抽样策略。"""
from __future__ import annotations

import os
import random
from typing import Dict, List, Optional, Sequence, Tuple

from wallpaper_maker.config import IMAGE_EXTENSIONS

def get_all_image_paths(folder: str, recursive: bool = False) -> list[str]:
    folder = os.path.expanduser(folder)
    if not os.path.isdir(folder):
        return []

    paths: list[str] = []

    def is_image(name: str) -> bool:
        lower = name.lower()
        return any(lower.endswith(ext.lower()) for ext in IMAGE_EXTENSIONS)

    if recursive:
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if is_image(f):
                    paths.append(os.path.join(root, f))
    else:
        for f in os.listdir(folder):
            fp = os.path.join(folder, f)
            if os.path.isfile(fp) and is_image(f):
                paths.append(fp)

    return sorted(paths)


def get_image_paths_from_folders(
    folders: Sequence[str],
    *,
    recursive: bool = False,
    per_folder_counts: Optional[List[Tuple[str, int]]] = None,
    per_folder_paths: Optional[List[Tuple[str, List[str]]]] = None,
) -> list[str]:
    """
    合并多个文件夹内的图片路径并去重（跨文件夹统一随机池）。
    如果传入 per_folder_counts（空列表），会追加 (folder_basename, count) 供调用方展示。
    如果传入 per_folder_paths（空列表），会追加 (folder_abs_path, unique_paths) 供抽样策略使用。
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in folders:
        folder = os.path.expanduser(str(raw).strip())
        if not folder or not os.path.isdir(folder):
            if per_folder_counts is not None:
                per_folder_counts.append((os.path.basename(raw.rstrip("/\\")), 0))
            if per_folder_paths is not None:
                per_folder_paths.append((os.path.abspath(os.path.expanduser(str(raw))), []))
            continue
        count_before = len(out)
        added_here: List[str] = []
        for p in get_all_image_paths(folder, recursive=recursive):
            key = os.path.normcase(os.path.abspath(p))
            if key not in seen:
                seen.add(key)
                out.append(p)
                added_here.append(p)
        if per_folder_counts is not None:
            per_folder_counts.append(
                (os.path.basename(folder.rstrip("/\\")), len(out) - count_before)
            )
        if per_folder_paths is not None:
            per_folder_paths.append((os.path.abspath(folder), added_here))
    return out


def _weighted_choice_index(weights: Sequence[float], rng: random.Random) -> Optional[int]:
    total = 0.0
    for w in weights:
        total += max(0.0, float(w))
    if total <= 0.0:
        return None
    hit = rng.random() * total
    acc = 0.0
    for i, w in enumerate(weights):
        acc += max(0.0, float(w))
        if hit <= acc:
            return i
    return len(weights) - 1 if weights else None


def pick_paths_by_strategy(
    pool_paths: Sequence[str],
    count: int,
    *,
    strategy: str = "natural",
    per_folder_paths: Optional[Sequence[Tuple[str, Sequence[str]]]] = None,
    folder_weight_by_path: Optional[Dict[str, float]] = None,
    seed: Optional[int] = None,
) -> List[str]:
    """
    按策略从图片池抽样：
    - natural：按总池自然比例（现有行为）
    - balanced：尽量每个文件夹都有（先每组 1 张，再补齐）
    - weighted：按文件夹权重抽样（组间权重；组内均匀）
    """
    paths = list(pool_paths)
    if not paths:
        return []
    n = max(1, min(int(count), len(paths)))
    sk = (strategy or "natural").strip().lower()
    rng = random.Random(seed)
    if sk == "natural" or not per_folder_paths:
        return rng.sample(paths, n)

    groups: List[Tuple[str, List[str]]] = []
    for folder, plist in per_folder_paths:
        cur = list(plist)
        if cur:
            groups.append((folder, cur))
    if not groups:
        return rng.sample(paths, n)

    if sk == "balanced":
        chosen: List[str] = []
        rng.shuffle(groups)
        if n >= len(groups):
            for _folder, g in groups:
                idx = rng.randrange(len(g))
                chosen.append(g.pop(idx))
            rem = n - len(chosen)
            if rem > 0:
                rest: List[str] = []
                for _folder, g in groups:
                    rest.extend(g)
                if rest:
                    chosen.extend(rng.sample(rest, min(rem, len(rest))))
        else:
            for _folder, g in groups[:n]:
                chosen.append(g[rng.randrange(len(g))])
        return chosen

    if sk == "weighted":
        folder_weight_by_path = folder_weight_by_path or {}
        mutable: List[Tuple[str, List[str], float]] = []
        for folder, g in groups:
            w = float(folder_weight_by_path.get(folder, 1.0))
            mutable.append((folder, g, max(0.0, w)))
        chosen: List[str] = []
        for _ in range(n):
            candidates = [x for x in mutable if x[1]]
            if not candidates:
                break
            ws = [x[2] for x in candidates]
            if sum(ws) <= 0:
                ws = [1.0] * len(candidates)
            gi = _weighted_choice_index(ws, rng)
            if gi is None:
                gi = rng.randrange(len(candidates))
            _folder, g, _w = candidates[gi]
            pi = rng.randrange(len(g))
            chosen.append(g.pop(pi))
        return chosen if chosen else rng.sample(paths, n)

    return rng.sample(paths, n)
