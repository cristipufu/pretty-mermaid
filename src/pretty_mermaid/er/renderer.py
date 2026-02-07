from __future__ import annotations

import math

from .types import (
    PositionedErDiagram,
    PositionedErEntity,
    PositionedErRelationship,
    ErAttribute,
    Cardinality,
)
from ..theme import DiagramColors, svg_open_tag, build_style_block
from ..styles import (
    FONT_SIZES,
    FONT_WEIGHTS,
    STROKE_WIDTHS,
    estimate_text_width,
    TEXT_BASELINE_SHIFT,
)

# ============================================================================
# ER diagram SVG renderer
#
# Renders positioned ER diagrams to SVG.
# All colors use CSS custom properties (var(--_xxx)) from the theme system.
#
# Render order:
#   1. Relationship lines (behind boxes)
#   2. Entity boxes (header + attribute rows)
#   3. Cardinality markers (crow's foot notation)
#   4. Relationship labels
# ============================================================================

# Font sizes specific to ER diagrams
ER_FONT_ATTR_SIZE = 11
ER_FONT_ATTR_WEIGHT = 400
ER_FONT_KEY_SIZE = 9
ER_FONT_KEY_WEIGHT = 600


def render_er_svg(
    diagram: PositionedErDiagram,
    colors: DiagramColors,
    font: str = "Inter",
    transparent: bool = False,
) -> str:
    """Render a positioned ER diagram as an SVG string.

    Args:
        diagram: The positioned ER diagram to render.
        colors: DiagramColors with bg/fg and optional enrichment variables.
        font: Font family name for text rendering.
        transparent: If True, renders with transparent background.
    """
    parts: list[str] = []

    # SVG root with CSS variables + style block (with mono font) + defs
    parts.append(svg_open_tag(diagram.width, diagram.height, colors, transparent))
    parts.append(build_style_block(font, True))
    parts.append("<defs>")
    parts.append("</defs>")  # No marker defs -- we draw crow's foot inline

    # 1. Relationship lines
    for rel in diagram.relationships:
        parts.append(_render_relationship_line(rel))

    # 2. Entity boxes
    for entity in diagram.entities:
        parts.append(_render_entity_box(entity))

    # 3. Cardinality markers at relationship endpoints
    for rel in diagram.relationships:
        parts.append(_render_cardinality(rel))

    # 4. Relationship labels
    for rel in diagram.relationships:
        parts.append(_render_relationship_label(rel))

    parts.append("</svg>")
    return "\n".join(parts)


# ============================================================================
# Entity box rendering
# ============================================================================


def _render_entity_box(entity: PositionedErEntity) -> str:
    """Render an entity box with header and attribute rows."""
    x = entity.x
    y = entity.y
    width = entity.width
    height = entity.height
    header_height = entity.header_height
    row_height = entity.row_height
    label = entity.label
    attributes = entity.attributes

    parts: list[str] = []

    # Outer rectangle
    parts.append(
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="0" ry="0" fill="var(--_node-fill)" stroke="var(--_node-stroke)" '
        f'stroke-width="{STROKE_WIDTHS["outer_box"]}" />'
    )

    # Header background
    parts.append(
        f'<rect x="{x}" y="{y}" width="{width}" height="{header_height}" '
        f'rx="0" ry="0" fill="var(--_group-hdr)" stroke="var(--_node-stroke)" '
        f'stroke-width="{STROKE_WIDTHS["outer_box"]}" />'
    )

    # Entity name
    parts.append(
        f'<text x="{x + width / 2}" y="{y + header_height / 2}" text-anchor="middle" '
        f'dy="{TEXT_BASELINE_SHIFT}" font-size="{FONT_SIZES["node_label"]}" '
        f'font-weight="700" fill="var(--_text)">{_escape_xml(label)}</text>'
    )

    # Divider
    attr_top = y + header_height
    parts.append(
        f'<line x1="{x}" y1="{attr_top}" x2="{x + width}" y2="{attr_top}" '
        f'stroke="var(--_node-stroke)" stroke-width="{STROKE_WIDTHS["inner_box"]}" />'
    )

    # Attribute rows
    for i, attr in enumerate(attributes):
        row_y = attr_top + i * row_height + row_height / 2
        parts.append(_render_attribute(attr, x, row_y, width))

    # Empty row placeholder when no attributes
    if len(attributes) == 0:
        parts.append(
            f'<text x="{x + width / 2}" y="{attr_top + row_height / 2}" text-anchor="middle" '
            f'dy="{TEXT_BASELINE_SHIFT}" font-size="{ER_FONT_ATTR_SIZE}" '
            f'fill="var(--_text-faint)" font-style="italic">(no attributes)</text>'
        )

    return "\n".join(parts)


def _render_attribute(attr: ErAttribute, box_x: float, y: float, box_width: float) -> str:
    """Render a single attribute row with monospace syntax highlighting.

    Layout: [PK badge]  type  name  (left-aligned in mono, name right-aligned)
    Uses <tspan> elements for per-part coloring, matching the class diagram style.

    Key badge uses var(--_key-badge) for background tint.
    """
    parts: list[str] = []

    # Key badges on the left (keep proportional font -- they're visual tags, not code)
    key_width = 0.0
    if attr.keys:
        key_text = ",".join(attr.keys)
        key_width = estimate_text_width(key_text, ER_FONT_KEY_SIZE, ER_FONT_KEY_WEIGHT) + 8
        parts.append(
            f'<rect x="{box_x + 6}" y="{y - 7}" width="{key_width}" height="14" '
            f'rx="2" ry="2" fill="var(--_key-badge)" />'
        )
        parts.append(
            f'<text x="{box_x + 6 + key_width / 2}" y="{y}" text-anchor="middle" '
            f'dy="{TEXT_BASELINE_SHIFT}" font-size="{ER_FONT_KEY_SIZE}" '
            f'font-weight="{ER_FONT_KEY_WEIGHT}" fill="var(--_text-sec)">'
            f"{key_text}</text>"
        )

    # Type (left-aligned after keys, monospace with syntax highlighting)
    type_x = box_x + 8 + (key_width + 6 if key_width > 0 else 0)
    parts.append(
        f'<text x="{type_x}" y="{y}" class="mono" dy="{TEXT_BASELINE_SHIFT}" '
        f'font-size="{ER_FONT_ATTR_SIZE}" font-weight="{ER_FONT_ATTR_WEIGHT}">'
        f'<tspan fill="var(--_text-muted)">{_escape_xml(attr.type)}</tspan></text>'
    )

    # Name (right-aligned, monospace with syntax highlighting)
    name_x = box_x + box_width - 8
    parts.append(
        f'<text x="{name_x}" y="{y}" class="mono" text-anchor="end" '
        f'dy="{TEXT_BASELINE_SHIFT}" font-size="{ER_FONT_ATTR_SIZE}" '
        f'font-weight="{ER_FONT_ATTR_WEIGHT}">'
        f'<tspan fill="var(--_text-sec)">{_escape_xml(attr.name)}</tspan></text>'
    )

    return "\n".join(parts)


# ============================================================================
# Relationship rendering
# ============================================================================


def _render_relationship_line(rel: PositionedErRelationship) -> str:
    """Render a relationship line."""
    if len(rel.points) < 2:
        return ""

    path_data = " ".join(f"{px},{py}" for (px, py) in rel.points)
    dash_array = ' stroke-dasharray="6 4"' if not rel.identifying else ""

    return (
        f'<polyline points="{path_data}" fill="none" stroke="var(--_line)" '
        f'stroke-width="{STROKE_WIDTHS["connector"]}"{dash_array} />'
    )


def _render_relationship_label(rel: PositionedErRelationship) -> str:
    """Render a relationship label at the midpoint."""
    if not rel.label or len(rel.points) < 2:
        return ""

    mid = _midpoint(rel.points)
    text_width = estimate_text_width(
        rel.label, FONT_SIZES["edge_label"], FONT_WEIGHTS["edge_label"]
    )

    # Background pill for readability
    bg_w = text_width + 8
    bg_h = FONT_SIZES["edge_label"] + 6

    return (
        f'<rect x="{mid[0] - bg_w / 2}" y="{mid[1] - bg_h / 2}" '
        f'width="{bg_w}" height="{bg_h}" rx="2" ry="2" '
        f'fill="var(--bg)" stroke="var(--_inner-stroke)" stroke-width="0.5" />'
        f'\n<text x="{mid[0]}" y="{mid[1]}" text-anchor="middle" '
        f'dy="{TEXT_BASELINE_SHIFT}" font-size="{FONT_SIZES["edge_label"]}" '
        f'font-weight="{FONT_WEIGHTS["edge_label"]}" '
        f'fill="var(--_text-muted)">{_escape_xml(rel.label)}</text>'
    )


def _render_cardinality(rel: PositionedErRelationship) -> str:
    """Render crow's foot cardinality markers at both endpoints of a relationship.

    Crow's foot notation:
      'one':       --||--  (single vertical line)
      'zero-one':  --o||-- (circle + single line)
      'many':      --<|--  (crow's foot + single line)
      'zero-many': --o<|-- (circle + crow's foot)
    """
    if len(rel.points) < 2:
        return ""
    parts: list[str] = []

    # Entity1 side (first point, direction toward second point)
    p1 = rel.points[0]
    p2 = rel.points[1]
    parts.append(_render_crows_foot(p1, p2, rel.cardinality1))

    # Entity2 side (last point, direction toward second-to-last point)
    p_n = rel.points[-1]
    p_n1 = rel.points[-2]
    parts.append(_render_crows_foot(p_n, p_n1, rel.cardinality2))

    return "\n".join(parts)


def _render_crows_foot(
    point: tuple[float, float],
    toward: tuple[float, float],
    cardinality: Cardinality,
) -> str:
    """Render a crow's foot marker at a given endpoint.

    ``point`` is the endpoint, ``toward`` gives the direction the line comes from.
    """
    parts: list[str] = []
    sw = STROKE_WIDTHS["connector"] + 0.25

    # Calculate direction from toward -> point (unit vector)
    dx = point[0] - toward[0]
    dy = point[1] - toward[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length == 0:
        return ""
    ux = dx / length
    uy = dy / length

    # Perpendicular direction
    px = -uy
    py = ux

    # Marker sits 4px from the endpoint, extending 12px back along the edge
    tip_x = point[0] - ux * 4
    tip_y = point[1] - uy * 4
    back_x = point[0] - ux * 16
    back_y = point[1] - uy * 16

    # Single line: always present for 'one' and part of others
    has_one_line = cardinality in ("one", "zero-one")
    has_crows_foot = cardinality in ("many", "zero-many")
    has_circle = cardinality in ("zero-one", "zero-many")

    # Draw single vertical line (perpendicular to edge) at the tip
    if has_one_line:
        half_w = 6
        parts.append(
            f'<line x1="{tip_x + px * half_w}" y1="{tip_y + py * half_w}" '
            f'x2="{tip_x - px * half_w}" y2="{tip_y - py * half_w}" '
            f'stroke="var(--_line)" stroke-width="{sw}" />'
        )
        # Second line slightly back for "exactly one" emphasis
        line2_x = tip_x - ux * 4
        line2_y = tip_y - uy * 4
        parts.append(
            f'<line x1="{line2_x + px * half_w}" y1="{line2_y + py * half_w}" '
            f'x2="{line2_x - px * half_w}" y2="{line2_y - py * half_w}" '
            f'stroke="var(--_line)" stroke-width="{sw}" />'
        )

    # Crow's foot (three lines fanning out from tip)
    if has_crows_foot:
        fan_w = 7
        cf_tip_x = tip_x
        cf_tip_y = tip_y
        # Top fan line
        parts.append(
            f'<line x1="{cf_tip_x + px * fan_w}" y1="{cf_tip_y + py * fan_w}" '
            f'x2="{back_x}" y2="{back_y}" '
            f'stroke="var(--_line)" stroke-width="{sw}" />'
        )
        # Center line
        parts.append(
            f'<line x1="{cf_tip_x}" y1="{cf_tip_y}" '
            f'x2="{back_x}" y2="{back_y}" '
            f'stroke="var(--_line)" stroke-width="{sw}" />'
        )
        # Bottom fan line
        parts.append(
            f'<line x1="{cf_tip_x - px * fan_w}" y1="{cf_tip_y - py * fan_w}" '
            f'x2="{back_x}" y2="{back_y}" '
            f'stroke="var(--_line)" stroke-width="{sw}" />'
        )

    # Circle (for zero variants)
    if has_circle:
        circle_offset = 20 if has_crows_foot else 12
        circle_x = point[0] - ux * circle_offset
        circle_y = point[1] - uy * circle_offset
        parts.append(
            f'<circle cx="{circle_x}" cy="{circle_y}" r="4" '
            f'fill="var(--bg)" stroke="var(--_line)" stroke-width="{sw}" />'
        )

    return "\n".join(parts)


# ============================================================================
# Utilities
# ============================================================================


def _midpoint(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Compute the arc-length midpoint of a polyline path.

    Walks along each segment, finds the point at exactly 50% of total path length.
    This ensures the label sits ON the path even for orthogonal routes with bends,
    unlike the naive first/last geometric center which floats in space for L/Z shapes.
    """
    if len(points) == 0:
        return (0.0, 0.0)
    if len(points) == 1:
        return points[0]

    # Compute total path length
    total_len = 0.0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        total_len += math.sqrt(dx * dx + dy * dy)

    if total_len == 0:
        return points[0]

    # Walk to 50% of total length, interpolating within the segment that crosses the halfway mark
    half_len = total_len / 2
    walked = 0.0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        seg_len = math.sqrt(dx * dx + dy * dy)
        if walked + seg_len >= half_len:
            t = (half_len - walked) / seg_len if seg_len > 0 else 0
            return (
                points[i - 1][0] + dx * t,
                points[i - 1][1] + dy * t,
            )
        walked += seg_len

    return points[-1]


def _escape_xml(text: str) -> str:
    """Escape special XML characters in text content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
