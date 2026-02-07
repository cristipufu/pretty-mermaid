from __future__ import annotations

import math
from dataclasses import dataclass

from ..er.parser import parse_er_diagram
from ..er.types import ErDiagram, ErEntity, ErAttribute, Cardinality
from .types import AsciiConfig, Canvas
from .canvas import mk_canvas, canvas_to_string, increase_size
from .draw import draw_multi_box

# ============================================================================
# ASCII renderer -- ER diagrams
#
# Renders erDiagram text to ASCII/Unicode art.
# Each entity is a 2-section box (header | attributes).
# Relationships are drawn as lines with crow's foot notation at endpoints.
#
# Layout: entities are placed in a grid pattern (multiple rows if needed).
# Relationship lines use Manhattan routing between entity boxes.
# ============================================================================

# ============================================================================
# Entity box content
# ============================================================================


def _format_attribute(attr: ErAttribute) -> str:
    """Format an attribute line: 'PK type name' or 'FK type name' etc."""
    key_str = ",".join(attr.keys) + " " if len(attr.keys) > 0 else "   "
    return f"{key_str}{attr.type} {attr.name}"


def _build_entity_sections(entity: ErEntity) -> list[list[str]]:
    """Build sections for an entity box: [header], [attributes]."""
    header = [entity.label]
    attrs = [_format_attribute(a) for a in entity.attributes]
    if len(attrs) == 0:
        return [header]
    return [header, attrs]


# ============================================================================
# Crow's foot notation
# ============================================================================


def _get_crows_foot_chars(card: Cardinality, use_ascii: bool) -> str:
    """Return the ASCII/Unicode characters for a crow's foot cardinality marker.

    These are drawn near the endpoint of a relationship line.

    Cardinality markers (horizontal direction):
      one:       --||--   or  ──║──
      zero-one:  --o|--   or  ──o║──
      many:      --<|--   or  ──╟──
      zero-many: --o<--   or  ──o╟──
    """
    if use_ascii:
        if card == "one":
            return "||"
        elif card == "zero-one":
            return "o|"
        elif card == "many":
            return "}|"
        else:  # zero-many
            return "o{"
    else:
        if card == "one":
            return "\u2551"      # ║
        elif card == "zero-one":
            return "o\u2551"     # o║
        elif card == "many":
            return "\u255f"      # ╟
        else:  # zero-many
            return "o\u255f"     # o╟


# ============================================================================
# Positioned entity
# ============================================================================


@dataclass(slots=True)
class _PlacedEntity:
    entity: ErEntity
    sections: list[list[str]]
    x: int
    y: int
    width: int
    height: int


# ============================================================================
# Layout and rendering
# ============================================================================


def render_er_ascii(lines: list[str], config: AsciiConfig) -> str:
    """Render a Mermaid ER diagram to ASCII/Unicode text.

    Pipeline: parse -> build boxes -> grid layout -> draw boxes
              -> draw relationships -> string.
    """
    diagram = parse_er_diagram(lines)

    if len(diagram.entities) == 0:
        return ""

    use_ascii = config.use_ascii
    h_gap = 6  # horizontal gap between entity boxes
    v_gap = 4  # vertical gap between rows (for relationship lines)

    # --- Build entity box dimensions ---
    entity_sections: dict[str, list[list[str]]] = {}
    entity_box_w: dict[str, int] = {}
    entity_box_h: dict[str, int] = {}

    for ent in diagram.entities:
        sections = _build_entity_sections(ent)
        entity_sections[ent.id] = sections

        max_text_w = 0
        for section in sections:
            for line in section:
                max_text_w = max(max_text_w, len(line))
        box_w = max_text_w + 4  # 2 border + 2 padding

        total_lines = 0
        for section in sections:
            total_lines += max(len(section), 1)
        box_h = total_lines + (len(sections) - 1) + 2

        entity_box_w[ent.id] = box_w
        entity_box_h[ent.id] = box_h

    # --- Layout: place entities in rows ---
    # Use a simple grid: max N entities per row (based on count).
    max_per_row = max(2, math.ceil(math.sqrt(len(diagram.entities))))

    placed: dict[str, _PlacedEntity] = {}
    current_x = 0
    current_y = 0
    max_row_h = 0
    col_count = 0

    for ent in diagram.entities:
        w = entity_box_w[ent.id]
        h = entity_box_h[ent.id]

        if col_count >= max_per_row:
            # Wrap to next row
            current_y += max_row_h + v_gap
            current_x = 0
            max_row_h = 0
            col_count = 0

        placed[ent.id] = _PlacedEntity(
            entity=ent,
            sections=entity_sections[ent.id],
            x=current_x,
            y=current_y,
            width=w,
            height=h,
        )

        current_x += w + h_gap
        max_row_h = max(max_row_h, h)
        col_count += 1

    # --- Create canvas ---
    total_w = 0
    total_h = 0
    for p in placed.values():
        total_w = max(total_w, p.x + p.width)
        total_h = max(total_h, p.y + p.height)
    total_w += 4
    total_h += 2

    canvas = mk_canvas(total_w - 1, total_h - 1)

    # --- Draw entity boxes ---
    for p in placed.values():
        box_canvas = draw_multi_box(p.sections, use_ascii)
        for bx in range(len(box_canvas)):
            for by in range(len(box_canvas[0])):
                ch = box_canvas[bx][by]
                if ch != " ":
                    cx = p.x + bx
                    cy = p.y + by
                    if cx < total_w and cy < total_h:
                        canvas[cx][cy] = ch

    # --- Draw relationships ---
    H = "-" if use_ascii else "\u2500"   # ─
    V = "|" if use_ascii else "\u2502"   # │
    dash_h = "." if use_ascii else "\u254c"  # ╌
    dash_v = ":" if use_ascii else "\u250a"  # ┊

    for rel in diagram.relationships:
        e1 = placed.get(rel.entity1)
        e2 = placed.get(rel.entity2)
        if e1 is None or e2 is None:
            continue

        line_h = H if rel.identifying else dash_h
        line_v = V if rel.identifying else dash_v

        # Determine connection direction based on relative position.
        e1_cx = e1.x + e1.width // 2
        e1_cy = e1.y + e1.height // 2
        e2_cx = e2.x + e2.width // 2
        e2_cy = e2.y + e2.height // 2

        # Check if entities are on the same row (horizontal connection)
        same_row = abs(e1_cy - e2_cy) < max(e1.height, e2.height)

        if same_row:
            # Horizontal connection: right side of left entity -> left side of right entity
            if e1_cx < e2_cx:
                left, right = e1, e2
                left_card, right_card = rel.cardinality1, rel.cardinality2
            else:
                left, right = e2, e1
                left_card, right_card = rel.cardinality2, rel.cardinality1

            start_x = left.x + left.width
            end_x = right.x - 1
            line_y = left.y + left.height // 2

            # Draw horizontal line
            for x in range(start_x, end_x + 1):
                if x < total_w:
                    canvas[x][line_y] = line_h

            # Draw crow's foot markers at endpoints
            left_chars = _get_crows_foot_chars(left_card, use_ascii)
            for i, ch in enumerate(left_chars):
                mx = start_x + i
                if mx < total_w:
                    canvas[mx][line_y] = ch

            right_chars = _get_crows_foot_chars(right_card, use_ascii)
            for i, ch in enumerate(right_chars):
                mx = end_x - len(right_chars) + 1 + i
                if 0 <= mx < total_w:
                    canvas[mx][line_y] = ch

            # Relationship label centered in the gap between the two entities, above the line.
            if rel.label:
                gap_mid = (start_x + end_x) // 2
                label_start = max(start_x, gap_mid - len(rel.label) // 2)
                label_y = line_y - 1
                if label_y >= 0:
                    for i, ch in enumerate(rel.label):
                        lx = label_start + i
                        if start_x <= lx <= end_x and lx < total_w:
                            canvas[lx][label_y] = ch
        else:
            # Vertical connection: bottom of upper entity -> top of lower entity
            if e1_cy < e2_cy:
                upper, lower = e1, e2
                upper_card, lower_card = rel.cardinality1, rel.cardinality2
            else:
                upper, lower = e2, e1
                upper_card, lower_card = rel.cardinality2, rel.cardinality1

            start_y = upper.y + upper.height
            end_y = lower.y - 1
            line_x = upper.x + upper.width // 2

            # Vertical line
            for y in range(start_y, end_y + 1):
                if y < total_h:
                    canvas[line_x][y] = line_v

            # If horizontal offset needed, add a horizontal segment
            lower_cx = lower.x + lower.width // 2
            if line_x != lower_cx:
                mid_y = (start_y + end_y) // 2
                # Horizontal segment at mid_y
                lx = min(line_x, lower_cx)
                rx = max(line_x, lower_cx)
                for x in range(lx, rx + 1):
                    if x < total_w and mid_y < total_h:
                        canvas[x][mid_y] = line_h
                # Vertical from mid_y to lower entity
                for y in range(mid_y + 1, end_y + 1):
                    if y < total_h:
                        canvas[lower_cx][y] = line_v

            # Crow's foot markers (vertical direction)
            upper_chars = _get_crows_foot_chars(upper_card, use_ascii)
            if start_y < total_h:
                for i, ch in enumerate(upper_chars):
                    mx = line_x - len(upper_chars) // 2 + i
                    if 0 <= mx < total_w:
                        canvas[mx][start_y] = ch

            target_x = lower_cx if line_x != lower_cx else line_x
            lower_chars = _get_crows_foot_chars(lower_card, use_ascii)
            if 0 <= end_y < total_h:
                for i, ch in enumerate(lower_chars):
                    mx = target_x - len(lower_chars) // 2 + i
                    if 0 <= mx < total_w:
                        canvas[mx][end_y] = ch

            # Relationship label -- placed to the right of the vertical line at midpoint.
            if rel.label:
                mid_y = (start_y + end_y) // 2
                label_x = line_x + 2
                if mid_y >= 0:
                    for i, ch in enumerate(rel.label):
                        lx = label_x + i
                        if lx >= 0:
                            increase_size(canvas, lx + 1, mid_y + 1)
                            canvas[lx][mid_y] = ch

    return canvas_to_string(canvas)
