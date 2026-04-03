"""UI 参数面板相关静态映射（从 app.py 拆分）。"""
from __future__ import annotations

from typing import Dict


BG_BASE_STYLE_KEY_BY_ZH: Dict[str, str] = {
    "从所选图取色渐变（推荐）": "from_covers",
    "浅灰上下微渐变": "neutral_gradient",
    "纯色浅灰底": "solid",
    "径向渐变（跟图取色）": "radial_covers",
    "自定义双色渐变（竖直）": "custom_gradient",
    "自定义双色径向渐变": "custom_gradient_radial",
    "杂志渐变（暖纸色多段）": "magazine_gradient",
}

BG_OVERLAY_STYLE_KEY_BY_ZH: Dict[str, str] = {
    "无叠层": "none",
    "磨砂质感": "frosted_glass",
    "暗角聚焦": "edge_vignette",
    "几何纹理": "geo_texture",
    "纸张纹理": "paper_grain",
    "柔光雾化": "soft_bloom",
    "电影分级": "cinematic_grade",
    "中心聚光": "radial_focus",
}

BG_OVERLAY_RECOMMENDED_STRENGTH: Dict[str, int] = {
    "none": 0,
    "frosted_glass": 78,
    "edge_vignette": 72,
    "geo_texture": 88,
    "paper_grain": 68,
    "soft_bloom": 62,
    "cinematic_grade": 74,
    "radial_focus": 66,
}

FILTER_STYLE_KEY_BY_ZH: Dict[str, str] = {
    "无滤镜（原始质感）": "none",
    "胶片质感（Film Grain）": "film_grain",
    "低饱和冷调（Cool Tone）": "cool_tone",
    "暖调胶片（Warm Vintage）": "warm_vintage",
    "高对比黑白（High Contrast B&W）": "high_contrast_bw",
    "柔焦朦胧（Soft Focus）": "soft_focus",
    "暗角（Vignette）": "vignette",
    "哑光褪黑（Matte Fade）": "matte_fade",
    "编辑锐感（Editorial Crisp）": "editorial_crisp",
    "Lomo暗角系（灵魂）": "lomo_vignette",
    "Lomo色调偏色系（特色）": "lomo_tone_shift",
    "Lomo褪色（复古系）": "lomo_fade",
    "Lomo光效系": "lomo_light_fx",
}

FILTER_RECOMMENDED_STRENGTH: Dict[str, int] = {
    "none": 0,
    "film_grain": 72,
    "cool_tone": 76,
    "warm_vintage": 74,
    "high_contrast_bw": 84,
    "soft_focus": 64,
    "vignette": 70,
    "matte_fade": 72,
    "editorial_crisp": 82,
    "lomo_vignette": 80,
    "lomo_tone_shift": 78,
    "lomo_fade": 76,
    "lomo_light_fx": 74,
}

