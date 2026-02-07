from __future__ import annotations

import math

from .types import PositionedGraph, PositionedNode, PositionedEdge, PositionedGroup, Point
from .theme import DiagramColors, svg_open_tag, build_style_block
from .styles import (
    FONT_SIZES,
    FONT_WEIGHTS,
    STROKE_WIDTHS,
    ARROW_HEAD,
    estimate_text_width,
    TEXT_BASELINE_SHIFT,
)

# ============================================================================
# SVG renderer — converts a PositionedGraph into an SVG string.
# ============================================================================


def render_svg(
    graph: PositionedGraph,
    colors: DiagramColors,
    font: str = "Inter",
    transparent: bool = False,
) -> str:
    """Render a positioned graph as an SVG string."""
    parts: list[str] = []

    parts.append(svg_open_tag(graph.width, graph.height, colors, transparent))
    parts.append(build_style_block(font, False))
    parts.append("<defs>")
    parts.append(_arrow_marker_defs())
    parts.append("</defs>")

    # 1. Group backgrounds
    for group in graph.groups:
        parts.append(_render_group(group, font))

    # 2. Edges
    for edge in graph.edges:
        parts.append(_render_edge(edge))

    # 3. Edge labels
    for edge in graph.edges:
        if edge.label:
            parts.append(_render_edge_label(edge, font))

    # 4. Node shapes
    for node in graph.nodes:
        parts.append(_render_node_shape(node))

    # 5. Node labels
    for node in graph.nodes:
        parts.append(_render_node_label(node, font))

    parts.append("</svg>")
    return "\n".join(parts)


# ============================================================================
# Arrow marker definitions
# ============================================================================


def _arrow_marker_defs() -> str:
    w = ARROW_HEAD["width"]
    h = ARROW_HEAD["height"]
    return (
        f'  <marker id="arrowhead" markerWidth="{w}" markerHeight="{h}" '
        f'refX="{w}" refY="{h / 2}" orient="auto">\n'
        f'    <polygon points="0 0, {w} {h / 2}, 0 {h}" fill="var(--_arrow)" />\n'
        f"  </marker>\n"
        f'  <marker id="arrowhead-start" markerWidth="{w}" markerHeight="{h}" '
        f'refX="0" refY="{h / 2}" orient="auto-start-reverse">\n'
        f'    <polygon points="{w} 0, 0 {h / 2}, {w} {h}" fill="var(--_arrow)" />\n'
        f"  </marker>"
    )


# ============================================================================
# Group rendering
# ============================================================================


def _render_group(group: PositionedGroup, font: str) -> str:
    header_height = FONT_SIZES["group_header"] + 16
    parts: list[str] = []

    parts.append(
        f'<rect x="{group.x}" y="{group.y}" width="{group.width}" height="{group.height}" '
        f'rx="0" ry="0" fill="var(--_group-fill)" stroke="var(--_node-stroke)" '
        f'stroke-width="{STROKE_WIDTHS["outer_box"]}" />'
    )

    parts.append(
        f'<rect x="{group.x}" y="{group.y}" width="{group.width}" height="{header_height}" '
        f'rx="0" ry="0" fill="var(--_group-hdr)" stroke="var(--_node-stroke)" '
        f'stroke-width="{STROKE_WIDTHS["outer_box"]}" />'
    )

    parts.append(
        f'<text x="{group.x + 12}" y="{group.y + header_height / 2}" '
        f'dy="{TEXT_BASELINE_SHIFT}" font-size="{FONT_SIZES["group_header"]}" '
        f'font-weight="{FONT_WEIGHTS["group_header"]}" '
        f'fill="var(--_text-sec)">{escape_xml(group.label)}</text>'
    )

    for child in group.children:
        parts.append(_render_group(child, font))

    return "\n".join(parts)


# ============================================================================
# Edge rendering
# ============================================================================


def _render_edge(edge: PositionedEdge) -> str:
    if len(edge.points) < 2:
        return ""

    path_data = _points_to_polyline_path(edge.points)
    dash_array = ' stroke-dasharray="4 4"' if edge.style == "dotted" else ""
    stroke_width = (
        STROKE_WIDTHS["connector"] * 2
        if edge.style == "thick"
        else STROKE_WIDTHS["connector"]
    )

    markers = ""
    if edge.has_arrow_end:
        markers += ' marker-end="url(#arrowhead)"'
    if edge.has_arrow_start:
        markers += ' marker-start="url(#arrowhead-start)"'

    return (
        f'<polyline points="{path_data}" fill="none" stroke="var(--_line)" '
        f'stroke-width="{stroke_width}"{dash_array}{markers} />'
    )


def _points_to_polyline_path(points: list[Point]) -> str:
    return " ".join(f"{p.x},{p.y}" for p in points)


def _render_edge_label(edge: PositionedEdge, font: str) -> str:
    mid = edge.label_position if edge.label_position else _edge_midpoint(edge.points)
    label = edge.label or ""
    text_width = estimate_text_width(
        label, FONT_SIZES["edge_label"], FONT_WEIGHTS["edge_label"]
    )
    padding = 8
    bg_width = text_width + padding * 2
    bg_height = FONT_SIZES["edge_label"] + padding * 2

    return (
        f'<rect x="{mid.x - bg_width / 2}" y="{mid.y - bg_height / 2}" '
        f'width="{bg_width}" height="{bg_height}" rx="4" ry="4" '
        f'fill="var(--bg)" stroke="var(--_inner-stroke)" stroke-width="0.5" />\n'
        f'<text x="{mid.x}" y="{mid.y}" text-anchor="middle" dy="{TEXT_BASELINE_SHIFT}" '
        f'font-size="{FONT_SIZES["edge_label"]}" font-weight="{FONT_WEIGHTS["edge_label"]}" '
        f'fill="var(--_text-muted)">{escape_xml(label)}</text>'
    )


def _edge_midpoint(points: list[Point]) -> Point:
    if not points:
        return Point(x=0, y=0)
    if len(points) == 1:
        return points[0]

    total_length = 0.0
    for i in range(1, len(points)):
        total_length += _dist(points[i - 1], points[i])

    remaining = total_length / 2
    for i in range(1, len(points)):
        seg_len = _dist(points[i - 1], points[i])
        if remaining <= seg_len:
            t = remaining / seg_len if seg_len > 0 else 0
            return Point(
                x=points[i - 1].x + t * (points[i].x - points[i - 1].x),
                y=points[i - 1].y + t * (points[i].y - points[i - 1].y),
            )
        remaining -= seg_len

    return points[-1]


def _dist(a: Point, b: Point) -> float:
    return math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)


# ============================================================================
# Node rendering
# ============================================================================


def _render_node_shape(node: PositionedNode) -> str:
    x, y, w, h = node.x, node.y, node.width, node.height
    style = node.inline_style or {}

    fill = escape_xml(style.get("fill", "var(--_node-fill)"))
    stroke = escape_xml(style.get("stroke", "var(--_node-stroke)"))
    sw = escape_xml(style.get("stroke-width", str(STROKE_WIDTHS["inner_box"])))

    shape = node.shape
    if shape == "diamond":
        return _render_diamond(x, y, w, h, fill, stroke, sw)
    elif shape == "rounded":
        return _render_rounded_rect(x, y, w, h, fill, stroke, sw)
    elif shape == "stadium":
        return _render_stadium(x, y, w, h, fill, stroke, sw)
    elif shape == "circle":
        return _render_circle(x, y, w, h, fill, stroke, sw)
    elif shape == "subroutine":
        return _render_subroutine(x, y, w, h, fill, stroke, sw)
    elif shape == "doublecircle":
        return _render_double_circle(x, y, w, h, fill, stroke, sw)
    elif shape == "hexagon":
        return _render_hexagon(x, y, w, h, fill, stroke, sw)
    elif shape == "cylinder":
        return _render_cylinder(x, y, w, h, fill, stroke, sw)
    elif shape == "asymmetric":
        return _render_asymmetric(x, y, w, h, fill, stroke, sw)
    elif shape == "trapezoid":
        return _render_trapezoid(x, y, w, h, fill, stroke, sw)
    elif shape == "trapezoid-alt":
        return _render_trapezoid_alt(x, y, w, h, fill, stroke, sw)
    elif shape == "state-start":
        return _render_state_start(x, y, w, h)
    elif shape == "state-end":
        return _render_state_end(x, y, w, h)
    else:
        return _render_rect(x, y, w, h, fill, stroke, sw)


def _render_rect(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'rx="0" ry="0" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'
    )


def _render_rounded_rect(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'rx="6" ry="6" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'
    )


def _render_stadium(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    r = h / 2
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'rx="{r}" ry="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'
    )


def _render_circle(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    cx = x + w / 2
    cy = y + h / 2
    r = min(w, h) / 2
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'
    )


def _render_diamond(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    cx = x + w / 2
    cy = y + h / 2
    hw = w / 2
    hh = h / 2
    points = f"{cx},{cy - hh} {cx + hw},{cy} {cx},{cy + hh} {cx - hw},{cy}"
    return f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'


def _render_subroutine(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    inset = 8
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'rx="0" ry="0" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />\n'
        f'<line x1="{x + inset}" y1="{y}" x2="{x + inset}" y2="{y + h}" '
        f'stroke="{stroke}" stroke-width="{sw}" />\n'
        f'<line x1="{x + w - inset}" y1="{y}" x2="{x + w - inset}" y2="{y + h}" '
        f'stroke="{stroke}" stroke-width="{sw}" />'
    )


def _render_double_circle(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    cx = x + w / 2
    cy = y + h / 2
    outer_r = min(w, h) / 2
    inner_r = outer_r - 5
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{outer_r}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />\n'
        f'<circle cx="{cx}" cy="{cy}" r="{inner_r}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'
    )


def _render_hexagon(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    inset = h / 4
    points = (
        f"{x + inset},{y} {x + w - inset},{y} {x + w},{y + h / 2} "
        f"{x + w - inset},{y + h} {x + inset},{y + h} {x},{y + h / 2}"
    )
    return f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'


def _render_cylinder(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    ry = 7
    cx = x + w / 2
    body_top = y + ry
    body_h = h - 2 * ry
    return (
        f'<rect x="{x}" y="{body_top}" width="{w}" height="{body_h}" '
        f'fill="{fill}" stroke="none" />\n'
        f'<line x1="{x}" y1="{body_top}" x2="{x}" y2="{body_top + body_h}" '
        f'stroke="{stroke}" stroke-width="{sw}" />\n'
        f'<line x1="{x + w}" y1="{body_top}" x2="{x + w}" y2="{body_top + body_h}" '
        f'stroke="{stroke}" stroke-width="{sw}" />\n'
        f'<ellipse cx="{cx}" cy="{y + h - ry}" rx="{w / 2}" ry="{ry}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />\n'
        f'<ellipse cx="{cx}" cy="{body_top}" rx="{w / 2}" ry="{ry}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'
    )


def _render_asymmetric(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    indent = 12
    points = (
        f"{x + indent},{y} {x + w},{y} {x + w},{y + h} "
        f"{x + indent},{y + h} {x},{y + h / 2}"
    )
    return f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'


def _render_trapezoid(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    inset = w * 0.15
    points = (
        f"{x + inset},{y} {x + w - inset},{y} "
        f"{x + w},{y + h} {x},{y + h}"
    )
    return f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'


def _render_trapezoid_alt(
    x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: str
) -> str:
    inset = w * 0.15
    points = (
        f"{x},{y} {x + w},{y} "
        f"{x + w - inset},{y + h} {x + inset},{y + h}"
    )
    return f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" />'


def _render_state_start(x: float, y: float, w: float, h: float) -> str:
    cx = x + w / 2
    cy = y + h / 2
    r = min(w, h) / 2 - 2
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="var(--_text)" stroke="none" />'


def _render_state_end(x: float, y: float, w: float, h: float) -> str:
    cx = x + w / 2
    cy = y + h / 2
    outer_r = min(w, h) / 2 - 2
    inner_r = outer_r - 4
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{outer_r}" '
        f'fill="none" stroke="var(--_text)" stroke-width="{STROKE_WIDTHS["inner_box"] * 2}" />\n'
        f'<circle cx="{cx}" cy="{cy}" r="{inner_r}" fill="var(--_text)" stroke="none" />'
    )


# ============================================================================
# Node label rendering
# ============================================================================


def _render_node_label(node: PositionedNode, font: str) -> str:
    if node.shape in ("state-start", "state-end") and not node.label:
        return ""

    cx = node.x + node.width / 2
    cy = node.y + node.height / 2

    text_color = escape_xml(
        (node.inline_style or {}).get("color", "var(--_text)")
    )

    return (
        f'<text x="{cx}" y="{cy}" text-anchor="middle" dy="{TEXT_BASELINE_SHIFT}" '
        f'font-size="{FONT_SIZES["node_label"]}" font-weight="{FONT_WEIGHTS["node_label"]}" '
        f'fill="{text_color}">{escape_xml(node.label)}</text>'
    )


# ============================================================================
# Utilities
# ============================================================================


def escape_xml(text: str) -> str:
    """Escape special XML characters in text content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
