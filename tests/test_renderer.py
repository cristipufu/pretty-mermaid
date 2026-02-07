"""Tests for the SVG renderer.

Uses hand-crafted PositionedGraph data to test SVG output without
depending on the layout engine.
"""
from __future__ import annotations

import re

import pytest

from pretty_mermaid.renderer import render_svg
from pretty_mermaid.theme import DiagramColors
from pretty_mermaid.types import (
    PositionedGraph,
    PositionedNode,
    PositionedEdge,
    PositionedGroup,
    Point,
)


def make_graph(**overrides) -> PositionedGraph:
    """Minimal positioned graph for testing."""
    defaults = dict(
        width=400,
        height=300,
        nodes=[],
        edges=[],
        groups=[],
    )
    defaults.update(overrides)
    return PositionedGraph(**defaults)


def make_node(**overrides) -> PositionedNode:
    """Helper to build a positioned node."""
    defaults = dict(
        id="A",
        label="Test",
        shape="rectangle",
        x=100,
        y=100,
        width=80,
        height=40,
    )
    defaults.update(overrides)
    return PositionedNode(**defaults)


def make_edge(**overrides) -> PositionedEdge:
    """Helper to build a positioned edge with arrow defaults."""
    defaults = dict(
        source="A",
        target="B",
        label=None,
        style="solid",
        has_arrow_start=False,
        has_arrow_end=True,
        points=[Point(x=100, y=120), Point(x=100, y=200)],
    )
    defaults.update(overrides)
    return PositionedEdge(**defaults)


light_colors = DiagramColors(bg="#FFFFFF", fg="#27272A")
dark_colors = DiagramColors(bg="#18181B", fg="#FAFAFA")


# ============================================================================
# SVG structure
# ============================================================================


class TestSvgStructure:
    def test_produces_a_valid_svg_root_element(self):
        svg = render_svg(make_graph(), light_colors)
        assert '<svg xmlns="http://www.w3.org/2000/svg"' in svg
        assert 'viewBox="0 0 400 300"' in svg
        assert 'width="400"' in svg
        assert 'height="300"' in svg
        assert "</svg>" in svg

    def test_includes_defs_with_arrow_markers(self):
        svg = render_svg(make_graph(), light_colors)
        assert "<defs>" in svg
        assert '<marker id="arrowhead"' in svg
        assert '<marker id="arrowhead-start"' in svg
        assert "</defs>" in svg

    def test_includes_embedded_google_fonts_import(self):
        svg = render_svg(make_graph(), light_colors, "Inter")
        assert "fonts.googleapis.com" in svg
        assert "Inter" in svg

    def test_uses_custom_font_name_when_specified(self):
        svg = render_svg(make_graph(), light_colors, "Roboto Mono")
        assert "Roboto%20Mono" in svg
        assert "'Roboto Mono'" in svg

    def test_sets_css_color_variables_in_inline_style(self):
        light = render_svg(make_graph(), light_colors)
        assert "--bg:#FFFFFF" in light
        assert "--fg:#27272A" in light

        dark = render_svg(make_graph(), dark_colors)
        assert "--bg:#18181B" in dark
        assert "--fg:#FAFAFA" in dark


# ============================================================================
# Original node shapes
# ============================================================================


class TestNodeShapes:
    def test_renders_rectangle_with_rx_0(self):
        graph = make_graph(nodes=[make_node(shape="rectangle")])
        svg = render_svg(graph, light_colors)
        assert 'rx="0" ry="0"' in svg

    def test_renders_rounded_rectangle_with_rx_6(self):
        graph = make_graph(nodes=[make_node(shape="rounded")])
        svg = render_svg(graph, light_colors)
        assert 'rx="6" ry="6"' in svg

    def test_renders_stadium_with_rx_half_height(self):
        node = make_node(shape="stadium", height=40)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert 'rx="20.0" ry="20.0"' in svg

    def test_renders_circle_with_circle_element(self):
        node = make_node(shape="circle", width=60, height=60)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert "<circle" in svg
        assert 'r="30.0"' in svg

    def test_renders_diamond_with_polygon(self):
        node = make_node(shape="diamond", width=80, height=80)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert "<polygon" in svg
        assert 'points="140.0,100.0 180.0,140.0 140.0,180.0 100.0,140.0"' in svg

    def test_renders_node_labels_as_text_elements(self):
        graph = make_graph(nodes=[make_node(label="My Node")])
        svg = render_svg(graph, light_colors)
        assert ">My Node</text>" in svg


# ============================================================================
# New Batch 1 shapes
# ============================================================================


class TestBatch1Shapes:
    def test_renders_subroutine_with_outer_rect_and_inset_vertical_lines(self):
        node = make_node(shape="subroutine", width=100, height=40)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert '<rect x="100" y="100" width="100" height="40"' in svg
        assert 'x1="108"' in svg
        assert 'x1="192"' in svg
        assert "<line" in svg

    def test_renders_double_circle_with_two_circle_elements(self):
        node = make_node(shape="doublecircle", width=80, height=80)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        circle_matches = re.findall(r"<circle", svg)
        assert len(circle_matches) == 2
        assert 'r="40.0"' in svg
        assert 'r="35.0"' in svg

    def test_renders_hexagon_with_6_point_polygon(self):
        node = make_node(shape="hexagon", width=100, height=40)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert "<polygon" in svg
        polygon_match = re.search(r'points="([^"]+)"', svg)
        points = polygon_match.group(1).split(" ") if polygon_match else []
        assert len(points) == 6


# ============================================================================
# New Batch 2 shapes
# ============================================================================


class TestBatch2Shapes:
    def test_renders_cylinder_with_ellipses_and_body_rect(self):
        node = make_node(shape="cylinder", width=80, height=50)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        ellipse_matches = re.findall(r"<ellipse", svg)
        assert len(ellipse_matches) == 2
        assert "<rect" in svg

    def test_renders_asymmetric_flag_with_5_point_polygon(self):
        node = make_node(shape="asymmetric", width=100, height=40)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert "<polygon" in svg
        all_polygons = re.findall(r'points="([^"]+)"', svg)
        shape_polygon = all_polygons[-1]
        points = shape_polygon.split(" ")
        assert len(points) == 5

    def test_renders_trapezoid_with_4_point_polygon(self):
        node = make_node(shape="trapezoid", width=100, height=40)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert "<polygon" in svg
        all_polygons = re.findall(r'points="([^"]+)"', svg)
        shape_polygon = all_polygons[-1]
        points = shape_polygon.split(" ")
        assert len(points) == 4

    def test_renders_trapezoid_alt_with_4_point_polygon(self):
        node = make_node(shape="trapezoid-alt", width=100, height=40)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert "<polygon" in svg
        all_polygons = re.findall(r'points="([^"]+)"', svg)
        shape_polygon = all_polygons[-1]
        points = shape_polygon.split(" ")
        assert len(points) == 4


# ============================================================================
# Batch 3: State diagram pseudostates
# ============================================================================


class TestStatePseudostates:
    def test_renders_state_start_as_a_filled_circle(self):
        node = make_node(shape="state-start", label="", width=28, height=28)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert "<circle" in svg
        assert 'fill="var(--_text)"' in svg
        assert 'stroke="none"' in svg

    def test_renders_state_end_as_bullseye(self):
        node = make_node(shape="state-end", label="", width=28, height=28)
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        circle_matches = re.findall(r"<circle", svg)
        assert len(circle_matches) == 2
        assert 'fill="none"' in svg
        assert 'fill="var(--_text)"' in svg


# ============================================================================
# Edge rendering
# ============================================================================


class TestEdges:
    def test_renders_a_solid_edge_as_polyline_with_end_arrow(self):
        edge = make_edge(style="solid", has_arrow_end=True)
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)
        assert "<polyline" in svg
        assert 'points="100,120 100,200"' in svg
        assert 'marker-end="url(#arrowhead)"' in svg

    def test_renders_dotted_edges_with_stroke_dasharray(self):
        edge = make_edge(style="dotted")
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)
        assert 'stroke-dasharray="4 4"' in svg

    def test_renders_thick_edges_with_doubled_stroke_width(self):
        edge = make_edge(style="thick")
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)
        assert 'stroke-width="1.5"' in svg

    def test_does_not_add_dasharray_to_solid_edges(self):
        edge = make_edge(style="solid")
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)
        assert "dasharray" not in svg

    def test_skips_edges_with_fewer_than_2_points(self):
        edge = make_edge(points=[Point(x=0, y=0)])
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)
        assert "<polyline" not in svg

    def test_renders_no_arrow_edge_without_marker_end(self):
        edge = make_edge(has_arrow_end=False, has_arrow_start=False)
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)
        assert "<polyline" in svg
        assert "marker-end" not in svg
        assert "marker-start" not in svg

    def test_renders_bidirectional_edge_with_both_markers(self):
        edge = make_edge(has_arrow_start=True, has_arrow_end=True)
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)
        assert 'marker-end="url(#arrowhead)"' in svg
        assert 'marker-start="url(#arrowhead-start)"' in svg


# ============================================================================
# Edge labels
# ============================================================================


class TestEdgeLabels:
    def test_renders_edge_label_with_background_pill(self):
        edge = make_edge(label="Yes")
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)
        assert ">Yes</text>" in svg
        assert 'rx="4" ry="4"' in svg

    def test_does_not_render_label_elements_for_edges_without_labels(self):
        edge = make_edge(label=None)
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)
        text_matches = re.findall(r"<text[^>]*>.*?</text>", svg)
        assert len(text_matches) == 0

    def test_uses_label_position_when_provided_instead_of_edge_midpoint(self):
        edge = make_edge(
            label="Go",
            points=[Point(x=100, y=120), Point(x=100, y=200)],
            label_position=Point(x=50, y=80),
        )
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)

        assert 'x="50" y="80"' in svg
        assert 'y="160"' not in svg


# ============================================================================
# Group rendering (subgraphs)
# ============================================================================


class TestGroups:
    def test_renders_group_with_outer_rectangle_and_header_band(self):
        group = PositionedGroup(
            id="sg1", label="Backend",
            x=20, y=20, width=200, height=150, children=[],
        )
        graph = make_graph(groups=[group])
        svg = render_svg(graph, light_colors)
        rect_count = len(re.findall(r'x="20" y="20"', svg))
        assert rect_count >= 2
        assert ">Backend</text>" in svg

    def test_renders_nested_groups_recursively(self):
        inner = PositionedGroup(
            id="inner", label="Inner",
            x=40, y=60, width=120, height=80, children=[],
        )
        outer = PositionedGroup(
            id="outer", label="Outer",
            x=20, y=20, width=200, height=150, children=[inner],
        )
        graph = make_graph(groups=[outer])
        svg = render_svg(graph, light_colors)
        assert ">Outer</text>" in svg
        assert ">Inner</text>" in svg


# ============================================================================
# Inline style support
# ============================================================================


class TestInlineStyles:
    def test_applies_inline_fill_override(self):
        node = make_node(inline_style={"fill": "#ff0000"})
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert 'fill="#ff0000"' in svg

    def test_applies_inline_stroke_override(self):
        node = make_node(inline_style={"stroke": "#00ff00"})
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert 'stroke="#00ff00"' in svg

    def test_applies_inline_text_color_override(self):
        node = make_node(inline_style={"color": "#0000ff"})
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert 'fill="#0000ff"' in svg

    def test_falls_back_to_theme_when_no_inline_style(self):
        node = make_node()
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert 'fill="var(--_node-fill)"' in svg


# ============================================================================
# XML escaping
# ============================================================================


class TestXmlEscaping:
    def test_escapes_special_characters_in_node_labels(self):
        node = make_node(label="<script> & \"quotes\" 'apos'")
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert "&lt;script&gt;" in svg
        assert "&amp;" in svg
        assert "&quot;quotes&quot;" in svg
        assert "&#39;apos&#39;" in svg

    def test_escapes_special_characters_in_edge_labels(self):
        edge = make_edge(label="A & B > C")
        graph = make_graph(edges=[edge])
        svg = render_svg(graph, light_colors)
        assert "A &amp; B &gt; C" in svg

    def test_escapes_special_characters_in_group_labels(self):
        group = PositionedGroup(
            id="g1", label="A < B",
            x=0, y=0, width=100, height=100, children=[],
        )
        graph = make_graph(groups=[group])
        svg = render_svg(graph, light_colors)
        assert "A &lt; B" in svg

    def test_escapes_attribute_injection_in_inline_style_fill(self):
        node = make_node(inline_style={"fill": 'red" onmouseover="alert(1)'})
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert 'onmouseover="alert' not in svg
        assert 'red&quot; onmouseover=&quot;alert(1)' in svg

    def test_escapes_element_injection_in_inline_style_fill(self):
        node = make_node(inline_style={"fill": 'red"/><svg onload="alert(1)"><rect fill="x'})
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert "<svg onload" not in svg
        assert "&lt;svg onload=" in svg

    def test_escapes_injection_in_inline_style_stroke(self):
        node = make_node(inline_style={"stroke": 'blue" onclick="alert(1)'})
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert 'onclick="alert' not in svg
        assert 'blue&quot; onclick=&quot;alert(1)' in svg

    def test_escapes_injection_in_inline_style_stroke_width(self):
        node = make_node(inline_style={"stroke-width": '2" onmouseover="alert(1)'})
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert 'onmouseover="alert' not in svg
        assert '2&quot; onmouseover=&quot;alert(1)' in svg

    def test_escapes_injection_in_inline_style_color(self):
        node = make_node(inline_style={"color": 'green" onfocus="alert(1)'})
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert 'onfocus="alert' not in svg
        assert 'green&quot; onfocus=&quot;alert(1)' in svg


# ============================================================================
# Theme application
# ============================================================================


class TestCssVariableTheming:
    def test_uses_css_variables_for_styling_light_colors(self):
        node = make_node()
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, light_colors)
        assert "var(--_node-fill)" in svg
        assert "var(--_node-stroke)" in svg
        assert "var(--_text)" in svg

    def test_uses_same_css_variables_with_dark_colors(self):
        node = make_node()
        graph = make_graph(nodes=[node])
        svg = render_svg(graph, dark_colors)
        assert "var(--_node-fill)" in svg
        assert "var(--_node-stroke)" in svg
        assert "var(--_text)" in svg
        assert "--bg:#18181B" in svg

    def test_arrow_marker_uses_css_variable_for_fill(self):
        svg = render_svg(make_graph(), light_colors)
        assert 'fill="var(--_arrow)"' in svg
