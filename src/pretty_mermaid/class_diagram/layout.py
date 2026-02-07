from __future__ import annotations

from grandalf.graphs import Vertex, Edge, Graph
from grandalf.layouts import SugiyamaLayout

from .types import (
    ClassDiagram,
    ClassNode,
    ClassMember,
    PositionedClassDiagram,
    PositionedClassNode,
    PositionedClassRelationship,
)
from ..types import RenderOptions
from ..styles import (
    estimate_text_width,
    estimate_mono_text_width,
    FONT_SIZES,
    FONT_WEIGHTS,
)

# ============================================================================
# Class diagram layout engine
#
# Uses grandalf (Sugiyama algorithm) for positioning class boxes, then sizes
# each box based on the number of attributes and methods it contains.
#
# Each class box has 3 compartments:
#   1. Header (class name + optional annotation)
#   2. Attributes section
#   3. Methods section
# ============================================================================

# Layout constants for class diagrams
CLS = {
    # Padding around the diagram
    "padding": 40,
    # Horizontal padding inside class boxes -- used by both layout and renderer
    "box_pad_x": 8,
    # Header height (class name + annotation)
    "header_base_height": 32,
    # Extra height when annotation is present
    "annotation_height": 16,
    # Height per member row (attribute or method)
    "member_row_height": 20,
    # Vertical padding around member sections (4px top + 4px bottom)
    "section_pad_y": 8,
    # Minimum empty section height (when no attrs or no methods)
    "empty_section_height": 8,
    # Minimum box width
    "min_width": 120,
    # Font size for member text
    "member_font_size": 11,
    # Font weight for member text
    "member_font_weight": 400,
    # Spacing between class nodes
    "node_spacing": 40,
    # Spacing between layers
    "layer_spacing": 60,
}


class _VertexView:
    """Minimal view object required by grandalf's SugiyamaLayout."""

    def __init__(self, w: float = 60, h: float = 36) -> None:
        self.w = w
        self.h = h
        # xy is set by the layout engine (center coordinates)
        self.xy = (0.0, 0.0)


def layout_class_diagram(
    diagram: ClassDiagram,
    options: RenderOptions | None = None,
) -> PositionedClassDiagram:
    """Lay out a parsed class diagram using grandalf (Sugiyama algorithm).

    Returns positioned class nodes and relationship paths.
    """
    if len(diagram.classes) == 0:
        return PositionedClassDiagram(width=0, height=0)

    # 1. Calculate box dimensions for each class
    class_sizes: dict[str, dict[str, float]] = {}

    for cls in diagram.classes:
        header_height = (
            CLS["header_base_height"] + CLS["annotation_height"]
            if cls.annotation
            else CLS["header_base_height"]
        )

        attr_height = (
            len(cls.attributes) * CLS["member_row_height"] + CLS["section_pad_y"]
            if len(cls.attributes) > 0
            else CLS["empty_section_height"]
        )

        method_height = (
            len(cls.methods) * CLS["member_row_height"] + CLS["section_pad_y"]
            if len(cls.methods) > 0
            else CLS["empty_section_height"]
        )

        # Width: max of header text, widest attribute, widest method
        header_text_w = estimate_text_width(
            cls.label, FONT_SIZES["node_label"], FONT_WEIGHTS["node_label"]
        )
        max_attr_w = _max_member_width(cls.attributes)
        max_method_w = _max_member_width(cls.methods)
        width = max(
            CLS["min_width"],
            header_text_w + CLS["box_pad_x"] * 2,
            max_attr_w + CLS["box_pad_x"] * 2,
            max_method_w + CLS["box_pad_x"] * 2,
        )

        height = header_height + attr_height + method_height

        class_sizes[cls.id] = {
            "width": width,
            "height": height,
            "header_height": header_height,
            "attr_height": attr_height,
            "method_height": method_height,
        }

    # 2. Build grandalf graph
    vertices: dict[str, Vertex] = {}
    for cls in diagram.classes:
        size = class_sizes[cls.id]
        v = Vertex(cls.id)
        v.view = _VertexView(size["width"], size["height"])
        vertices[cls.id] = v

    # Build edges
    edges_list: list[Edge] = []
    edge_index_map: dict[int, int] = {}  # grandalf edge index -> original relationship index

    for i, rel in enumerate(diagram.relationships):
        src_v = vertices.get(rel.from_)
        tgt_v = vertices.get(rel.to)
        if not src_v or not tgt_v:
            continue
        e = Edge(src_v, tgt_v)
        edge_index_map[len(edges_list)] = i
        edges_list.append(e)

    # 3. Run grandalf Sugiyama layout
    all_vertices = list(vertices.values())
    g = Graph(all_vertices, edges_list)

    try:
        sug = SugiyamaLayout(g.C[0] if g.C else g)
        sug.xspace = CLS["node_spacing"]
        sug.yspace = CLS["layer_spacing"]

        # Initialize views for any vertices that don't have one
        for v in all_vertices:
            if not hasattr(v, "view") or v.view is None:
                v.view = _VertexView()

        sug.init_all()
        sug.draw()
    except Exception as err:
        raise RuntimeError(f"Grandalf layout failed (class diagram): {err}") from err

    # 4. Extract positioned classes
    class_lookup: dict[str, ClassNode] = {}
    for cls in diagram.classes:
        class_lookup[cls.id] = cls

    positioned_classes: list[PositionedClassNode] = []
    for cls in diagram.classes:
        v = vertices[cls.id]
        size = class_sizes[cls.id]
        vw = v.view
        cx, cy = vw.xy[0], vw.xy[1]
        # Convert center to top-left
        tl_x = cx - vw.w / 2
        tl_y = cy - vw.h / 2

        positioned_classes.append(
            PositionedClassNode(
                id=cls.id,
                label=cls.label,
                annotation=cls.annotation,
                attributes=cls.attributes,
                methods=cls.methods,
                x=tl_x,
                y=tl_y,
                width=vw.w,
                height=vw.h,
                header_height=size["header_height"],
                attr_height=size["attr_height"],
                method_height=size["method_height"],
            )
        )

    # 5. Extract relationship paths
    # Build a node center lookup for path computation
    node_centers: dict[str, tuple[float, float, float, float]] = {}
    for pcls in positioned_classes:
        node_centers[pcls.id] = (
            pcls.x + pcls.width / 2,
            pcls.y + pcls.height / 2,
            pcls.width,
            pcls.height,
        )

    relationships: list[PositionedClassRelationship] = []
    for ei, e in enumerate(edges_list):
        orig_idx = edge_index_map.get(ei)
        if orig_idx is None:
            continue
        rel = diagram.relationships[orig_idx]

        src_v = e.v[0]
        tgt_v = e.v[1]
        src_cx, src_cy = src_v.view.xy[0], src_v.view.xy[1]
        tgt_cx, tgt_cy = tgt_v.view.xy[0], tgt_v.view.xy[1]

        # Build simple two-point path with orthogonal snapping
        raw_points = [
            {"x": src_cx, "y": src_cy},
            {"x": tgt_cx, "y": tgt_cy},
        ]

        # Snap to orthogonal (vertical-first for TB layout)
        points = _snap_to_orthogonal(raw_points, vertical_first=True)

        # Clip endpoints to node boundaries
        src_info = node_centers.get(rel.from_)
        tgt_info = node_centers.get(rel.to)
        points = _clip_endpoints_to_nodes(points, src_info, tgt_info)

        # Compute label position at midpoint
        label_position: dict[str, float] | None = None
        if rel.label and len(points) >= 2:
            mid_idx = len(points) // 2
            label_position = {"x": points[mid_idx]["x"], "y": points[mid_idx]["y"]}

        relationships.append(
            PositionedClassRelationship(
                from_=rel.from_,
                to=rel.to,
                type=rel.type,
                marker_at=rel.marker_at,
                label=rel.label,
                from_cardinality=rel.from_cardinality,
                to_cardinality=rel.to_cardinality,
                points=points,
                label_position=label_position,
            )
        )

    # 6. Normalize coordinates and compute diagram dimensions
    padding = CLS["padding"]
    all_xs: list[float] = []
    all_ys: list[float] = []
    for pcls in positioned_classes:
        all_xs.extend([pcls.x, pcls.x + pcls.width])
        all_ys.extend([pcls.y, pcls.y + pcls.height])
    for r in relationships:
        for p in r.points:
            all_xs.append(p["x"])
            all_ys.append(p["y"])

    if all_xs and all_ys:
        min_x = min(all_xs)
        min_y = min(all_ys)
        # Shift so minimum is at padding
        if min_x < padding:
            dx = padding - min_x
            for pcls in positioned_classes:
                pcls.x += dx
            for r in relationships:
                for p in r.points:
                    p["x"] += dx
                if r.label_position:
                    r.label_position["x"] += dx
        if min_y < padding:
            dy = padding - min_y
            for pcls in positioned_classes:
                pcls.y += dy
            for r in relationships:
                for p in r.points:
                    p["y"] += dy
                if r.label_position:
                    r.label_position["y"] += dy

    # Compute final dimensions
    max_x = max(
        [pcls.x + pcls.width for pcls in positioned_classes]
        + [p["x"] for r in relationships for p in r.points]
        + [0],
    )
    max_y = max(
        [pcls.y + pcls.height for pcls in positioned_classes]
        + [p["y"] for r in relationships for p in r.points]
        + [0],
    )

    graph_width = max_x + padding
    graph_height = max_y + padding

    return PositionedClassDiagram(
        width=graph_width,
        height=graph_height,
        classes=positioned_classes,
        relationships=relationships,
    )


def _max_member_width(members: list[ClassMember]) -> float:
    """Calculate the max width of a list of class members (uses mono metrics)."""
    if len(members) == 0:
        return 0
    max_w = 0.0
    for m in members:
        text = member_to_string(m)
        # Members render in monospace -- use mono width estimation for accurate box sizing
        w = estimate_mono_text_width(text, CLS["member_font_size"])
        if w > max_w:
            max_w = w
    return max_w


def member_to_string(m: ClassMember) -> str:
    """Convert a class member to its display string."""
    vis = f"{m.visibility} " if m.visibility else ""
    type_ = f": {m.type}" if m.type else ""
    return f"{vis}{m.name}{type_}"


# ============================================================================
# Orthogonal snapping and endpoint clipping (simplified for class diagrams)
# ============================================================================


def _snap_to_orthogonal(
    points: list[dict[str, float]], vertical_first: bool = True
) -> list[dict[str, float]]:
    """Post-process edge points into strictly orthogonal (90-degree) segments."""
    if len(points) < 2:
        return points

    result: list[dict[str, float]] = [points[0]]

    for i in range(1, len(points)):
        prev = result[-1]
        curr = points[i]

        dx = abs(curr["x"] - prev["x"])
        dy = abs(curr["y"] - prev["y"])

        if dx < 1 or dy < 1:
            result.append(curr)
            continue

        if vertical_first:
            result.append({"x": prev["x"], "y": curr["y"]})
        else:
            result.append({"x": curr["x"], "y": prev["y"]})
        result.append(curr)

    return _remove_collinear(result)


def _remove_collinear(pts: list[dict[str, float]]) -> list[dict[str, float]]:
    """Remove middle points from three-in-a-row collinear sequences."""
    if len(pts) < 3:
        return pts
    out: list[dict[str, float]] = [pts[0]]
    for i in range(1, len(pts) - 1):
        a = out[-1]
        b = pts[i]
        c = pts[i + 1]
        same_x = abs(a["x"] - b["x"]) < 1 and abs(b["x"] - c["x"]) < 1
        same_y = abs(a["y"] - b["y"]) < 1 and abs(b["y"] - c["y"]) < 1
        if same_x or same_y:
            continue
        out.append(b)
    out.append(pts[-1])
    return out


def _clip_endpoints_to_nodes(
    points: list[dict[str, float]],
    src_info: tuple[float, float, float, float] | None,
    tgt_info: tuple[float, float, float, float] | None,
) -> list[dict[str, float]]:
    """Clip edge endpoints to the correct side of rectangular node boundaries.

    src_info/tgt_info: (cx, cy, width, height) or None
    """
    if len(points) < 2:
        return points

    result = [{"x": p["x"], "y": p["y"]} for p in points]

    # --- Fix target endpoint ---
    if tgt_info is not None:
        tcx, tcy, tw, th = tgt_info
        thw, thh = tw / 2, th / 2
        last = len(result) - 1

        if len(result) == 2:
            first_pt = result[0]
            curr = result[last]
            dx = abs(curr["x"] - first_pt["x"])
            dy = abs(curr["y"] - first_pt["y"])

            if dy >= dx:
                approach_from_top = curr["y"] > first_pt["y"]
                side_y = (tcy - thh) if approach_from_top else (tcy + thh)
                result[last] = {"x": curr["x"], "y": side_y}
            else:
                approach_from_left = curr["x"] > first_pt["x"]
                side_x = (tcx - thw) if approach_from_left else (tcx + thw)
                result[last] = {"x": side_x, "y": curr["y"]}
        else:
            prev = result[last - 1]
            curr = result[last]
            dx = abs(curr["x"] - prev["x"])
            dy = abs(curr["y"] - prev["y"])

            is_horiz = dy < 1 and dx >= 1
            is_vert = dx < 1 and dy >= 1

            if is_horiz:
                approach_from_left = curr["x"] > prev["x"]
                side_x = (tcx - thw) if approach_from_left else (tcx + thw)
                result[last] = {"x": side_x, "y": tcy}
                result[last - 1] = {"x": prev["x"], "y": tcy}
            elif is_vert:
                approach_from_top = curr["y"] > prev["y"]
                side_y = (tcy - thh) if approach_from_top else (tcy + thh)
                result[last] = {"x": tcx, "y": side_y}
                result[last - 1] = {"x": tcx, "y": prev["y"]}

    # --- Fix source endpoint ---
    if src_info is not None and len(result) >= 3:
        scx, scy, sw, sh = src_info
        shw, shh = sw / 2, sh / 2

        first_pt = result[0]
        next_pt = result[1]
        dx = abs(next_pt["x"] - first_pt["x"])
        dy = abs(next_pt["y"] - first_pt["y"])

        is_horiz = dy < 1 and dx >= 1
        is_vert = dx < 1 and dy >= 1

        if is_horiz:
            exit_to_right = next_pt["x"] > first_pt["x"]
            side_x = (scx + shw) if exit_to_right else (scx - shw)
            result[0] = {"x": side_x, "y": scy}
            result[1] = {"x": result[1]["x"], "y": scy}
        elif is_vert:
            exit_downward = next_pt["y"] > first_pt["y"]
            side_y = (scy + shh) if exit_downward else (scy - shh)
            result[0] = {"x": scx, "y": side_y}
            result[1] = {"x": scx, "y": result[1]["y"]}

    return result
