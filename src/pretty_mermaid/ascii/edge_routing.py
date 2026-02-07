from __future__ import annotations

# ============================================================================
# ASCII renderer -- direction system and edge path determination
#
# Ported from AlexanderGrooff/mermaid-ascii cmd/direction.go + cmd/mapping_edge.go.
# Handles direction constants, edge attachment point selection,
# and dual-path comparison for optimal edge routing.
# ============================================================================

from typing import Optional

from .types import (
    GridCoord,
    Direction,
    AsciiEdge,
    AsciiGraph,
    Up,
    Down,
    Left,
    Right,
    UpperRight,
    UpperLeft,
    LowerRight,
    LowerLeft,
    Middle,
    grid_coord_direction,
)
from .pathfinder import get_path, merge_path


# ============================================================================
# Direction utilities
# ============================================================================


def get_opposite(d: Direction) -> Direction:
    """Return the opposite direction."""
    if d == Up:
        return Down
    if d == Down:
        return Up
    if d == Left:
        return Right
    if d == Right:
        return Left
    if d == UpperRight:
        return LowerLeft
    if d == UpperLeft:
        return LowerRight
    if d == LowerRight:
        return UpperLeft
    if d == LowerLeft:
        return UpperRight
    return Middle


def dir_equals(a: Direction, b: Direction) -> bool:
    """Compare directions by value (not reference)."""
    return a.x == b.x and a.y == b.y


def determine_direction(
    from_coord: GridCoord | Direction,
    to_coord: GridCoord | Direction,
) -> Direction:
    """Determine 8-way direction from one coordinate to another.

    Uses the coordinate difference to pick one of 8 cardinal/ordinal directions.
    Works with any object that has ``.x`` and ``.y`` attributes.
    """
    if from_coord.x == to_coord.x:
        return Down if from_coord.y < to_coord.y else Up
    elif from_coord.y == to_coord.y:
        return Right if from_coord.x < to_coord.x else Left
    elif from_coord.x < to_coord.x:
        return LowerRight if from_coord.y < to_coord.y else UpperRight
    else:
        return LowerLeft if from_coord.y < to_coord.y else UpperLeft


# ============================================================================
# Start/end direction selection for edges
# ============================================================================


def _self_reference_direction(
    graph_direction: str,
) -> tuple[Direction, Direction, Direction, Direction]:
    """Self-reference routing (node points to itself)."""
    if graph_direction == "LR":
        return (Right, Down, Down, Right)
    return (Down, Right, Right, Down)


def determine_start_and_end_dir(
    edge: AsciiEdge,
    graph_direction: str,
) -> tuple[Direction, Direction, Direction, Direction]:
    """Determine preferred and alternative start/end directions for an edge.

    Returns ``(preferred_start, preferred_end, alternative_start, alternative_end)``.

    The edge routing tries both pairs and picks the shorter path.
    Direction selection depends on relative node positions and graph direction (LR vs TD).
    """
    if edge.from_node is edge.to_node:
        return _self_reference_direction(graph_direction)

    assert edge.from_node.grid_coord is not None
    assert edge.to_node.grid_coord is not None
    d = determine_direction(edge.from_node.grid_coord, edge.to_node.grid_coord)

    is_backwards: bool
    if graph_direction == "LR":
        is_backwards = (
            dir_equals(d, Left)
            or dir_equals(d, UpperLeft)
            or dir_equals(d, LowerLeft)
        )
    else:
        is_backwards = (
            dir_equals(d, Up)
            or dir_equals(d, UpperLeft)
            or dir_equals(d, UpperRight)
        )

    if dir_equals(d, LowerRight):
        if graph_direction == "LR":
            preferred_dir = Down
            preferred_opposite_dir = Left
            alternative_dir = Right
            alternative_opposite_dir = Up
        else:
            preferred_dir = Right
            preferred_opposite_dir = Up
            alternative_dir = Down
            alternative_opposite_dir = Left
    elif dir_equals(d, UpperRight):
        if graph_direction == "LR":
            preferred_dir = Up
            preferred_opposite_dir = Left
            alternative_dir = Right
            alternative_opposite_dir = Down
        else:
            preferred_dir = Right
            preferred_opposite_dir = Down
            alternative_dir = Up
            alternative_opposite_dir = Left
    elif dir_equals(d, LowerLeft):
        if graph_direction == "LR":
            preferred_dir = Down
            preferred_opposite_dir = Down
            alternative_dir = Left
            alternative_opposite_dir = Up
        else:
            preferred_dir = Left
            preferred_opposite_dir = Up
            alternative_dir = Down
            alternative_opposite_dir = Right
    elif dir_equals(d, UpperLeft):
        if graph_direction == "LR":
            preferred_dir = Down
            preferred_opposite_dir = Down
            alternative_dir = Left
            alternative_opposite_dir = Down
        else:
            preferred_dir = Right
            preferred_opposite_dir = Right
            alternative_dir = Up
            alternative_opposite_dir = Right
    elif is_backwards:
        if graph_direction == "LR" and dir_equals(d, Left):
            preferred_dir = Down
            preferred_opposite_dir = Down
            alternative_dir = Left
            alternative_opposite_dir = Right
        elif graph_direction == "TD" and dir_equals(d, Up):
            preferred_dir = Right
            preferred_opposite_dir = Right
            alternative_dir = Up
            alternative_opposite_dir = Down
        else:
            preferred_dir = d
            preferred_opposite_dir = get_opposite(d)
            alternative_dir = d
            alternative_opposite_dir = get_opposite(d)
    else:
        # Default: go in the natural direction
        preferred_dir = d
        preferred_opposite_dir = get_opposite(d)
        alternative_dir = d
        alternative_opposite_dir = get_opposite(d)

    return (preferred_dir, preferred_opposite_dir, alternative_dir, alternative_opposite_dir)


# ============================================================================
# Edge path determination
# ============================================================================


def determine_path(graph: AsciiGraph, edge: AsciiEdge) -> None:
    """Determine the path for an edge by trying two candidate routes (preferred + alternative)
    and picking the shorter one. Sets ``edge.path``, ``edge.start_dir``, ``edge.end_dir``.
    """
    (
        preferred_dir,
        preferred_opposite_dir,
        alternative_dir,
        alternative_opposite_dir,
    ) = determine_start_and_end_dir(edge, graph.config.graph_direction)

    assert edge.from_node.grid_coord is not None
    assert edge.to_node.grid_coord is not None

    # Try preferred path
    pref_from = grid_coord_direction(edge.from_node.grid_coord, preferred_dir)
    pref_to = grid_coord_direction(edge.to_node.grid_coord, preferred_opposite_dir)
    preferred_path = get_path(graph.grid, pref_from, pref_to)

    if preferred_path is None:
        # No preferred path found -- use alternative
        edge.start_dir = alternative_dir
        edge.end_dir = alternative_opposite_dir
        edge.path = []
        return

    preferred_path = merge_path(preferred_path)

    # Try alternative path
    alt_from = grid_coord_direction(edge.from_node.grid_coord, alternative_dir)
    alt_to = grid_coord_direction(edge.to_node.grid_coord, alternative_opposite_dir)
    alternative_path = get_path(graph.grid, alt_from, alt_to)

    if alternative_path is None:
        # Only preferred path works
        edge.start_dir = preferred_dir
        edge.end_dir = preferred_opposite_dir
        edge.path = preferred_path
        return

    alternative_path = merge_path(alternative_path)

    # Pick the shorter path
    if len(preferred_path) <= len(alternative_path):
        edge.start_dir = preferred_dir
        edge.end_dir = preferred_opposite_dir
        edge.path = preferred_path
    else:
        edge.start_dir = alternative_dir
        edge.end_dir = alternative_opposite_dir
        edge.path = alternative_path


def determine_label_line(graph: AsciiGraph, edge: AsciiEdge) -> None:
    """Find the best line segment in an edge's path to place a label on.

    Picks the first segment wide enough for the label, or the widest segment overall.
    Also increases the column width at the label position to fit the text.
    """
    if len(edge.text) == 0:
        return

    len_label = len(edge.text)
    prev_step = edge.path[0]
    largest_line: tuple[GridCoord, GridCoord] = (prev_step, edge.path[1])
    largest_line_size = 0

    for i in range(1, len(edge.path)):
        step = edge.path[i]
        line = (prev_step, step)
        line_width = _calculate_line_width(graph, line)

        if line_width >= len_label:
            largest_line = line
            break
        elif line_width > largest_line_size:
            largest_line_size = line_width
            largest_line = line

        prev_step = step

    # Ensure column at midpoint is wide enough for the label
    min_x = min(largest_line[0].x, largest_line[1].x)
    max_x = max(largest_line[0].x, largest_line[1].x)
    middle_x = min_x + (max_x - min_x) // 2

    current = graph.column_width.get(middle_x, 0)
    graph.column_width[middle_x] = max(current, len_label + 2)

    edge.label_line = [largest_line[0], largest_line[1]]


def _calculate_line_width(
    graph: AsciiGraph,
    line: tuple[GridCoord, GridCoord],
) -> int:
    """Calculate the total character width of a line segment by summing column widths."""
    total = 0
    start_x = min(line[0].x, line[1].x)
    end_x = max(line[0].x, line[1].x)
    for x in range(start_x, end_x + 1):
        total += graph.column_width.get(x, 0)
    return total
