"""导出相关工具：格式归一化、扩展名解析、保存编码与 ICC。"""
from __future__ import annotations

import os
from typing import Optional

from PIL import Image

from wallpaper_maker.config import DEFAULT_JPEG_QUALITY, DEFAULT_WEBP_QUALITY

_SRGB_ICC_TRIED = False
_SRGB_ICC_BYTES: Optional[bytes] = None


def _normalize_export_format(raw: object) -> str:
    s = (str(raw).strip().lower() if raw is not None else "png")
    if s in ("jpg", "jpeg"):
        return "jpeg"
    if s == "webp":
        return "webp"
    return "png"


def _export_ext(fmt: str) -> str:
    norm = _normalize_export_format(fmt)
    return ".jpg" if norm == "jpeg" else f".{norm}"


def _srgb_icc_profile_bytes() -> Optional[bytes]:
    """由 Pillow 生成标准 sRGB ICC 字节，供嵌入 PNG/JPEG/WebP。"""
    global _SRGB_ICC_TRIED, _SRGB_ICC_BYTES
    if _SRGB_ICC_TRIED:
        return _SRGB_ICC_BYTES
    _SRGB_ICC_TRIED = True
    try:
        from PIL import ImageCms

        pr = ImageCms.createProfile("sRGB")
        _SRGB_ICC_BYTES = ImageCms.ImageCmsProfile(pr).tobytes()
    except Exception:
        _SRGB_ICC_BYTES = None
    return _SRGB_ICC_BYTES


def _export_save_path_resolved(path: str, export_format: str) -> str:
    """使输出路径扩展名与编码格式一致（保留所选目录与主文件名）。"""
    base, _ext = os.path.splitext(path)
    return base + _export_ext(export_format)


def _save_wallpaper_file(
    im: Image.Image,
    path: str,
    *,
    export_format: str = "png",
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    webp_quality: int = DEFAULT_WEBP_QUALITY,
    webp_lossless: bool = False,
    embed_srgb_icc: bool = True,
) -> None:
    fmt = _normalize_export_format(export_format)
    icc = _srgb_icc_profile_bytes() if embed_srgb_icc else None

    if im.mode != "RGB":
        im = im.convert("RGB")

    if fmt == "png":
        kw: dict = {"format": "PNG", "compress_level": 6}
        if icc:
            kw["icc_profile"] = icc
        im.save(path, **kw)
        return

    if fmt == "jpeg":
        q = max(1, min(95, int(jpeg_quality)))
        kw = {"format": "JPEG", "quality": q, "optimize": True, "subsampling": 0}
        if icc:
            kw["icc_profile"] = icc
        im.save(path, **kw)
        return

    kw = {"format": "WEBP", "method": 6}
    if webp_lossless:
        kw["lossless"] = True
    else:
        kw["quality"] = max(1, min(100, int(webp_quality)))
    if icc:
        kw["icc_profile"] = icc
    im.save(path, **kw)

