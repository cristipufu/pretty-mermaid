from __future__ import annotations

from .types import (
    PositionedSequenceDiagram,
    PositionedActor,
    Lifeline,
    PositionedMessage,
    Activation,
    PositionedBlock,
    PositionedNote,
)
from ..theme import DiagramColors, svg_open_tag, build_style_block
from ..styles import (
    FONT_SIZES,
    FONT_WEIGHTS,
    STROKE_WIDTHS,
    ARROW_HEAD,
    estimate_text_width,
    TEXT_BASELINE_SHIFT,
)

# ============================================================================
# Sequence diagram SVG renderer
#
# Renders a positioned sequence diagram to SVG string.
# All colors use CSS custom properties (var(--_xxx)) from the theme system.
#
# Render order (back to front):
#   1. Block backgrounds (loop/alt/opt)
#   2. Lifelines (dashed vertical lines)
#   3. Activation boxes
#   4. Messages (arrows with labels)
#   5. Notes
#   6. Actor boxes (at top)
# ============================================================================


def render_sequence_svg(
    diagram: PositionedSequenceDiagram,
    colors: DiagramColors,
    font: str = "Inter",
    transparent: bool = False,
) -> str:
    """Render a positioned sequence diagram as an SVG string.

    Args:
        colors: DiagramColors with bg/fg and optional enrichment variables.
        transparent: If true, renders with transparent background.
    """
    parts: list[str] = []

    # SVG root with CSS variables + style block + defs
    parts.append(svg_open_tag(diagram.width, diagram.height, colors, transparent))
    parts.append(build_style_block(font, False))
    parts.append("<defs>")

    # Arrow marker definitions
    parts.append(_arrow_marker_defs())
    parts.append("</defs>")

    # 1. Block backgrounds (loop/alt/opt rectangles)
    for block in diagram.blocks:
        parts.append(_render_block(block))

    # 2. Lifelines (dashed vertical lines from actor to bottom)
    for lifeline in diagram.lifelines:
        parts.append(_render_lifeline(lifeline))

    # 3. Activation boxes
    for activation in diagram.activations:
        parts.append(_render_activation(activation))

    # 4. Messages (horizontal arrows with labels)
    for message in diagram.messages:
        parts.append(_render_message(message))

    # 5. Notes
    for note in diagram.notes:
        parts.append(_render_note(note))

    # 6. Actor boxes at top (rendered last so they're on top)
    for actor in diagram.actors:
        parts.append(_render_actor(actor))

    parts.append("</svg>")
    return "\n".join(parts)


# ============================================================================
# Arrow marker definitions
# ============================================================================


def _arrow_marker_defs() -> str:
    w = ARROW_HEAD["width"]
    h = ARROW_HEAD["height"]
    return (
        f'  <marker id="seq-arrow" markerWidth="{w}" markerHeight="{h}" '
        f'refX="{w}" refY="{h / 2}" orient="auto-start-reverse">\n'
        f'    <polygon points="0 0, {w} {h / 2}, 0 {h}" fill="var(--_arrow)" />\n'
        f"  </marker>\n"
        # Open arrow head (just lines, no fill)
        f'  <marker id="seq-arrow-open" markerWidth="{w}" markerHeight="{h}" '
        f'refX="{w}" refY="{h / 2}" orient="auto-start-reverse">\n'
        f'    <polyline points="0 0, {w} {h / 2}, 0 {h}" fill="none" '
        f'stroke="var(--_arrow)" stroke-width="1" />\n'
        f"  </marker>"
    )


# ============================================================================
# Component renderers
# ============================================================================


def _render_actor(actor: PositionedActor) -> str:
    """Render an actor box (participant = rectangle, actor = stick figure)."""
    x = actor.x
    y = actor.y
    width = actor.width
    height = actor.height
    label = actor.label
    actor_type = actor.type

    if actor_type == "actor":
        # Circle-person icon: outer circle + head circle + shoulders arc.
        # Defined in a 24x24 coordinate space, scaled to 90% of the actor box height
        # and centered both horizontally and vertically within the box.
        # Stroke width is inverse-scaled so the visual thickness matches STROKE_WIDTHS.outer_box.
        s = (height / 24) * 0.9
        tx = x - 12 * s  # center icon horizontally on actor.x
        ty = y + (height - 24 * s) / 2  # center icon vertically in actor box
        sw = STROKE_WIDTHS["outer_box"] / s  # compensate for scale transform
        icon_stroke = "var(--_line)"  # use line color for actor icon strokes

        return (
            f'<g transform="translate({tx},{ty}) scale({s})">\n'
            # Outer circle
            f'  <path d="M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12'
            f'C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" '
            f'fill="none" stroke="{icon_stroke}" stroke-width="{sw}" />\n'
            # Head
            f'  <path d="M15 10C15 11.6569 13.6569 13 12 13C10.3431 13 9 11.6569 9 10'
            f'C9 8.34315 10.3431 7 12 7C13.6569 7 15 8.34315 15 10Z" '
            f'fill="none" stroke="{icon_stroke}" stroke-width="{sw}" />\n'
            # Shoulders
            f'  <path d="M5.62842 18.3563C7.08963 17.0398 9.39997 16 12 16'
            f'C14.6 16 16.9104 17.0398 18.3716 18.3563" '
            f'fill="none" stroke="{icon_stroke}" stroke-width="{sw}" />\n'
            f"</g>\n"
            # Label below the icon
            f'<text x="{x}" y="{y + height + 14}" text-anchor="middle" '
            f'font-size="{FONT_SIZES["node_label"]}" font-weight="{FONT_WEIGHTS["node_label"]}" '
            f'fill="var(--_text)">{_escape_xml(label)}</text>'
        )

    # Participant: rectangle box with label
    box_x = x - width / 2
    return (
        f'<rect x="{box_x}" y="{y}" width="{width}" height="{height}" rx="4" ry="4" '
        f'fill="var(--_node-fill)" stroke="var(--_node-stroke)" '
        f'stroke-width="{STROKE_WIDTHS["outer_box"]}" />\n'
        f'<text x="{x}" y="{y + height / 2}" text-anchor="middle" dy="{TEXT_BASELINE_SHIFT}" '
        f'font-size="{FONT_SIZES["node_label"]}" font-weight="{FONT_WEIGHTS["node_label"]}" '
        f'fill="var(--_text)">{_escape_xml(label)}</text>'
    )


def _render_lifeline(lifeline: Lifeline) -> str:
    """Render a lifeline (dashed vertical line from actor to bottom)."""
    return (
        f'<line x1="{lifeline.x}" y1="{lifeline.top_y}" '
        f'x2="{lifeline.x}" y2="{lifeline.bottom_y}" '
        f'stroke="var(--_line)" stroke-width="0.75" stroke-dasharray="6 4" />'
    )


def _render_activation(activation: Activation) -> str:
    """Render an activation box (narrow filled rectangle on lifeline)."""
    return (
        f'<rect x="{activation.x}" y="{activation.top_y}" '
        f'width="{activation.width}" '
        f'height="{activation.bottom_y - activation.top_y}" '
        f'fill="var(--_node-fill)" stroke="var(--_node-stroke)" '
        f'stroke-width="{STROKE_WIDTHS["inner_box"]}" />'
    )


def _render_message(msg: PositionedMessage) -> str:
    """Render a message arrow with label."""
    parts: list[str] = []
    dash_array = ' stroke-dasharray="6 4"' if msg.line_style == "dashed" else ""
    marker_id = "seq-arrow" if msg.arrow_head == "filled" else "seq-arrow-open"

    if msg.is_self:
        # Self-message: curved loop going right and back
        loop_w = 30
        loop_h = 20
        parts.append(
            f'<polyline points="{msg.x1},{msg.y} {msg.x1 + loop_w},{msg.y} '
            f'{msg.x1 + loop_w},{msg.y + loop_h} {msg.x2},{msg.y + loop_h}" '
            f'fill="none" stroke="var(--_line)" '
            f'stroke-width="{STROKE_WIDTHS["connector"]}"{dash_array} '
            f'marker-end="url(#{marker_id})" />'
        )
        # Label to the right of the loop
        parts.append(
            f'<text x="{msg.x1 + loop_w + 6}" y="{msg.y + loop_h / 2}" '
            f'dy="{TEXT_BASELINE_SHIFT}" '
            f'font-size="{FONT_SIZES["edge_label"]}" '
            f'font-weight="{FONT_WEIGHTS["edge_label"]}" '
            f'fill="var(--_text-muted)">{_escape_xml(msg.label)}</text>'
        )
    else:
        # Normal message: horizontal arrow
        parts.append(
            f'<line x1="{msg.x1}" y1="{msg.y}" x2="{msg.x2}" y2="{msg.y}" '
            f'stroke="var(--_line)" '
            f'stroke-width="{STROKE_WIDTHS["connector"]}"{dash_array} '
            f'marker-end="url(#{marker_id})" />'
        )
        # Label above the arrow, centered
        mid_x = (msg.x1 + msg.x2) / 2
        parts.append(
            f'<text x="{mid_x}" y="{msg.y - 6}" text-anchor="middle" '
            f'font-size="{FONT_SIZES["edge_label"]}" '
            f'font-weight="{FONT_WEIGHTS["edge_label"]}" '
            f'fill="var(--_text-muted)">{_escape_xml(msg.label)}</text>'
        )

    return "\n".join(parts)


def _render_block(block: PositionedBlock) -> str:
    """Render a block background (loop/alt/opt)."""
    parts: list[str] = []

    # Outer rectangle
    parts.append(
        f'<rect x="{block.x}" y="{block.y}" width="{block.width}" '
        f'height="{block.height}" rx="0" ry="0" fill="none" '
        f'stroke="var(--_node-stroke)" stroke-width="{STROKE_WIDTHS["outer_box"]}" />'
    )

    # Type label tab (top-left corner)
    label_text = f"{block.type} [{block.label}]" if block.label else block.type
    tab_width = (
        estimate_text_width(
            label_text, FONT_SIZES["edge_label"], FONT_WEIGHTS["group_header"]
        )
        + 16
    )
    tab_height = 18

    parts.append(
        f'<rect x="{block.x}" y="{block.y}" width="{tab_width}" '
        f'height="{tab_height}" fill="var(--_group-hdr)" '
        f'stroke="var(--_node-stroke)" stroke-width="{STROKE_WIDTHS["outer_box"]}" />'
    )
    parts.append(
        f'<text x="{block.x + 6}" y="{block.y + tab_height / 2}" '
        f'dy="{TEXT_BASELINE_SHIFT}" '
        f'font-size="{FONT_SIZES["edge_label"]}" '
        f'font-weight="{FONT_WEIGHTS["group_header"]}" '
        f'fill="var(--_text-sec)">{_escape_xml(label_text)}</text>'
    )

    # Divider lines (for alt/else, par/and)
    for divider in block.dividers:
        parts.append(
            f'<line x1="{block.x}" y1="{divider.y}" '
            f'x2="{block.x + block.width}" y2="{divider.y}" '
            f'stroke="var(--_line)" stroke-width="0.75" stroke-dasharray="6 4" />'
        )
        if divider.label:
            parts.append(
                f'<text x="{block.x + 8}" y="{divider.y + 14}" '
                f'font-size="{FONT_SIZES["edge_label"]}" '
                f'font-weight="{FONT_WEIGHTS["edge_label"]}" '
                f'fill="var(--_text-muted)">[{_escape_xml(divider.label)}]</text>'
            )

    return "\n".join(parts)


def _render_note(note: PositionedNote) -> str:
    """Render a note box."""
    # Folded corner effect: note rectangle + small triangle in top-right
    fold_size = 6
    return (
        f'<rect x="{note.x}" y="{note.y}" width="{note.width}" '
        f'height="{note.height}" fill="var(--_group-hdr)" '
        f'stroke="var(--_node-stroke)" stroke-width="{STROKE_WIDTHS["inner_box"]}" />\n'
        # Fold triangle
        f'<polygon points="{note.x + note.width - fold_size},{note.y} '
        f'{note.x + note.width},{note.y + fold_size} '
        f'{note.x + note.width - fold_size},{note.y + fold_size}" '
        f'fill="var(--_inner-stroke)" />\n'
        # Note text
        f'<text x="{note.x + note.width / 2}" y="{note.y + note.height / 2}" '
        f'text-anchor="middle" dy="{TEXT_BASELINE_SHIFT}" '
        f'font-size="{FONT_SIZES["edge_label"]}" '
        f'font-weight="{FONT_WEIGHTS["edge_label"]}" '
        f'fill="var(--_text-muted)">{_escape_xml(note.text)}</text>'
    )


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
