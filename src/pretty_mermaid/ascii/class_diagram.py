from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..class_diagram.parser import parse_class_diagram
from ..class_diagram.types import (
    ClassDiagram,
    ClassNode,
    ClassMember,
    ClassRelationship,
    RelationshipType,
)
from .types import AsciiConfig, Canvas
from .canvas import mk_canvas, canvas_to_string, increase_size
from .draw import draw_multi_box

# ============================================================================
# ASCII renderer -- class diagrams
#
# Renders classDiagram text to ASCII/Unicode art.
# Each class is a multi-compartment box (header | attributes | methods).
# Relationships are drawn as lines between classes with UML markers.
#
# Layout: level-based top-down.  "From" classes are placed above "to" classes
# for all relationship types, matching dagre/mermaid.com behavior.
# Relationship lines use simple Manhattan routing (vertical + horizontal).
# ============================================================================

# ============================================================================
# Class member formatting
# ============================================================================


def _format_member(m: ClassMember) -> str:
    """Format a class member as a display string: visibility + name + optional type."""
    vis = m.visibility or ""
    type_suffix = f": {m.type}" if m.type else ""
    return f"{vis}{m.name}{type_suffix}"


def _build_class_sections(cls: ClassNode) -> list[list[str]]:
    """Build the text sections for a class box: [header], [attributes], [methods]."""
    # Header section: optional annotation + class name
    header: list[str] = []
    if cls.annotation:
        header.append(f"<<{cls.annotation}>>")
    header.append(cls.label)

    # Attributes section
    attrs = [_format_member(a) for a in cls.attributes]

    # Methods section
    methods = [_format_member(m) for m in cls.methods]

    # If no attrs and no methods, just return header (1-section box)
    if len(attrs) == 0 and len(methods) == 0:
        return [header]
    # If no methods, return header + attrs (2-section box)
    if len(methods) == 0:
        return [header, attrs]
    # Full 3-section box
    return [header, attrs, methods]


# ============================================================================
# Relationship marker characters
# ============================================================================


@dataclass(slots=True)
class _RelMarker:
    """Relationship marker metadata."""

    type: RelationshipType
    marker_at: Literal["from", "to"]
    dashed: bool


def _get_rel_marker(
    rel_type: RelationshipType, marker_at: Literal["from", "to"]
) -> _RelMarker:
    """Build the marker metadata for a relationship."""
    dashed = rel_type in ("dependency", "realization")
    return _RelMarker(type=rel_type, marker_at=marker_at, dashed=dashed)


def _get_marker_shape(
    rel_type: RelationshipType,
    use_ascii: bool,
    direction: str | None = None,
) -> str:
    """Get the UML marker shape character for a relationship type.

    For directional arrows (association/dependency), the direction parameter
    specifies which way the arrow should point.
    """
    if rel_type in ("inheritance", "realization"):
        # Hollow triangle -- rotate based on line direction
        if direction == "down":
            return "^" if use_ascii else "\u25b3"  # △
        elif direction == "up":
            return "v" if use_ascii else "\u25bd"  # ▽
        elif direction == "left":
            return ">" if use_ascii else "\u25c1"  # ◁
        else:
            return "<" if use_ascii else "\u25b7"  # ▷

    elif rel_type == "composition":
        # Filled diamond -- omnidirectional shape
        return "*" if use_ascii else "\u25c6"  # ◆

    elif rel_type == "aggregation":
        # Hollow diamond -- omnidirectional shape
        return "o" if use_ascii else "\u25c7"  # ◇

    else:
        # association, dependency -- directional arrow
        if direction == "down":
            return "v" if use_ascii else "\u25bc"  # ▼
        elif direction == "up":
            return "^" if use_ascii else "\u25b2"  # ▲
        elif direction == "left":
            return "<" if use_ascii else "\u25c0"  # ◀
        else:
            return ">" if use_ascii else "\u25b6"  # ▶


# ============================================================================
# Layout and rendering
# ============================================================================


@dataclass(slots=True)
class _PlacedClass:
    """Positioned class node on the canvas."""

    cls: ClassNode
    sections: list[list[str]]
    x: int
    y: int
    width: int
    height: int


def render_class_ascii(lines: list[str], config: AsciiConfig) -> str:
    """Render a Mermaid class diagram to ASCII/Unicode text.

    Pipeline: parse -> build boxes -> level-based layout -> draw boxes
              -> draw relationships -> string.
    """
    diagram = parse_class_diagram(lines)

    if len(diagram.classes) == 0:
        return ""

    use_ascii = config.use_ascii
    h_gap = 4  # horizontal gap between class boxes
    v_gap = 3  # vertical gap between levels (enough for relationship lines)

    # --- Build box dimensions for each class ---
    class_sections: dict[str, list[list[str]]] = {}
    class_box_w: dict[str, int] = {}
    class_box_h: dict[str, int] = {}

    for cls in diagram.classes:
        sections = _build_class_sections(cls)
        class_sections[cls.id] = sections

        # Compute box dimensions from draw_multi_box logic
        max_text_w = 0
        for section in sections:
            for line in section:
                max_text_w = max(max_text_w, len(line))
        box_w = max_text_w + 4  # 2 border + 2 padding

        total_lines = 0
        for section in sections:
            total_lines += max(len(section), 1)
        box_h = total_lines + (len(sections) - 1) + 2  # section lines + dividers + top/bottom

        class_box_w[cls.id] = box_w
        class_box_h[cls.id] = box_h

    # --- Assign levels: topological sort based on directed relationships ---
    class_by_id: dict[str, ClassNode] = {}
    for cls in diagram.classes:
        class_by_id[cls.id] = cls

    parents: dict[str, set[str]] = {}   # child -> set of parent IDs
    children: dict[str, set[str]] = {}  # parent -> set of child IDs

    for rel in diagram.relationships:
        is_hierarchical = rel.type in ("inheritance", "realization")
        parent_id = rel.to if is_hierarchical and rel.marker_at == "to" else rel.from_
        child_id = rel.from_ if is_hierarchical and rel.marker_at == "to" else rel.to

        if child_id not in parents:
            parents[child_id] = set()
        parents[child_id].add(parent_id)
        if parent_id not in children:
            children[parent_id] = set()
        children[parent_id].add(child_id)

    # BFS from roots (classes that have no parents) to assign levels.
    level: dict[str, int] = {}
    roots = [c for c in diagram.classes if c.id not in parents or len(parents[c.id]) == 0]
    queue: list[str] = [c.id for c in roots]
    for id_ in queue:
        level[id_] = 0

    level_cap = len(diagram.classes) - 1
    qi = 0
    while qi < len(queue):
        id_ = queue[qi]
        qi += 1
        child_set = children.get(id_)
        if child_set is None:
            continue
        for child_id in child_set:
            new_level = level.get(id_, 0) + 1
            if new_level > level_cap:
                continue  # cycle detected -- skip to prevent infinite loop
            if child_id not in level or level[child_id] < new_level:
                level[child_id] = new_level
                queue.append(child_id)

    # Assign remaining (unconnected) classes to level 0
    for cls in diagram.classes:
        if cls.id not in level:
            level[cls.id] = 0

    # --- Position classes by level ---
    max_level = max(level.values()) if level else 0
    level_groups: list[list[str]] = [[] for _ in range(max_level + 1)]
    for cls in diagram.classes:
        level_groups[level[cls.id]].append(cls.id)

    # Compute positions: each level is a row, classes in a row are spaced horizontally
    placed: dict[str, _PlacedClass] = {}
    current_y = 0

    for lv in range(max_level + 1):
        group = level_groups[lv]
        if len(group) == 0:
            continue

        current_x = 0
        max_h = 0

        for id_ in group:
            cls = class_by_id[id_]
            w = class_box_w[id_]
            h = class_box_h[id_]
            placed[id_] = _PlacedClass(
                cls=cls,
                sections=class_sections[id_],
                x=current_x,
                y=current_y,
                width=w,
                height=h,
            )
            current_x += w + h_gap
            max_h = max(max_h, h)

        current_y += max_h + v_gap

    # --- Create canvas ---
    total_w = 0
    total_h = 0
    for p in placed.values():
        total_w = max(total_w, p.x + p.width)
        total_h = max(total_h, p.y + p.height)

    # Extra space for relationship lines that may go below/beside
    total_w += 4
    total_h += 2

    canvas = mk_canvas(total_w - 1, total_h - 1)

    # --- Draw class boxes ---
    for p in placed.values():
        box_canvas = draw_multi_box(p.sections, use_ascii)
        # Copy box onto main canvas at (p.x, p.y)
        for bx in range(len(box_canvas)):
            for by in range(len(box_canvas[0])):
                ch = box_canvas[bx][by]
                if ch != " ":
                    cx = p.x + bx
                    cy = p.y + by
                    if cx < total_w and cy < total_h:
                        canvas[cx][cy] = ch

    # --- Draw relationship lines ---
    H = "-" if use_ascii else "\u2500"   # ─
    V = "|" if use_ascii else "\u2502"   # │
    dash_h = "." if use_ascii else "\u254c"  # ╌
    dash_v = ":" if use_ascii else "\u250a"  # ┊

    for rel in diagram.relationships:
        from_p = placed.get(rel.from_)
        to_p = placed.get(rel.to)
        if from_p is None or to_p is None:
            continue

        marker = _get_rel_marker(rel.type, rel.marker_at)
        line_h = dash_h if marker.dashed else H
        line_v = dash_v if marker.dashed else V

        # Connection points: center-bottom of source -> center-top of target
        from_cx = from_p.x + from_p.width // 2
        from_by = from_p.y + from_p.height - 1
        to_cx = to_p.x + to_p.width // 2
        to_ty = to_p.y

        if from_by < to_ty:
            # Target is below source -- simple vertical-first routing
            mid_y = from_by + (to_ty - from_by) // 2

            # Vertical from source bottom to mid_y
            for y in range(from_by + 1, mid_y + 1):
                if y < total_h:
                    canvas[from_cx][y] = line_v

            # Horizontal from from_cx to to_cx at mid_y
            if from_cx != to_cx:
                lx = min(from_cx, to_cx)
                rx = max(from_cx, to_cx)
                for x in range(lx, rx + 1):
                    if x < total_w and mid_y < total_h:
                        canvas[x][mid_y] = line_h
                # Corner characters
                if not use_ascii and mid_y < total_h:
                    if from_cx < to_cx:
                        canvas[from_cx][mid_y] = "\u2514"  # └
                        canvas[to_cx][mid_y] = "\u2510"    # ┐
                    else:
                        canvas[from_cx][mid_y] = "\u2518"  # ┘
                        canvas[to_cx][mid_y] = "\u250c"    # ┌

            # Vertical from mid_y to target top
            for y in range(mid_y + 1, to_ty):
                if y < total_h:
                    canvas[to_cx][y] = line_v

            # Draw markers
            if marker.marker_at == "to":
                marker_char = _get_marker_shape(marker.type, use_ascii, "down")
                my = to_ty - 1
                if 0 <= my < total_h:
                    for i, ch in enumerate(marker_char):
                        mx = to_cx - len(marker_char) // 2 + i
                        if 0 <= mx < total_w:
                            canvas[mx][my] = ch
            if marker.marker_at == "from":
                marker_char = _get_marker_shape(marker.type, use_ascii, "down")
                my = from_by + 1
                if my < total_h:
                    for i, ch in enumerate(marker_char):
                        mx = from_cx - len(marker_char) // 2 + i
                        if 0 <= mx < total_w:
                            canvas[mx][my] = ch

        elif to_p.y + to_p.height - 1 < from_p.y:
            # Target is ABOVE source -- draw upward from source top to target bottom
            from_ty = from_p.y
            to_by = to_p.y + to_p.height - 1
            mid_y = to_by + (from_ty - to_by) // 2

            for y in range(from_ty - 1, mid_y - 1, -1):
                if 0 <= y < total_h:
                    canvas[from_cx][y] = line_v

            if from_cx != to_cx:
                lx = min(from_cx, to_cx)
                rx = max(from_cx, to_cx)
                for x in range(lx, rx + 1):
                    if x < total_w and 0 <= mid_y < total_h:
                        canvas[x][mid_y] = line_h
                if not use_ascii and 0 <= mid_y < total_h:
                    if from_cx < to_cx:
                        canvas[from_cx][mid_y] = "\u250c"  # ┌
                        canvas[to_cx][mid_y] = "\u2518"    # ┘
                    else:
                        canvas[from_cx][mid_y] = "\u2510"  # ┐
                        canvas[to_cx][mid_y] = "\u2514"    # └

            for y in range(mid_y - 1, to_by, -1):
                if 0 <= y < total_h:
                    canvas[to_cx][y] = line_v

            # Draw markers -- arrows point in the direction of the vertical segment (upward)
            if marker.marker_at == "from":
                marker_char = _get_marker_shape(marker.type, use_ascii, "up")
                my = from_ty - 1
                if 0 <= my < total_h:
                    for i, ch in enumerate(marker_char):
                        mx = from_cx - len(marker_char) // 2 + i
                        if 0 <= mx < total_w:
                            canvas[mx][my] = ch
            if marker.marker_at == "to":
                is_hierarchical = marker.type in ("inheritance", "realization")
                marker_dir = "down" if is_hierarchical else "up"
                marker_char = _get_marker_shape(marker.type, use_ascii, marker_dir)
                my = to_by + 1
                if my < total_h:
                    for i, ch in enumerate(marker_char):
                        mx = to_cx - len(marker_char) // 2 + i
                        if 0 <= mx < total_w:
                            canvas[mx][my] = ch

        else:
            # Same level -- draw horizontal line with a detour below both boxes
            detour_y = max(from_by, to_p.y + to_p.height - 1) + 2
            increase_size(canvas, total_w, detour_y + 1)

            # Vertical down from source
            for y in range(from_by + 1, detour_y + 1):
                canvas[from_cx][y] = line_v
            # Horizontal
            lx = min(from_cx, to_cx)
            rx = max(from_cx, to_cx)
            for x in range(lx, rx + 1):
                canvas[x][detour_y] = line_h
            # Vertical up to target
            for y in range(detour_y - 1, to_p.y + to_p.height - 1, -1):
                canvas[to_cx][y] = line_v

            # Draw markers -- same-level routing uses vertical segments at both ends
            if marker.marker_at == "from":
                marker_char = _get_marker_shape(marker.type, use_ascii, "down")
                my = from_by + 1
                if my < total_h:
                    for i, ch in enumerate(marker_char):
                        mx = from_cx - len(marker_char) // 2 + i
                        if 0 <= mx < total_w:
                            canvas[mx][my] = ch
            if marker.marker_at == "to":
                marker_char = _get_marker_shape(marker.type, use_ascii, "up")
                my = to_p.y + to_p.height
                if my < total_h:
                    for i, ch in enumerate(marker_char):
                        mx = to_cx - len(marker_char) // 2 + i
                        if 0 <= mx < total_w:
                            canvas[mx][my] = ch

        # Draw relationship label at midpoint if present
        if rel.label:
            padded_label = f" {rel.label} "
            mid_x = (from_cx + to_cx) // 2
            # Calculate mid_y based on routing direction
            if from_by < to_ty:
                label_mid_y = (from_by + 1 + to_ty - 1) // 2
            elif to_p.y + to_p.height - 1 < from_p.y:
                to_by_val = to_p.y + to_p.height - 1
                label_mid_y = (to_by_val + 1 + from_p.y - 1) // 2
            else:
                label_mid_y = max(from_by, to_p.y + to_p.height - 1) + 2
            label_start = mid_x - len(padded_label) // 2
            for i, ch in enumerate(padded_label):
                lx = label_start + i
                if 0 <= lx < total_w and 0 <= label_mid_y < total_h:
                    canvas[lx][label_mid_y] = ch

    return canvas_to_string(canvas)
