from __future__ import annotations

# ============================================================================
# ASCII renderer -- grid-based layout
#
# Ported from AlexanderGrooff/mermaid-ascii cmd/graph.go + cmd/mapping_node.go.
# Places nodes on a logical grid, computes column/row sizes,
# converts grid coordinates to character-level drawing coordinates,
# and handles subgraph bounding boxes.
# ============================================================================

from .types import (
    GridCoord,
    DrawingCoord,
    Direction,
    AsciiGraph,
    AsciiNode,
    AsciiSubgraph,
    grid_key,
)
from .canvas import mk_canvas, set_canvas_size_to_grid
from .edge_routing import determine_path, determine_label_line
# draw_box imported lazily inside create_mapping() to avoid circular import with draw.py

# ============================================================================
# Grid coordinate -> drawing coordinate conversion
# ============================================================================


def grid_to_drawing_coord(
    graph: AsciiGraph,
    c: GridCoord,
    d: Direction | None = None,
) -> DrawingCoord:
    """Convert a grid coordinate to a drawing (character) coordinate.

    Sums column widths up to the target column, and row heights up to the
    target row, then centers within the cell.
    """
    if d is not None:
        target = GridCoord(x=c.x + d.x, y=c.y + d.y)
    else:
        target = c

    x = 0
    for col in range(target.x):
        x += graph.column_width.get(col, 0)

    y = 0
    for row in range(target.y):
        y += graph.row_height.get(row, 0)

    col_w = graph.column_width.get(target.x, 0)
    row_h = graph.row_height.get(target.y, 0)
    return DrawingCoord(
        x=x + col_w // 2 + graph.offset_x,
        y=y + row_h // 2 + graph.offset_y,
    )


def line_to_drawing(graph: AsciiGraph, line: list[GridCoord]) -> list[DrawingCoord]:
    """Convert a path of grid coords to drawing coords."""
    return [grid_to_drawing_coord(graph, c) for c in line]


# ============================================================================
# Node placement on the grid
# ============================================================================


def reserve_spot_in_grid(
    graph: AsciiGraph,
    node: AsciiNode,
    requested: GridCoord,
) -> GridCoord:
    """Reserve a 3x3 block in the grid for a node.

    If the requested position is occupied, recursively shift by 4 grid units
    (in the perpendicular direction based on graph direction) until a free
    spot is found.
    """
    if grid_key(requested) in graph.grid:
        # Collision -- shift perpendicular to main flow direction
        if graph.config.graph_direction == "LR":
            return reserve_spot_in_grid(
                graph, node, GridCoord(x=requested.x, y=requested.y + 4),
            )
        else:
            return reserve_spot_in_grid(
                graph, node, GridCoord(x=requested.x + 4, y=requested.y),
            )

    # Reserve the 3x3 block
    for dx in range(3):
        for dy in range(3):
            reserved = GridCoord(x=requested.x + dx, y=requested.y + dy)
            graph.grid[grid_key(reserved)] = node

    node.grid_coord = requested
    return requested


# ============================================================================
# Column width / row height computation
# ============================================================================


def set_column_width(graph: AsciiGraph, node: AsciiNode) -> None:
    """Set column widths and row heights for a node's 3x3 grid block.

    Each node occupies 3 columns (border, content, border) and 3 rows.
    The content column must be wide enough for the node's label.
    """
    gc = node.grid_coord
    assert gc is not None
    padding = graph.config.box_border_padding

    # 3 columns: [border=1] [content=2*padding+label_len] [border=1]
    col_widths = [1, 2 * padding + len(node.display_label), 1]
    # 3 rows: [border=1] [content=1+2*padding] [border=1]
    row_heights = [1, 1 + 2 * padding, 1]

    for idx in range(len(col_widths)):
        x_coord = gc.x + idx
        current = graph.column_width.get(x_coord, 0)
        graph.column_width[x_coord] = max(current, col_widths[idx])

    for idx in range(len(row_heights)):
        y_coord = gc.y + idx
        current = graph.row_height.get(y_coord, 0)
        graph.row_height[y_coord] = max(current, row_heights[idx])

    # Padding column/row before the node (spacing between nodes)
    if gc.x > 0:
        current = graph.column_width.get(gc.x - 1, 0)
        graph.column_width[gc.x - 1] = max(current, graph.config.padding_x)

    if gc.y > 0:
        base_padding = graph.config.padding_y
        # Extra vertical padding for nodes with incoming edges from outside
        # their subgraph
        if _has_incoming_edge_from_outside_subgraph(graph, node):
            subgraph_overhead = 4
            base_padding += subgraph_overhead
        current = graph.row_height.get(gc.y - 1, 0)
        graph.row_height[gc.y - 1] = max(current, base_padding)


def increase_grid_size_for_path(graph: AsciiGraph, path: list[GridCoord]) -> None:
    """Ensure grid has width/height entries for all cells along an edge path."""
    for c in path:
        if c.x not in graph.column_width:
            graph.column_width[c.x] = graph.config.padding_x // 2
        if c.y not in graph.row_height:
            graph.row_height[c.y] = graph.config.padding_y // 2


# ============================================================================
# Subgraph helpers
# ============================================================================


def _is_node_in_any_subgraph(graph: AsciiGraph, node: AsciiNode) -> bool:
    return any(node in sg.nodes for sg in graph.subgraphs)


def _get_node_subgraph(graph: AsciiGraph, node: AsciiNode) -> AsciiSubgraph | None:
    for sg in graph.subgraphs:
        if node in sg.nodes:
            return sg
    return None


def _has_incoming_edge_from_outside_subgraph(
    graph: AsciiGraph,
    node: AsciiNode,
) -> bool:
    """Check if a node has an incoming edge from outside its subgraph
    AND is the topmost such node in its subgraph.
    Used to add extra vertical padding for subgraph borders.
    """
    node_sg = _get_node_subgraph(graph, node)
    if node_sg is None:
        return False

    has_external_edge = False
    for edge in graph.edges:
        if edge.to_node is node:
            source_sg = _get_node_subgraph(graph, edge.from_node)
            if source_sg is not node_sg:
                has_external_edge = True
                break

    if not has_external_edge:
        return False

    # Only return true for the topmost node with an external incoming edge
    for other_node in node_sg.nodes:
        if other_node is node or other_node.grid_coord is None:
            continue
        other_has_external = False
        for edge in graph.edges:
            if edge.to_node is other_node:
                source_sg = _get_node_subgraph(graph, edge.from_node)
                if source_sg is not node_sg:
                    other_has_external = True
                    break
        if other_has_external and other_node.grid_coord.y < node.grid_coord.y:  # type: ignore[union-attr]
            return False

    return True


# ============================================================================
# Subgraph bounding boxes
# ============================================================================


def _calculate_subgraph_bounding_box(
    graph: AsciiGraph,
    sg: AsciiSubgraph,
) -> None:
    if len(sg.nodes) == 0:
        return

    min_x = 1_000_000
    min_y = 1_000_000
    max_x = -1_000_000
    max_y = -1_000_000

    # Include children's bounding boxes
    for child in sg.children:
        _calculate_subgraph_bounding_box(graph, child)
        if len(child.nodes) > 0:
            min_x = min(min_x, child.min_x)
            min_y = min(min_y, child.min_y)
            max_x = max(max_x, child.max_x)
            max_y = max(max_y, child.max_y)

    # Include node positions
    for node in sg.nodes:
        if node.drawing_coord is None or node.drawing is None:
            continue
        node_min_x = node.drawing_coord.x
        node_min_y = node.drawing_coord.y
        node_max_x = node_min_x + len(node.drawing) - 1
        node_max_y = node_min_y + len(node.drawing[0]) - 1
        min_x = min(min_x, node_min_x)
        min_y = min(min_y, node_min_y)
        max_x = max(max_x, node_max_x)
        max_y = max(max_y, node_max_y)

    subgraph_padding = 2
    subgraph_label_space = 2
    sg.min_x = min_x - subgraph_padding
    sg.min_y = min_y - subgraph_padding - subgraph_label_space
    sg.max_x = max_x + subgraph_padding
    sg.max_y = max_y + subgraph_padding


def _ensure_subgraph_spacing(graph: AsciiGraph) -> None:
    """Ensure non-overlapping root subgraphs have minimum spacing."""
    min_spacing = 1
    root_subgraphs = [
        sg for sg in graph.subgraphs
        if sg.parent is None and len(sg.nodes) > 0
    ]

    for i in range(len(root_subgraphs)):
        for j in range(i + 1, len(root_subgraphs)):
            sg1 = root_subgraphs[i]
            sg2 = root_subgraphs[j]

            # Horizontal overlap -> adjust vertical
            if sg1.min_x < sg2.max_x and sg1.max_x > sg2.min_x:
                if (
                    sg1.max_y >= sg2.min_y - min_spacing
                    and sg1.min_y < sg2.min_y
                ):
                    sg2.min_y = sg1.max_y + min_spacing + 1
                elif (
                    sg2.max_y >= sg1.min_y - min_spacing
                    and sg2.min_y < sg1.min_y
                ):
                    sg1.min_y = sg2.max_y + min_spacing + 1

            # Vertical overlap -> adjust horizontal
            if sg1.min_y < sg2.max_y and sg1.max_y > sg2.min_y:
                if (
                    sg1.max_x >= sg2.min_x - min_spacing
                    and sg1.min_x < sg2.min_x
                ):
                    sg2.min_x = sg1.max_x + min_spacing + 1
                elif (
                    sg2.max_x >= sg1.min_x - min_spacing
                    and sg2.min_x < sg1.min_x
                ):
                    sg1.min_x = sg2.max_x + min_spacing + 1


def calculate_subgraph_bounding_boxes(graph: AsciiGraph) -> None:
    for sg in graph.subgraphs:
        _calculate_subgraph_bounding_box(graph, sg)
    _ensure_subgraph_spacing(graph)


def offset_drawing_for_subgraphs(graph: AsciiGraph) -> None:
    """Offset all drawing coordinates so subgraph borders don't go negative.

    If any subgraph has negative min coordinates, shift everything positive.
    """
    if len(graph.subgraphs) == 0:
        return

    min_x = 0
    min_y = 0
    for sg in graph.subgraphs:
        min_x = min(min_x, sg.min_x)
        min_y = min(min_y, sg.min_y)

    off_x = -min_x
    off_y = -min_y
    if off_x == 0 and off_y == 0:
        return

    graph.offset_x = off_x
    graph.offset_y = off_y

    for sg in graph.subgraphs:
        sg.min_x += off_x
        sg.min_y += off_y
        sg.max_x += off_x
        sg.max_y += off_y

    for node in graph.nodes:
        if node.drawing_coord is not None:
            node.drawing_coord.x += off_x
            node.drawing_coord.y += off_y


# ============================================================================
# Main layout orchestrator
# ============================================================================


def create_mapping(graph: AsciiGraph) -> None:
    """Perform the full grid layout.

    1. Place root nodes on the grid
    2. Place child nodes level by level
    3. Compute column widths and row heights
    4. Run A* pathfinding for all edges
    5. Determine label placement
    6. Convert grid coords -> drawing coords
    7. Generate node box drawings
    8. Calculate subgraph bounding boxes
    """
    direction = graph.config.graph_direction
    highest_position_per_level: list[int] = [0] * 100

    # Identify root nodes -- nodes that aren't the target of any edge
    nodes_found: set[str] = set()
    root_nodes: list[AsciiNode] = []

    for node in graph.nodes:
        if node.name not in nodes_found:
            root_nodes.append(node)
        nodes_found.add(node.name)
        for child in _get_children(graph, node):
            nodes_found.add(child.name)

    # In LR mode with both external and subgraph roots, separate them
    # so subgraph roots are placed one level deeper
    has_external_roots = False
    has_subgraph_roots_with_edges = False
    for node in root_nodes:
        if _is_node_in_any_subgraph(graph, node):
            if len(_get_children(graph, node)) > 0:
                has_subgraph_roots_with_edges = True
        else:
            has_external_roots = True
    should_separate = (
        direction == "LR"
        and has_external_roots
        and has_subgraph_roots_with_edges
    )

    if should_separate:
        external_root_nodes = [
            n for n in root_nodes if not _is_node_in_any_subgraph(graph, n)
        ]
        subgraph_root_nodes = [
            n for n in root_nodes if _is_node_in_any_subgraph(graph, n)
        ]
    else:
        external_root_nodes = root_nodes
        subgraph_root_nodes = []

    # Place external root nodes
    for node in external_root_nodes:
        if direction == "LR":
            requested = GridCoord(x=0, y=highest_position_per_level[0])
        else:
            requested = GridCoord(x=highest_position_per_level[0], y=0)
        reserve_spot_in_grid(graph, graph.nodes[node.index], requested)
        highest_position_per_level[0] += 4

    # Place subgraph root nodes at level 4 (one level in from the edge)
    if should_separate and len(subgraph_root_nodes) > 0:
        subgraph_level = 4
        for node in subgraph_root_nodes:
            if direction == "LR":
                requested = GridCoord(
                    x=subgraph_level,
                    y=highest_position_per_level[subgraph_level],
                )
            else:
                requested = GridCoord(
                    x=highest_position_per_level[subgraph_level],
                    y=subgraph_level,
                )
            reserve_spot_in_grid(graph, graph.nodes[node.index], requested)
            highest_position_per_level[subgraph_level] += 4

    # Place child nodes level by level
    for node in graph.nodes:
        gc = node.grid_coord
        assert gc is not None
        if direction == "LR":
            child_level = gc.x + 4
        else:
            child_level = gc.y + 4
        highest_position = highest_position_per_level[child_level]

        for child in _get_children(graph, node):
            if child.grid_coord is not None:
                continue  # already placed

            if direction == "LR":
                requested = GridCoord(x=child_level, y=highest_position)
            else:
                requested = GridCoord(x=highest_position, y=child_level)
            reserve_spot_in_grid(graph, graph.nodes[child.index], requested)
            highest_position_per_level[child_level] = highest_position + 4
            highest_position = highest_position_per_level[child_level]

    # Compute column widths and row heights
    for node in graph.nodes:
        set_column_width(graph, node)

    # Route edges via A* and determine label positions
    for edge in graph.edges:
        determine_path(graph, edge)
        increase_grid_size_for_path(graph, edge.path)
        determine_label_line(graph, edge)

    # Convert grid coords -> drawing coords and generate box drawings
    for node in graph.nodes:
        assert node.grid_coord is not None
        node.drawing_coord = grid_to_drawing_coord(graph, node.grid_coord)
        from .draw import draw_box  # noqa: E402 — lazy to break circular import
        node.drawing = draw_box(node, graph)

    # Set canvas size and compute subgraph bounding boxes
    set_canvas_size_to_grid(graph.canvas, graph.column_width, graph.row_height)
    calculate_subgraph_bounding_boxes(graph)
    offset_drawing_for_subgraphs(graph)


# ============================================================================
# Graph traversal helpers
# ============================================================================


def _get_edges_from_node(graph: AsciiGraph, node: AsciiNode) -> list:
    """Get all edges originating from a node."""
    return [e for e in graph.edges if e.from_node.name == node.name]


def _get_children(graph: AsciiGraph, node: AsciiNode) -> list[AsciiNode]:
    """Get all direct children of a node (targets of outgoing edges)."""
    return [e.to_node for e in _get_edges_from_node(graph, node)]
