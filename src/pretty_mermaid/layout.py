from __future__ import annotations

import math
from dataclasses import dataclass

from grandalf.graphs import Vertex, Edge, Graph
from grandalf.layouts import SugiyamaLayout

from .types import (
    MermaidGraph,
    MermaidSubgraph,
    PositionedGraph,
    PositionedNode,
    PositionedEdge,
    PositionedGroup,
    Point,
    RenderOptions,
)
from .styles import (
    estimate_text_width,
    FONT_SIZES,
    FONT_WEIGHTS,
    NODE_PADDING,
    GROUP_HEADER_CONTENT_PAD,
)
from .dagre_adapter import (
    center_to_top_left,
    snap_to_orthogonal,
    clip_to_diamond_boundary,
    clip_to_circle_boundary,
    clip_endpoints_to_nodes,
    NodeRect,
)

# Shapes that render as circles
CIRCULAR_SHAPES = {"circle", "doublecircle", "state-start", "state-end"}

# Non-rectangular shapes
NON_RECT_SHAPES = {"diamond", "circle", "doublecircle", "state-start", "state-end"}

# Layout defaults
LAYOUT_DEFAULTS = {
    "font": "Inter",
    "padding": 40,
    "node_spacing": 24,
    "layer_spacing": 40,
}


# ============================================================================
# Vertex view for grandalf — provides width/height for layout
# ============================================================================


class _VertexView:
    """Minimal view object required by grandalf's SugiyamaLayout."""

    def __init__(self, w: float = 60, h: float = 36) -> None:
        self.w = w
        self.h = h
        # xy is set by the layout engine (center coordinates)
        self.xy = (0.0, 0.0)


# ============================================================================
# Pre-computed subgraph layout data
# ============================================================================


@dataclass
class _PreComputedSubgraph:
    id: str
    label: str
    width: float
    height: float
    nodes: list[PositionedNode]
    edges: list[PositionedEdge]
    groups: list[PositionedGroup]
    node_ids: set[str]
    internal_edge_indices: set[int]


# ============================================================================
# Main layout function
# ============================================================================


def layout_graph(
    graph: MermaidGraph,
    options: RenderOptions | None = None,
) -> PositionedGraph:
    """Lay out a parsed mermaid graph using grandalf (Sugiyama algorithm).

    Returns a fully positioned graph ready for SVG rendering.
    """
    opts = _merge_options(options)
    is_horizontal = graph.direction in ("LR", "RL")
    is_reversed = graph.direction in ("BT", "RL")

    # Phase 1: Pre-compute layouts for subgraphs with direction overrides
    pre_computed: dict[str, _PreComputedSubgraph] = {}
    for sg in graph.subgraphs:
        if sg.direction and sg.direction != graph.direction:
            pre_computed[sg.id] = _pre_compute_subgraph_layout(sg, graph, opts)

    # Collect node IDs in subgraphs
    subgraph_node_ids: set[str] = set()
    for sg in graph.subgraphs:
        subgraph_node_ids.add(sg.id)
        _collect_subgraph_node_ids(sg, subgraph_node_ids)

    # Build redirect maps
    subgraph_entry_node: dict[str, str] = {}
    subgraph_exit_node: dict[str, str] = {}
    for sg in graph.subgraphs:
        if sg.id not in pre_computed:
            _build_subgraph_redirects(sg, subgraph_entry_node, subgraph_exit_node)

    for sg_id, pc in pre_computed.items():
        for node_id in pc.node_ids:
            subgraph_entry_node[node_id] = sg_id
            subgraph_exit_node[node_id] = sg_id

    # Collect all internal edge indices from pre-computed subgraphs
    all_internal_indices: set[int] = set()
    for pc in pre_computed.values():
        all_internal_indices |= pc.internal_edge_indices

    # Phase 2: Build the main grandalf graph
    vertices: dict[str, Vertex] = {}

    # Add top-level nodes
    for nid, node in graph.nodes.items():
        if nid in subgraph_node_ids:
            continue
        size = _estimate_node_size(nid, node.label, node.shape)
        v = Vertex(nid)
        v.view = _VertexView(size[0], size[1])
        vertices[nid] = v

    # Add pre-computed subgraphs as placeholder nodes
    for sg_id, pc in pre_computed.items():
        v = Vertex(sg_id)
        v.view = _VertexView(pc.width, pc.height)
        vertices[sg_id] = v

    # Add subgraph compound nodes and their children
    for sg in graph.subgraphs:
        if sg.id not in pre_computed:
            _add_subgraph_nodes(vertices, sg, graph)

    # Build edges
    edges_list: list[Edge] = []
    edge_index_map: dict[int, int] = {}  # grandalf edge index -> original edge index

    introduced_targets: set[str] = set()

    for i, edge in enumerate(graph.edges):
        if i in all_internal_indices:
            continue
        source = subgraph_exit_node.get(edge.source, edge.source)
        target = subgraph_entry_node.get(edge.target, edge.target)

        src_v = vertices.get(source)
        tgt_v = vertices.get(target)
        if not src_v or not tgt_v:
            continue

        e = Edge(src_v, tgt_v)
        edge_index_map[len(edges_list)] = i
        edges_list.append(e)

    # Build grandalf graph and run layout
    all_vertices = list(vertices.values())
    g = Graph(all_vertices, edges_list)

    # Run Sugiyama layout
    sug = SugiyamaLayout(g.C[0] if g.C else g)
    sug.xspace = opts["node_spacing"]
    sug.yspace = opts["layer_spacing"]

    # Initialize views for any vertices that don't have one
    for v in all_vertices:
        if not hasattr(v, "view") or v.view is None:
            v.view = _VertexView()

    sug.init_all()
    sug.draw()

    # Phase 3: Extract positions
    vertical_first = graph.direction in ("TD", "TB", "BT")

    # Build subgraph ID set
    subgraph_ids: set[str] = set()
    for sg in graph.subgraphs:
        _collect_all_subgraph_ids(sg, subgraph_ids)

    pre_computed_node_ids: set[str] = set()
    for pc in pre_computed.values():
        pre_computed_node_ids |= pc.node_ids

    # Extract nodes
    nodes: list[PositionedNode] = []
    for nid, v in vertices.items():
        if nid in subgraph_ids:
            continue
        m_node = graph.nodes.get(nid)
        if not m_node:
            # Could be a pre-computed subgraph placeholder
            if nid in pre_computed:
                continue
            continue

        vw = v.view
        if is_horizontal:
            # For LR/RL, grandalf's y-axis is our x-axis
            cx, cy = vw.xy[1], vw.xy[0]
        else:
            cx, cy = vw.xy[0], vw.xy[1]

        if is_reversed:
            if is_horizontal:
                cx = -cx
            else:
                cy = -cy

        w, h = vw.w, vw.h
        top_left = center_to_top_left(cx, cy, w, h)

        nodes.append(PositionedNode(
            id=nid,
            label=m_node.label,
            shape=m_node.shape,
            x=top_left.x,
            y=top_left.y,
            width=w,
            height=h,
            inline_style=_resolve_node_style(graph, nid),
        ))

    # Extract edges
    pos_edges: list[PositionedEdge] = []
    for ei, e in enumerate(edges_list):
        orig_idx = edge_index_map.get(ei)
        if orig_idx is None:
            continue
        original_edge = graph.edges[orig_idx]

        # Get source and target positions
        src_v = e.v[0]
        tgt_v = e.v[1]

        if is_horizontal:
            src_cx, src_cy = src_v.view.xy[1], src_v.view.xy[0]
            tgt_cx, tgt_cy = tgt_v.view.xy[1], tgt_v.view.xy[0]
        else:
            src_cx, src_cy = src_v.view.xy[0], src_v.view.xy[1]
            tgt_cx, tgt_cy = tgt_v.view.xy[0], tgt_v.view.xy[1]

        if is_reversed:
            if is_horizontal:
                src_cx, tgt_cx = -src_cx, -tgt_cx
            else:
                src_cy, tgt_cy = -src_cy, -tgt_cy

        raw_points = [Point(x=src_cx, y=src_cy), Point(x=tgt_cx, y=tgt_cy)]

        # Clip to non-rectangular boundaries
        if raw_points:
            src_shape = graph.nodes.get(original_edge.source)
            if src_shape and src_shape.shape == "diamond":
                hw = src_v.view.w / 2
                hh = src_v.view.h / 2
                raw_points[0] = clip_to_diamond_boundary(
                    raw_points[0], src_cx, src_cy, hw, hh
                )
            elif src_shape and src_shape.shape in CIRCULAR_SHAPES:
                r = min(src_v.view.w, src_v.view.h) / 2
                raw_points[0] = clip_to_circle_boundary(
                    raw_points[0], src_cx, src_cy, r
                )

            tgt_shape = graph.nodes.get(original_edge.target)
            if tgt_shape and tgt_shape.shape == "diamond":
                hw = tgt_v.view.w / 2
                hh = tgt_v.view.h / 2
                raw_points[-1] = clip_to_diamond_boundary(
                    raw_points[-1], tgt_cx, tgt_cy, hw, hh
                )
            elif tgt_shape and tgt_shape.shape in CIRCULAR_SHAPES:
                r = min(tgt_v.view.w, tgt_v.view.h) / 2
                raw_points[-1] = clip_to_circle_boundary(
                    raw_points[-1], tgt_cx, tgt_cy, r
                )

        ortho_points = snap_to_orthogonal(raw_points, vertical_first)

        # Clip rectangular endpoints
        src_shape_name = graph.nodes.get(original_edge.source)
        tgt_shape_name = graph.nodes.get(original_edge.target)
        src_rect = None
        if src_shape_name and src_shape_name.shape not in NON_RECT_SHAPES:
            src_rect = NodeRect(
                cx=src_cx, cy=src_cy,
                hw=src_v.view.w / 2, hh=src_v.view.h / 2,
            )
        tgt_rect = None
        if tgt_shape_name and tgt_shape_name.shape not in NON_RECT_SHAPES:
            tgt_rect = NodeRect(
                cx=tgt_cx, cy=tgt_cy,
                hw=tgt_v.view.w / 2, hh=tgt_v.view.h / 2,
            )
        points = clip_endpoints_to_nodes(ortho_points, src_rect, tgt_rect)

        # Label position at midpoint
        label_position: Point | None = None
        if original_edge.label and len(points) >= 2:
            mid_x = (points[0].x + points[-1].x) / 2
            mid_y = (points[0].y + points[-1].y) / 2
            label_position = Point(x=mid_x, y=mid_y)

        pos_edges.append(PositionedEdge(
            source=original_edge.source,
            target=original_edge.target,
            label=original_edge.label,
            style=original_edge.style,
            has_arrow_start=original_edge.has_arrow_start,
            has_arrow_end=original_edge.has_arrow_end,
            points=points,
            label_position=label_position,
        ))

    # Extract groups
    groups: list[PositionedGroup] = []
    for sg in graph.subgraphs:
        groups.append(_extract_group(vertices, sg, is_horizontal, is_reversed))

    # Compose pre-computed layouts
    if pre_computed:
        node_position_map: dict[str, tuple[float, float]] = {}
        for n in nodes:
            node_position_map[n.id] = (n.x + n.width / 2, n.y + n.height / 2)

        for sg_id, pc in pre_computed.items():
            v = vertices.get(sg_id)
            if not v:
                continue
            vw = v.view
            if is_horizontal:
                ph_cx, ph_cy = vw.xy[1], vw.xy[0]
            else:
                ph_cx, ph_cy = vw.xy[0], vw.xy[1]
            if is_reversed:
                if is_horizontal:
                    ph_cx = -ph_cx
                else:
                    ph_cy = -ph_cy

            top_left = center_to_top_left(ph_cx, ph_cy, vw.w, vw.h)

            for pc_node in pc.nodes:
                composed = PositionedNode(
                    id=pc_node.id,
                    label=pc_node.label,
                    shape=pc_node.shape,
                    x=pc_node.x + top_left.x,
                    y=pc_node.y + top_left.y,
                    width=pc_node.width,
                    height=pc_node.height,
                    inline_style=pc_node.inline_style,
                )
                nodes.append(composed)
                node_position_map[composed.id] = (
                    composed.x + composed.width / 2,
                    composed.y + composed.height / 2,
                )

            for pc_edge in pc.edges:
                pos_edges.append(PositionedEdge(
                    source=pc_edge.source,
                    target=pc_edge.target,
                    label=pc_edge.label,
                    style=pc_edge.style,
                    has_arrow_start=pc_edge.has_arrow_start,
                    has_arrow_end=pc_edge.has_arrow_end,
                    points=[Point(x=p.x + top_left.x, y=p.y + top_left.y) for p in pc_edge.points],
                    label_position=Point(
                        x=pc_edge.label_position.x + top_left.x,
                        y=pc_edge.label_position.y + top_left.y,
                    ) if pc_edge.label_position else None,
                ))

            group = _find_group_by_id(groups, sg_id)
            if group and pc.groups:
                group.children = [_offset_group(cg, top_left.x, top_left.y) for cg in pc.groups]

        # Fix cross-boundary edges
        for edge in pos_edges:
            if edge.source in pre_computed_node_ids and edge.target in pre_computed_node_ids:
                continue
            modified = False
            if edge.source in pre_computed_node_ids:
                pos = node_position_map.get(edge.source)
                if pos and edge.points:
                    edge.points[0] = Point(x=pos[0], y=pos[1])
                    modified = True
            if edge.target in pre_computed_node_ids:
                pos = node_position_map.get(edge.target)
                if pos and edge.points:
                    edge.points[-1] = Point(x=pos[0], y=pos[1])
                    modified = True
            if modified:
                edge.points = snap_to_orthogonal(edge.points, vertical_first)

    # Post-process: expand groups for headers
    header_height = FONT_SIZES["group_header"] + 16
    _expand_groups_for_headers(groups, header_height)

    # Normalize coordinates: shift everything so minimum is at padding
    padding = opts["padding"]
    flat_groups = _flatten_all_groups(groups)
    all_ys = [n.y for n in nodes] + [g.y for g in flat_groups]
    all_xs = [n.x for n in nodes] + [g.x for g in flat_groups]

    if all_ys:
        min_y = min(all_ys)
        if min_y < padding:
            dy = padding - min_y
            for n in nodes:
                n.y += dy
            for e in pos_edges:
                for p in e.points:
                    p.y += dy
                if e.label_position:
                    e.label_position.y += dy
            for fg in flat_groups:
                fg.y += dy

    if all_xs:
        min_x = min(all_xs)
        if min_x < padding:
            dx = padding - min_x
            for n in nodes:
                n.x += dx
            for e in pos_edges:
                for p in e.points:
                    p.x += dx
                if e.label_position:
                    e.label_position.x += dx
            for fg in flat_groups:
                fg.x += dx

    # Compute final dimensions
    flat_groups = _flatten_all_groups(groups)
    max_x = max(
        [n.x + n.width for n in nodes]
        + [g.x + g.width for g in flat_groups]
        + [p.x for e in pos_edges for p in e.points]
        + [0],
    )
    max_y = max(
        [n.y + n.height for n in nodes]
        + [g.y + g.height for g in flat_groups]
        + [p.y for e in pos_edges for p in e.points]
        + [0],
    )

    graph_width = max_x + padding
    graph_height = max_y + padding

    return PositionedGraph(
        width=graph_width,
        height=graph_height,
        nodes=nodes,
        edges=pos_edges,
        groups=groups,
    )


# ============================================================================
# Helpers
# ============================================================================


def _merge_options(options: RenderOptions | None) -> dict:
    opts = dict(LAYOUT_DEFAULTS)
    if options:
        if options.font is not None:
            opts["font"] = options.font
        if options.padding is not None:
            opts["padding"] = options.padding
        if options.node_spacing is not None:
            opts["node_spacing"] = options.node_spacing
        if options.layer_spacing is not None:
            opts["layer_spacing"] = options.layer_spacing
    return opts


def _estimate_node_size(node_id: str, label: str, shape: str) -> tuple[float, float]:
    text_width = estimate_text_width(label, FONT_SIZES["node_label"], FONT_WEIGHTS["node_label"])

    width = text_width + NODE_PADDING["horizontal"] * 2
    height = FONT_SIZES["node_label"] + NODE_PADDING["vertical"] * 2

    if shape == "diamond":
        side = max(width, height) + NODE_PADDING["diamond_extra"]
        width = height = side

    if shape in ("circle", "doublecircle"):
        diameter = math.ceil(math.sqrt(width * width + height * height)) + 8
        width = diameter + 12 if shape == "doublecircle" else diameter
        height = width

    if shape == "hexagon":
        width += NODE_PADDING["horizontal"]

    if shape in ("trapezoid", "trapezoid-alt"):
        width += NODE_PADDING["horizontal"]

    if shape == "asymmetric":
        width += 12

    if shape == "cylinder":
        height += 14

    if shape in ("state-start", "state-end"):
        width = height = 28

    width = max(width, 60)
    height = max(height, 36)

    return width, height


def _add_subgraph_nodes(
    vertices: dict[str, Vertex],
    sg: MermaidSubgraph,
    graph: MermaidGraph,
) -> None:
    """Add subgraph nodes to the vertex dict."""
    if sg.id not in vertices:
        v = Vertex(sg.id)
        v.view = _VertexView()
        vertices[sg.id] = v

    for node_id in sg.node_ids:
        node = graph.nodes.get(node_id)
        if node and node_id not in vertices:
            size = _estimate_node_size(node_id, node.label, node.shape)
            v = Vertex(node_id)
            v.view = _VertexView(size[0], size[1])
            vertices[node_id] = v

    for child in sg.children:
        _add_subgraph_nodes(vertices, child, graph)


def _build_subgraph_redirects(
    sg: MermaidSubgraph,
    entry_map: dict[str, str],
    exit_map: dict[str, str],
) -> None:
    for child in sg.children:
        _build_subgraph_redirects(child, entry_map, exit_map)

    child_ids = list(sg.node_ids) + [c.id for c in sg.children]

    if not child_ids:
        entry_map[sg.id] = sg.id
        exit_map[sg.id] = sg.id
        return

    first_child = child_ids[0]
    last_child = child_ids[-1]
    entry_map[sg.id] = entry_map.get(first_child, first_child)
    exit_map[sg.id] = exit_map.get(last_child, last_child)


def _resolve_node_style(
    graph: MermaidGraph, node_id: str
) -> dict[str, str] | None:
    class_name = graph.class_assignments.get(node_id)
    class_props = graph.class_defs.get(class_name) if class_name else None
    inline_props = graph.node_styles.get(node_id)
    if not class_props and not inline_props:
        return None
    result: dict[str, str] = {}
    if class_props:
        result.update(class_props)
    if inline_props:
        result.update(inline_props)
    return result


def _collect_subgraph_node_ids(sg: MermaidSubgraph, out: set[str]) -> None:
    for nid in sg.node_ids:
        out.add(nid)
    for child in sg.children:
        _collect_subgraph_node_ids(child, out)


def _collect_all_subgraph_ids(sg: MermaidSubgraph, out: set[str]) -> None:
    out.add(sg.id)
    for child in sg.children:
        _collect_all_subgraph_ids(child, out)


def _extract_group(
    vertices: dict[str, Vertex],
    sg: MermaidSubgraph,
    is_horizontal: bool,
    is_reversed: bool,
) -> PositionedGroup:
    v = vertices.get(sg.id)
    if v and v.view:
        vw = v.view
        if is_horizontal:
            cx, cy = vw.xy[1], vw.xy[0]
        else:
            cx, cy = vw.xy[0], vw.xy[1]
        if is_reversed:
            if is_horizontal:
                cx = -cx
            else:
                cy = -cy
        top_left = center_to_top_left(cx, cy, vw.w, vw.h)
        x, y = top_left.x, top_left.y
        w, h = vw.w, vw.h
    else:
        x = y = 0.0
        w = h = 0.0

    # For groups, compute bounding box from children
    child_nodes: list[PositionedNode] = []
    for node_id in sg.node_ids:
        nv = vertices.get(node_id)
        if nv and nv.view:
            nvw = nv.view
            if is_horizontal:
                ncx, ncy = nvw.xy[1], nvw.xy[0]
            else:
                ncx, ncy = nvw.xy[0], nvw.xy[1]
            if is_reversed:
                if is_horizontal:
                    ncx = -ncx
                else:
                    ncy = -ncy
            ntl = center_to_top_left(ncx, ncy, nvw.w, nvw.h)
            child_nodes.append(PositionedNode(
                id=node_id, label="", shape="rectangle",
                x=ntl.x, y=ntl.y, width=nvw.w, height=nvw.h,
            ))

    children = [
        _extract_group(vertices, child, is_horizontal, is_reversed)
        for child in sg.children
    ]

    # Compute bounding box from all children (nodes + child groups)
    all_items = child_nodes + [
        PositionedNode(id=c.id, label="", shape="rectangle", x=c.x, y=c.y, width=c.width, height=c.height)
        for c in children
    ]

    if all_items:
        min_x = min(item.x for item in all_items)
        min_y = min(item.y for item in all_items)
        max_x = max(item.x + item.width for item in all_items)
        max_y = max(item.y + item.height for item in all_items)
        pad = 16
        x = min_x - pad
        y = min_y - pad
        w = (max_x - min_x) + 2 * pad
        h = (max_y - min_y) + 2 * pad

    return PositionedGroup(
        id=sg.id,
        label=sg.label,
        x=x,
        y=y,
        width=w,
        height=h,
        children=children,
    )


def _pre_compute_subgraph_layout(
    sg: MermaidSubgraph,
    graph: MermaidGraph,
    opts: dict,
) -> _PreComputedSubgraph:
    """Pre-compute layout for a direction-overridden subgraph."""
    is_horizontal = sg.direction in ("LR", "RL")
    is_reversed = sg.direction in ("BT", "RL")
    vertical_first = sg.direction in ("TD", "TB", "BT")

    node_ids: set[str] = {sg.id}
    _collect_subgraph_node_ids(sg, node_ids)

    vertices: dict[str, Vertex] = {}

    for node_id in sg.node_ids:
        node = graph.nodes.get(node_id)
        if node:
            size = _estimate_node_size(node_id, node.label, node.shape)
            v = Vertex(node_id)
            v.view = _VertexView(size[0], size[1])
            vertices[node_id] = v

    for child in sg.children:
        _add_subgraph_nodes(vertices, child, graph)

    internal_edge_indices: set[int] = set()
    edges_list: list[Edge] = []
    edge_idx_map: dict[int, int] = {}

    for i, edge in enumerate(graph.edges):
        if edge.source in node_ids and edge.target in node_ids:
            internal_edge_indices.add(i)
            src_v = vertices.get(edge.source)
            tgt_v = vertices.get(edge.target)
            if src_v and tgt_v:
                e = Edge(src_v, tgt_v)
                edge_idx_map[len(edges_list)] = i
                edges_list.append(e)

    all_verts = list(vertices.values())
    if not all_verts:
        return _PreComputedSubgraph(
            id=sg.id, label=sg.label,
            width=200, height=100,
            nodes=[], edges=[], groups=[],
            node_ids=node_ids,
            internal_edge_indices=internal_edge_indices,
        )

    sub_g = Graph(all_verts, edges_list)
    sug = SugiyamaLayout(sub_g.C[0] if sub_g.C else sub_g)
    sug.xspace = opts["node_spacing"]
    sug.yspace = opts["layer_spacing"]

    for v in all_verts:
        if not hasattr(v, "view") or v.view is None:
            v.view = _VertexView()

    sug.init_all()
    sug.draw()

    # Extract nodes
    nested_sg_ids: set[str] = set()
    for child in sg.children:
        _collect_all_subgraph_ids(child, nested_sg_ids)

    nodes: list[PositionedNode] = []
    for nid, v in vertices.items():
        if nid in nested_sg_ids:
            continue
        m_node = graph.nodes.get(nid)
        if not m_node:
            continue
        vw = v.view
        if is_horizontal:
            cx, cy = vw.xy[1], vw.xy[0]
        else:
            cx, cy = vw.xy[0], vw.xy[1]
        if is_reversed:
            if is_horizontal:
                cx = -cx
            else:
                cy = -cy
        tl = center_to_top_left(cx, cy, vw.w, vw.h)
        nodes.append(PositionedNode(
            id=nid, label=m_node.label, shape=m_node.shape,
            x=tl.x, y=tl.y, width=vw.w, height=vw.h,
            inline_style=_resolve_node_style(graph, nid),
        ))

    # Extract edges
    pos_edges: list[PositionedEdge] = []
    for ei, e in enumerate(edges_list):
        orig_idx = edge_idx_map.get(ei)
        if orig_idx is None:
            continue
        original_edge = graph.edges[orig_idx]

        src_v = e.v[0]
        tgt_v = e.v[1]
        if is_horizontal:
            src_cx, src_cy = src_v.view.xy[1], src_v.view.xy[0]
            tgt_cx, tgt_cy = tgt_v.view.xy[1], tgt_v.view.xy[0]
        else:
            src_cx, src_cy = src_v.view.xy[0], src_v.view.xy[1]
            tgt_cx, tgt_cy = tgt_v.view.xy[0], tgt_v.view.xy[1]
        if is_reversed:
            if is_horizontal:
                src_cx, tgt_cx = -src_cx, -tgt_cx
            else:
                src_cy, tgt_cy = -src_cy, -tgt_cy

        raw_points = [Point(x=src_cx, y=src_cy), Point(x=tgt_cx, y=tgt_cy)]
        ortho_points = snap_to_orthogonal(raw_points, vertical_first)

        src_shape = graph.nodes.get(original_edge.source)
        tgt_shape = graph.nodes.get(original_edge.target)
        src_rect = None
        if src_shape and src_shape.shape not in NON_RECT_SHAPES:
            src_rect = NodeRect(cx=src_cx, cy=src_cy, hw=src_v.view.w / 2, hh=src_v.view.h / 2)
        tgt_rect = None
        if tgt_shape and tgt_shape.shape not in NON_RECT_SHAPES:
            tgt_rect = NodeRect(cx=tgt_cx, cy=tgt_cy, hw=tgt_v.view.w / 2, hh=tgt_v.view.h / 2)
        points = clip_endpoints_to_nodes(ortho_points, src_rect, tgt_rect)

        label_pos: Point | None = None
        if original_edge.label and len(points) >= 2:
            label_pos = Point(
                x=(points[0].x + points[-1].x) / 2,
                y=(points[0].y + points[-1].y) / 2,
            )

        pos_edges.append(PositionedEdge(
            source=original_edge.source,
            target=original_edge.target,
            label=original_edge.label,
            style=original_edge.style,
            has_arrow_start=original_edge.has_arrow_start,
            has_arrow_end=original_edge.has_arrow_end,
            points=points,
            label_position=label_pos,
        ))

    # Normalize to (0,0) origin
    all_xs = [n.x for n in nodes] + [p.x for e in pos_edges for p in e.points]
    all_ys = [n.y for n in nodes] + [p.y for e in pos_edges for p in e.points]

    if all_xs and all_ys:
        min_x = min(all_xs)
        min_y = min(all_ys)
        for n in nodes:
            n.x -= min_x
            n.y -= min_y
        for e in pos_edges:
            for p in e.points:
                p.x -= min_x
                p.y -= min_y
            if e.label_position:
                e.label_position.x -= min_x
                e.label_position.y -= min_y

    max_x = max([n.x + n.width for n in nodes] + [0])
    max_y = max([n.y + n.height for n in nodes] + [0])

    groups: list[PositionedGroup] = []
    for child in sg.children:
        groups.append(_extract_group(vertices, child, is_horizontal, is_reversed))

    return _PreComputedSubgraph(
        id=sg.id,
        label=sg.label,
        width=max(max_x + 32, 200),
        height=max(max_y + 24, 100),
        nodes=nodes,
        edges=pos_edges,
        groups=groups,
        node_ids=node_ids,
        internal_edge_indices=internal_edge_indices,
    )


# ============================================================================
# Header space post-processing
# ============================================================================


def _expand_groups_for_headers(groups: list[PositionedGroup], header_height: float) -> None:
    for group in groups:
        _expand_group_for_header(group, header_height)


def _expand_group_for_header(group: PositionedGroup, header_height: float) -> None:
    for child in group.children:
        _expand_group_for_header(child, header_height)

    if group.children:
        min_y = group.y
        max_y = group.y + group.height
        for child in group.children:
            min_y = min(min_y, child.y)
            max_y = max(max_y, child.y + child.height)
        group.height = max_y - min_y
        group.y = min_y

    if group.label:
        expansion = header_height + GROUP_HEADER_CONTENT_PAD
        group.y -= expansion
        group.height += expansion


def _flatten_all_groups(groups: list[PositionedGroup]) -> list[PositionedGroup]:
    result: list[PositionedGroup] = []
    for g in groups:
        result.append(g)
        result.extend(_flatten_all_groups(g.children))
    return result


def _find_group_by_id(
    groups: list[PositionedGroup], group_id: str
) -> PositionedGroup | None:
    for g in groups:
        if g.id == group_id:
            return g
        found = _find_group_by_id(g.children, group_id)
        if found:
            return found
    return None


def _offset_group(
    group: PositionedGroup, dx: float, dy: float
) -> PositionedGroup:
    return PositionedGroup(
        id=group.id,
        label=group.label,
        x=group.x + dx,
        y=group.y + dy,
        width=group.width,
        height=group.height,
        children=[_offset_group(c, dx, dy) for c in group.children],
    )
