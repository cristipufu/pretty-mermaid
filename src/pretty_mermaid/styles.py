from __future__ import annotations

# ============================================================================
# Font metrics — character width estimates for Inter at different sizes.
# ============================================================================


def estimate_text_width(text: str, font_size: float, font_weight: int) -> float:
    """Average character width in px at the given font size and weight (proportional font)."""
    if font_weight >= 600:
        width_ratio = 0.58
    elif font_weight >= 500:
        width_ratio = 0.55
    else:
        width_ratio = 0.52
    return len(text) * font_size * width_ratio


def estimate_mono_text_width(text: str, font_size: float) -> float:
    """Average character width in px for monospace fonts (uniform glyph width)."""
    return len(text) * font_size * 0.6


# Monospace font family
MONO_FONT = "'JetBrains Mono'"
MONO_FONT_STACK = f"{MONO_FONT}, 'SF Mono', 'Fira Code', ui-monospace, monospace"

# Fixed font sizes (px)
FONT_SIZES = {
    "node_label": 13,
    "edge_label": 11,
    "group_header": 12,
}

# Font weights per element type
FONT_WEIGHTS = {
    "node_label": 500,
    "edge_label": 400,
    "group_header": 600,
}

# ============================================================================
# Spacing & sizing constants
# ============================================================================

GROUP_HEADER_CONTENT_PAD = 8

NODE_PADDING = {
    "horizontal": 16,
    "vertical": 10,
    "diamond_extra": 24,
}

STROKE_WIDTHS = {
    "outer_box": 1,
    "inner_box": 0.75,
    "connector": 0.75,
}

TEXT_BASELINE_SHIFT = "0.35em"

ARROW_HEAD = {
    "width": 8,
    "height": 4.8,
}
