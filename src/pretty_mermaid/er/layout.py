from __future__ import annotations

import math

from grandalf.graphs import Vertex, Edge, Graph
from grandalf.layouts import SugiyamaLayout

from .types import (
    ErDiagram,
    ErEntity,
    PositionedErDiagram,
    PositionedErEntity,
    PositionedErRelationship,
)
from ..types import RenderOptions, Point
from ..styles import (
    estimate_text_width,
    estimate_mono_text_width,
    FONT_SIZES,
    FONT_WEIGHTS,
)
from ..dagre_adapter import center_to_top_left, snap_to_orthogonal, clip_endpoints_to_nodes, NodeRect

# ============================================================================
# ER diagram layout engine
#
# Uses grandalf for positioning entity boxes, then sizes each box based on
# the entity name and number of attributes.
#
# Each entity box has:
#   1. Header (entity name)
#   2. Attribute rows (type, name, keys)
# ============================================================================

# Layout constants for ER diagrams
ER_PADDING = 40
ER_BOX_PAD_X = 12
ER_HEADER_HEIGHT = 32
ER_ROW_HEIGHT = 22
ER_MIN_WIDTH = 140
ER_ATTR_FONT_SIZE = 11
ER_ATTR_FONT_WEIGHT = 400
ER_NODE_SPACING = 50
ER_LAYER_SPACING = 70


# ============================================================================
# Vertex view for grandalf -- provides width/height for layout
# ============================================================================


class _VertexView:
    """Minimal view object required by grandalf's SugiyamaLayout."""

    def __init__(self, w: float = 60, h: float = 36) -> None:
        self.w = w
        self.h = h
        # xy is set by the layout engine (center coordinates)
        self.xy = (0.0, 0.0)


# ============================================================================
# Main layout function
# ============================================================================


def layout_er_diagram(
    diagram: ErDiagram,
    options: RenderOptions | None = None,
) -> PositionedErDiagram:
    """Lay out a parsed ER diagram using grandalf (Sugiyama algorithm).

    Returns positioned entity boxes and relationship paths.
    """
    if len(diagram.entities) == 0:
        return PositionedErDiagram(width=0, height=0)

    # 1. Calculate box dimensions for each entity
    entity_sizes: dict[str, tuple[float, float]] = {}

    for entity in diagram.entities:
        # Header width from entity label
        header_text_w = estimate_text_width(
            entity.label, FONT_SIZES["node_label"], FONT_WEIGHTS["node_label"]
        )

        # Max attribute row width: "type  name  PK FK"
        # Attribute text renders in monospace -- use mono width estimation for accurate box sizing
        max_attr_w = 0.0
        for attr in entity.attributes:
            attr_text = f"{attr.type}  {attr.name}"
            if attr.keys:
                attr_text += "  " + ",".join(attr.keys)
            w = estimate_mono_text_width(attr_text, ER_ATTR_FONT_SIZE)
            if w > max_attr_w:
                max_attr_w = w

        width = max(ER_MIN_WIDTH, header_text_w + ER_BOX_PAD_X * 2, max_attr_w + ER_BOX_PAD_X * 2)
        height = ER_HEADER_HEIGHT + max(len(entity.attributes), 1) * ER_ROW_HEIGHT

        entity_sizes[entity.id] = (width, height)

    # 2. Build grandalf graph
    vertices: dict[str, Vertex] = {}
    for entity in diagram.entities:
        size = entity_sizes[entity.id]
        v = Vertex(entity.id)
        v.view = _VertexView(size[0], size[1])
        vertices[entity.id] = v

    edges_list: list[Edge] = []
    edge_index_map: dict[int, int] = {}  # grandalf edge index -> original relationship index

    for i, rel in enumerate(diagram.relationships):
        src_v = vertices.get(rel.entity1)
        tgt_v = vertices.get(rel.entity2)
        if src_v and tgt_v:
            e = Edge(src_v, tgt_v)
            edge_index_map[len(edges_list)] = i
            edges_list.append(e)

    # 3. Run grandalf Sugiyama layout
    all_vertices = list(vertices.values())
    g = Graph(all_vertices, edges_list)

    try:
        sug = SugiyamaLayout(g.C[0] if g.C else g)
        sug.xspace = ER_NODE_SPACING
        sug.yspace = ER_LAYER_SPACING

        # Initialize views for any vertices that don't have one
        for v in all_vertices:
            if not hasattr(v, "view") or v.view is None:
                v.view = _VertexView()

        sug.init_all()
        sug.draw()
    except Exception as err:
        raise RuntimeError(f"Grandalf layout failed (ER diagram): {err}") from err

    # 4. Extract positioned entities
    # ER diagrams use LR direction, so swap x/y from grandalf output.
    # Grandalf outputs center coordinates via vertex.view.xy tuple.
    entity_lookup: dict[str, ErEntity] = {}
    for entity in diagram.entities:
        entity_lookup[entity.id] = entity

    positioned_entities: list[PositionedErEntity] = []
    for entity in diagram.entities:
        v = vertices[entity.id]
        vw = v.view
        # LR direction: grandalf's y-axis is our x-axis
        cx, cy = vw.xy[1], vw.xy[0]
        w = vw.w
        h = vw.h
        top_left = center_to_top_left(cx, cy, w, h)

        positioned_entities.append(
            PositionedErEntity(
                id=entity.id,
                label=entity.label,
                attributes=entity.attributes,
                x=top_left.x,
                y=top_left.y,
                width=w,
                height=h,
                header_height=ER_HEADER_HEIGHT,
                row_height=ER_ROW_HEIGHT,
            )
        )

    # 5. Extract relationship paths
    relationships: list[PositionedErRelationship] = []
    for ei, e in enumerate(edges_list):
        orig_idx = edge_index_map.get(ei)
        if orig_idx is None:
            continue
        rel = diagram.relationships[orig_idx]

        src_v = e.v[0]
        tgt_v = e.v[1]

        # LR direction: swap x/y
        src_cx, src_cy = src_v.view.xy[1], src_v.view.xy[0]
        tgt_cx, tgt_cy = tgt_v.view.xy[1], tgt_v.view.xy[0]

        raw_points = [Point(x=src_cx, y=src_cy), Point(x=tgt_cx, y=tgt_cy)]

        # LR layout -> horizontal-first bends
        ortho_points = snap_to_orthogonal(raw_points, vertical_first=False)

        # Clip endpoints to the correct side of source/target entity boxes
        src_rect = NodeRect(
            cx=src_cx,
            cy=src_cy,
            hw=src_v.view.w / 2,
            hh=src_v.view.h / 2,
        )
        tgt_rect = NodeRect(
            cx=tgt_cx,
            cy=tgt_cy,
            hw=tgt_v.view.w / 2,
            hh=tgt_v.view.h / 2,
        )
        points = clip_endpoints_to_nodes(ortho_points, src_rect, tgt_rect)

        relationships.append(
            PositionedErRelationship(
                entity1=rel.entity1,
                entity2=rel.entity2,
                cardinality1=rel.cardinality1,
                cardinality2=rel.cardinality2,
                label=rel.label,
                identifying=rel.identifying,
                points=[(p.x, p.y) for p in points],
            )
        )

    # Normalize coordinates: shift everything so minimum is at padding
    padding = ER_PADDING
    all_xs = (
        [ent.x for ent in positioned_entities]
        + [px for r in relationships for (px, _py) in r.points]
    )
    all_ys = (
        [ent.y for ent in positioned_entities]
        + [py for r in relationships for (_px, py) in r.points]
    )

    if all_xs:
        min_x = min(all_xs)
        if min_x < padding:
            dx = padding - min_x
            for ent in positioned_entities:
                ent.x += dx
            for r in relationships:
                r.points = [(px + dx, py) for (px, py) in r.points]

    if all_ys:
        min_y = min(all_ys)
        if min_y < padding:
            dy = padding - min_y
            for ent in positioned_entities:
                ent.y += dy
            for r in relationships:
                r.points = [(px, py + dy) for (px, py) in r.points]

    # Compute final dimensions
    max_x = max(
        [ent.x + ent.width for ent in positioned_entities]
        + [px for r in relationships for (px, _py) in r.points]
        + [0],
    )
    max_y = max(
        [ent.y + ent.height for ent in positioned_entities]
        + [py for r in relationships for (_px, py) in r.points]
        + [0],
    )

    graph_width = max_x + padding
    graph_height = max_y + padding

    return PositionedErDiagram(
        width=graph_width,
        height=graph_height,
        entities=positioned_entities,
        relationships=relationships,
    )
