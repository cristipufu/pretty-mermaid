"""Tests for styles module -- text measurement and constants.

Theme resolution tests are also included here (CSS custom property system).
"""
from __future__ import annotations

import re

import pytest

from pretty_mermaid.styles import (
    estimate_text_width,
    FONT_SIZES,
    FONT_WEIGHTS,
    NODE_PADDING,
    STROKE_WIDTHS,
    ARROW_HEAD,
)
from pretty_mermaid.theme import (
    THEMES,
    DEFAULTS,
    from_shiki_theme,
    build_style_block,
    svg_open_tag,
    DiagramColors,
)


# ============================================================================
# Theme system (CSS custom properties)
# ============================================================================


class TestThemes:
    def test_contains_well_known_theme_palettes(self):
        assert "zinc-dark" in THEMES
        assert "tokyo-night" in THEMES
        assert "catppuccin-mocha" in THEMES
        assert "nord" in THEMES

    def test_each_theme_has_valid_bg_and_fg_colors(self):
        for name, colors in THEMES.items():
            assert re.match(r"^#[0-9a-fA-F]{6}$", colors.bg), f"{name} bg invalid"
            assert re.match(r"^#[0-9a-fA-F]{6}$", colors.fg), f"{name} fg invalid"


class TestDefaults:
    def test_provides_zinc_light_bg_fg(self):
        assert DEFAULTS["bg"] == "#FFFFFF"
        assert DEFAULTS["fg"] == "#27272A"


class TestSvgOpenTag:
    def test_sets_bg_and_fg_css_variables_in_inline_style(self):
        tag = svg_open_tag(400, 300, DiagramColors(bg="#1a1b26", fg="#a9b1d6"))
        assert "--bg:#1a1b26" in tag
        assert "--fg:#a9b1d6" in tag
        assert "background:var(--bg)" in tag

    def test_includes_optional_enrichment_variables_when_provided(self):
        colors = DiagramColors(
            bg="#1a1b26", fg="#a9b1d6",
            line="#3d59a1", accent="#7aa2f7",
        )
        tag = svg_open_tag(400, 300, colors)
        assert "--line:#3d59a1" in tag
        assert "--accent:#7aa2f7" in tag

    def test_omits_unset_enrichment_variables(self):
        tag = svg_open_tag(400, 300, DiagramColors(bg="#fff", fg="#000"))
        assert "--line" not in tag
        assert "--accent" not in tag
        assert "--muted" not in tag


class TestBuildStyleBlock:
    def test_includes_derived_css_variable_declarations(self):
        style = build_style_block("Inter", False)
        assert "--_text" in style
        assert "--_line" in style
        assert "--_arrow" in style
        assert "--_node-fill" in style
        assert "--_node-stroke" in style

    def test_includes_mono_font_class_when_requested(self):
        with_mono = build_style_block("Inter", True)
        assert ".mono" in with_mono
        assert "JetBrains Mono" in with_mono

        without_mono = build_style_block("Inter", False)
        assert ".mono" not in without_mono


class TestFromShikiTheme:
    def test_extracts_bg_fg_from_editor_colors(self):
        colors = from_shiki_theme({
            "type": "dark",
            "colors": {
                "editor.background": "#1a1b26",
                "editor.foreground": "#a9b1d6",
            },
        })
        assert colors.bg == "#1a1b26"
        assert colors.fg == "#a9b1d6"

    def test_falls_back_for_missing_editor_colors(self):
        dark = from_shiki_theme({"type": "dark"})
        assert dark.bg == "#1e1e1e"
        assert dark.fg == "#d4d4d4"

        light = from_shiki_theme({"type": "light"})
        assert light.bg == "#ffffff"
        assert light.fg == "#333333"


# ============================================================================
# Text width estimation
# ============================================================================


class TestEstimateTextWidth:
    def test_returns_a_positive_number_for_non_empty_text(self):
        width = estimate_text_width("Hello", 13, 500)
        assert width > 0

    def test_returns_0_for_empty_text(self):
        assert estimate_text_width("", 13, 500) == 0

    def test_scales_with_text_length(self):
        short = estimate_text_width("Hi", 13, 500)
        long = estimate_text_width("Hello World", 13, 500)
        assert long > short

    def test_scales_with_font_size(self):
        small = estimate_text_width("Text", 11, 500)
        large = estimate_text_width("Text", 16, 500)
        assert large > small

    def test_heavier_weights_produce_wider_estimates(self):
        regular = estimate_text_width("Text", 13, 400)
        bold = estimate_text_width("Text", 13, 600)
        assert bold > regular

    def test_produces_reasonable_widths_for_typical_node_labels(self):
        width = estimate_text_width("Hello", FONT_SIZES["node_label"], FONT_WEIGHTS["node_label"])
        assert width > 25
        assert width < 60


# ============================================================================
# Exported constants
# ============================================================================


class TestConstants:
    def test_font_sizes_has_expected_values(self):
        assert FONT_SIZES["node_label"] == 13
        assert FONT_SIZES["edge_label"] == 11
        assert FONT_SIZES["group_header"] == 12

    def test_font_weights_has_expected_values(self):
        assert FONT_WEIGHTS["node_label"] == 500
        assert FONT_WEIGHTS["edge_label"] == 400
        assert FONT_WEIGHTS["group_header"] == 600

    def test_node_padding_has_expected_values(self):
        assert NODE_PADDING["horizontal"] == 16
        assert NODE_PADDING["vertical"] == 10
        assert NODE_PADDING["diamond_extra"] == 24

    def test_stroke_widths_has_expected_values(self):
        assert STROKE_WIDTHS["outer_box"] == 1
        assert STROKE_WIDTHS["inner_box"] == 0.75
        assert STROKE_WIDTHS["connector"] == 0.75

    def test_arrow_head_has_expected_values(self):
        assert ARROW_HEAD["width"] == 8
        assert ARROW_HEAD["height"] == 4.8
