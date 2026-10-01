"""Color-theme naming shared with the frontend's own theme/palette definitions.

The frontend renders every slide client-side and owns the actual color
values; this module only decides which theme *name* to suggest, either from
an explicit preset or from title keywords.
"""

from __future__ import annotations

from typing import Optional

# Preset giao diện do client chọn (vd từ demo/API). Khác với theme theo từ khóa title.
VALID_SLIDE_PRESETS = frozenset({"corporate", "modern", "minimal"})

_KEYWORD_THEMES = (
    (("tech", "công nghệ", "kỹ thuật", "software", "code", "programming"), "blue"),
    (("marketing", "business", "kinh doanh", "bán hàng", "sales"), "orange"),
    (("health", "sức khỏe", "y tế", "medical", "wellness"), "green"),
    (("creative", "design", "thiết kế", "art", "nghệ thuật"), "purple"),
)


def normalize_slide_preset(preset: Optional[str]) -> Optional[str]:
    """Trả về corporate|modern|minimal hoặc None nếu không hợp lệ / để dùng theme theo title."""
    if preset is None:
        return None
    p = str(preset).strip().lower()
    return p if p in VALID_SLIDE_PRESETS else None


def detect_theme(title: str) -> str:
    """Phát hiện theme dựa trên từ khóa trong title."""
    title_lower = str(title or "").lower()
    for keywords, theme in _KEYWORD_THEMES:
        if any(kw in title_lower for kw in keywords):
            return theme
    return "default"
