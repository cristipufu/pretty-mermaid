from __future__ import annotations

from .types import (
    PositionedClassDiagram,
    PositionedClassNode,
    PositionedClassRelationship,
    ClassMember,
    RelationshipType,
    MarkerAt,
)
from ..theme import DiagramColors, svg_open_tag, build_style_block
from ..styles import (
    FONT_SIZES,
    FONT_WEIGHTS,
    STROKE_WIDTHS,
    estimate_text_width,
    TEXT_BASELINE_SHIFT,
    MONO_FONT_STACK,
)
from .layout import CLS

# ============================================================================
# Class diagram SVG renderer
#
# Renders positioned class diagrams to SVG.
# All colors use CSS custom properties (var(--_xxx)) from the theme system.
#
# Render order:
#   1. Relationship lines (behind boxes)
#   2. Class boxes (header + attributes + methods compartments)
#   3. Relationship endpoint markers (diamonds, triangles)
#   4. Labels and cardinality
# ============================================================================

# Font sizes specific to class diagrams
CLS_FONT = {
    "member_size": 11,
    "member_weight": 400,
    "annotation_size": 10,
    "annotation_weight": 500,
}


def render_class_svg(
    diagram: PositionedClassDiagram,
    colors: DiagramColors,
    font: str = "Inter",
    transparent: bool = False,
) -> str:
    """Render a positioned class diagram as an SVG string.

    Args:
        diagram: The positioned class diagram to render.
        colors: DiagramColors with bg/fg and optional enrichment variables.
        font: Font family name for text rendering.
        transparent: If True, renders with transparent background.
    """
    parts: list[str] = []

    # SVG root with CSS variables + style block (with mono font) + defs
    parts.append(svg_open_tag(diagram.width, diagram.height, colors, transparent))
    parts.append(build_style_block(font, True))
    parts.append("<defs>")
    parts.append(_relationship_marker_defs())
    parts.append("</defs>")

    # 1. Relationship lines (rendered behind boxes)
    for rel in diagram.relationships:
        parts.append(_render_relationship(rel))

    # 2. Class boxes
    for cls in diagram.classes:
        parts.append(_render_class_box(cls))

    # 3. Relationship labels and cardinality
    for rel in diagram.relationships:
        parts.append(_render_relationship_labels(rel))

    parts.append("</svg>")
    return "\n".join(parts)


# ============================================================================
# Marker definitions
# ============================================================================


def _relationship_marker_defs() -> str:
    """Marker definitions for class relationship endpoints.

    Each relationship type has a distinct marker:
      - inheritance: hollow triangle
      - composition: filled diamond
      - aggregation: hollow diamond
      - association: open arrow (simple >)
      - dependency: open arrow (simple >)
      - realization: hollow triangle (same as inheritance)

    Uses var(--_arrow) for fill/stroke and var(--bg) for hollow marker fills.
    """
    return (
        # Hollow triangle (inheritance, realization) -- points at target
        '  <marker id="cls-inherit" markerWidth="12" markerHeight="10" refX="12" refY="5" orient="auto-start-reverse">'
        '\n    <polygon points="0 0, 12 5, 0 10" fill="var(--bg)" stroke="var(--_arrow)" stroke-width="1.5" />'
        "\n  </marker>"
        # Filled diamond (composition) -- points at source
        '\n  <marker id="cls-composition" markerWidth="12" markerHeight="10" refX="0" refY="5" orient="auto-start-reverse">'
        '\n    <polygon points="6 0, 12 5, 6 10, 0 5" fill="var(--_arrow)" stroke="var(--_arrow)" stroke-width="1" />'
        "\n  </marker>"
        # Hollow diamond (aggregation) -- points at source
        '\n  <marker id="cls-aggregation" markerWidth="12" markerHeight="10" refX="0" refY="5" orient="auto-start-reverse">'
        '\n    <polygon points="6 0, 12 5, 6 10, 0 5" fill="var(--bg)" stroke="var(--_arrow)" stroke-width="1.5" />'
        "\n  </marker>"
        # Open arrow (association, dependency)
        '\n  <marker id="cls-arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto-start-reverse">'
        '\n    <polyline points="0 0, 8 3, 0 6" fill="none" stroke="var(--_arrow)" stroke-width="1.5" />'
        "\n  </marker>"
    )


# ============================================================================
# Class box rendering
# ============================================================================


def _render_class_box(cls: PositionedClassNode) -> str:
    """Render a class box with 3 compartments: header, attributes, methods."""
    x, y, width, height = cls.x, cls.y, cls.width, cls.height
    header_height = cls.header_height
    attr_height = cls.attr_height
    method_height = cls.method_height
    parts: list[str] = []

    # Outer rectangle (full box)
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

    # Annotation (<<interface>>, <<abstract>>, etc.)
    name_y = y + header_height / 2
    if cls.annotation:
        annot_y = y + 12
        parts.append(
            f'<text x="{x + width / 2}" y="{annot_y}" text-anchor="middle" dy="{TEXT_BASELINE_SHIFT}" '
            f'font-size="{CLS_FONT["annotation_size"]}" font-weight="{CLS_FONT["annotation_weight"]}" '
            f'font-style="italic" fill="var(--_text-muted)">&lt;&lt;{_escape_xml(cls.annotation)}&gt;&gt;</text>'
        )
        name_y = y + header_height / 2 + 6

    # Class name
    parts.append(
        f'<text x="{x + width / 2}" y="{name_y}" text-anchor="middle" dy="{TEXT_BASELINE_SHIFT}" '
        f'font-size="{FONT_SIZES["node_label"]}" font-weight="700" '
        f'fill="var(--_text)">{_escape_xml(cls.label)}</text>'
    )

    # Divider line between header and attributes
    attr_top = y + header_height
    parts.append(
        f'<line x1="{x}" y1="{attr_top}" x2="{x + width}" y2="{attr_top}" '
        f'stroke="var(--_node-stroke)" stroke-width="{STROKE_WIDTHS["inner_box"]}" />'
    )

    # Attributes
    member_row_h = 20
    for i, member in enumerate(cls.attributes):
        member_y = attr_top + 4 + i * member_row_h + member_row_h / 2
        parts.append(_render_member(member, x + CLS["box_pad_x"], member_y))

    # Divider line between attributes and methods
    method_top = attr_top + attr_height
    parts.append(
        f'<line x1="{x}" y1="{method_top}" x2="{x + width}" y2="{method_top}" '
        f'stroke="var(--_node-stroke)" stroke-width="{STROKE_WIDTHS["inner_box"]}" />'
    )

    # Methods
    for i, member in enumerate(cls.methods):
        member_y = method_top + 4 + i * member_row_h + member_row_h / 2
        parts.append(_render_member(member, x + CLS["box_pad_x"], member_y))

    return "\n".join(parts)


def _render_member(member: ClassMember, x: float, y: float) -> str:
    """Render a single class member with syntax highlighting.

    Uses <tspan> elements to color each part of the member differently:
      - visibility symbol (+/-/#/~) -> textFaint
      - member name (incl. parens for methods) -> textSecondary
      - colon separator -> textFaint
      - type annotation -> textMuted
    """
    font_style = ' font-style="italic"' if member.is_abstract else ""
    decoration = ' text-decoration="underline"' if member.is_static else ""

    # Build tspan parts for syntax-highlighted member text
    spans: list[str] = []

    if member.visibility:
        spans.append(
            f'<tspan fill="var(--_text-faint)">{_escape_xml(member.visibility)} </tspan>'
        )

    spans.append(f'<tspan fill="var(--_text-sec)">{_escape_xml(member.name)}</tspan>')

    if member.type:
        spans.append('<tspan fill="var(--_text-faint)">: </tspan>')
        spans.append(
            f'<tspan fill="var(--_text-muted)">{_escape_xml(member.type)}</tspan>'
        )

    return (
        f'<text x="{x}" y="{y}" class="mono" dy="{TEXT_BASELINE_SHIFT}" '
        f'font-size="{CLS_FONT["member_size"]}" font-weight="{CLS_FONT["member_weight"]}"'
        f"{font_style}{decoration}>"
        f"{''.join(spans)}</text>"
    )


# ============================================================================
# Relationship rendering
# ============================================================================


def _render_relationship(rel: PositionedClassRelationship) -> str:
    """Render a relationship line with appropriate markers."""
    if len(rel.points) < 2:
        return ""

    path_data = " ".join(f'{p["x"]},{p["y"]}' for p in rel.points)
    is_dashed = rel.type in ("dependency", "realization")
    dash_array = ' stroke-dasharray="6 4"' if is_dashed else ""

    # Determine markers based on relationship type and which end has the marker
    markers = _get_relationship_markers(rel.type, rel.marker_at)

    return (
        f'<polyline points="{path_data}" fill="none" stroke="var(--_line)" '
        f'stroke-width="{STROKE_WIDTHS["connector"]}"{dash_array}{markers} />'
    )


def _get_relationship_markers(type_: RelationshipType, marker_at: MarkerAt) -> str:
    """Get marker-start/marker-end attributes for a relationship type.

    Uses `marker_at` from the parser to place the marker on the correct end:
      - 'from' -> marker-start (prefix arrows like `<|--`, `*--`, `o--`)
      - 'to'   -> marker-end   (suffix arrows like `..|>`, `-->`, `--*`)
    """
    marker_id = _get_marker_def_id(type_)
    if not marker_id:
        return ""

    if marker_at == "from":
        return f' marker-start="url(#{marker_id})"'
    else:
        return f' marker-end="url(#{marker_id})"'


def _get_marker_def_id(type_: RelationshipType) -> str | None:
    """Map relationship type to its SVG marker definition ID."""
    mapping: dict[str, str] = {
        "inheritance": "cls-inherit",
        "realization": "cls-inherit",
        "composition": "cls-composition",
        "aggregation": "cls-aggregation",
        "association": "cls-arrow",
        "dependency": "cls-arrow",
    }
    return mapping.get(type_)


def _render_relationship_labels(rel: PositionedClassRelationship) -> str:
    """Render relationship labels and cardinality text."""
    if not rel.label and not rel.from_cardinality and not rel.to_cardinality:
        return ""
    if len(rel.points) < 2:
        return ""

    parts: list[str] = []

    # Label -- prefer layout-computed position (collision-aware), fall back to midpoint
    if rel.label:
        pos = rel.label_position if rel.label_position else _midpoint(rel.points)
        parts.append(
            f'<text x="{pos["x"]}" y="{pos["y"] - 8}" text-anchor="middle" '
            f'font-size="{FONT_SIZES["edge_label"]}" font-weight="{FONT_WEIGHTS["edge_label"]}" '
            f'fill="var(--_text-muted)">{_escape_xml(rel.label)}</text>'
        )

    # From cardinality (near start)
    if rel.from_cardinality:
        p = rel.points[0]
        next_p = rel.points[1]
        offset = _cardinality_offset(p, next_p)
        parts.append(
            f'<text x="{p["x"] + offset["x"]}" y="{p["y"] + offset["y"]}" text-anchor="middle" '
            f'font-size="{FONT_SIZES["edge_label"]}" font-weight="{FONT_WEIGHTS["edge_label"]}" '
            f'fill="var(--_text-muted)">{_escape_xml(rel.from_cardinality)}</text>'
        )

    # To cardinality (near end)
    if rel.to_cardinality:
        p = rel.points[-1]
        prev_p = rel.points[-2]
        offset = _cardinality_offset(p, prev_p)
        parts.append(
            f'<text x="{p["x"] + offset["x"]}" y="{p["y"] + offset["y"]}" text-anchor="middle" '
            f'font-size="{FONT_SIZES["edge_label"]}" font-weight="{FONT_WEIGHTS["edge_label"]}" '
            f'fill="var(--_text-muted)">{_escape_xml(rel.to_cardinality)}</text>'
        )

    return "\n".join(parts)


def _midpoint(points: list[dict[str, float]]) -> dict[str, float]:
    """Get the midpoint of a point array."""
    if not points:
        return {"x": 0, "y": 0}
    mid = len(points) // 2
    return points[mid]


def _cardinality_offset(
    from_: dict[str, float], to: dict[str, float]
) -> dict[str, float]:
    """Calculate offset for cardinality label perpendicular to edge direction."""
    dx = to["x"] - from_["x"]
    dy = to["y"] - from_["y"]
    # Place label perpendicular to the edge, 14px away
    if abs(dx) > abs(dy):
        # Mostly horizontal -- offset vertically
        return {"x": 14 if dx > 0 else -14, "y": -10}
    # Mostly vertical -- offset horizontally
    return {"x": -14, "y": 14 if dy > 0 else -14}


# ============================================================================
# Utilities
# ============================================================================


def _escape_xml(text: str) -> str:
    """Escape special XML characters in text content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
