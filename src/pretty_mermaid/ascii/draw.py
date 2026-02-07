from __future__ import annotations

# ============================================================================
# ASCII renderer -- drawing operations
#
# Ported from AlexanderGrooff/mermaid-ascii cmd/draw.go + cmd/arrow.go.
# Contains all visual rendering: boxes, lines, arrows, corners,
# subgraphs, labels, and the top-level draw orchestrator.
# ============================================================================

from .types import (
    Canvas,
    DrawingCoord,
    GridCoord,
    Direction,
    AsciiGraph,
    AsciiNode,
    AsciiEdge,
    AsciiSubgraph,
    Up,
    Down,
    Left,
    Right,
    UpperLeft,
    UpperRight,
    LowerLeft,
    LowerRight,
    Middle,
    drawing_coord_equals,
)
from .canvas import mk_canvas, copy_canvas, merge_canvases, draw_text
from .edge_routing import determine_direction, dir_equals
from .grid import grid_to_drawing_coord, line_to_drawing


# ============================================================================
# Box drawing -- renders a node as a bordered rectangle
# ============================================================================


def draw_box(node: AsciiNode, graph: AsciiGraph) -> Canvas:
    """Draw a node box with centered label text.

    Returns a standalone canvas containing just the box.
    Box size is determined by the grid column/row sizes for the node's position.
    """
    gc = node.grid_coord
    assert gc is not None
    use_ascii = graph.config.use_ascii

    # Width spans 2 columns (border + content)
    w = 0
    for i in range(2):
        w += graph.column_width.get(gc.x + i, 0)

    # Height spans 2 rows (border + content)
    h = 0
    for i in range(2):
        h += graph.row_height.get(gc.y + i, 0)

    from_coord = DrawingCoord(x=0, y=0)
    to_coord = DrawingCoord(x=w, y=h)
    box = mk_canvas(max(from_coord.x, to_coord.x), max(from_coord.y, to_coord.y))

    if not use_ascii:
        # Unicode box-drawing characters
        for x in range(from_coord.x + 1, to_coord.x):
            box[x][from_coord.y] = "\u2500"  # ─
        for x in range(from_coord.x + 1, to_coord.x):
            box[x][to_coord.y] = "\u2500"
        for y in range(from_coord.y + 1, to_coord.y):
            box[from_coord.x][y] = "\u2502"  # │
        for y in range(from_coord.y + 1, to_coord.y):
            box[to_coord.x][y] = "\u2502"
        box[from_coord.x][from_coord.y] = "\u250c"  # ┌
        box[to_coord.x][from_coord.y] = "\u2510"    # ┐
        box[from_coord.x][to_coord.y] = "\u2514"    # └
        box[to_coord.x][to_coord.y] = "\u2518"      # ┘
    else:
        # ASCII characters
        for x in range(from_coord.x + 1, to_coord.x):
            box[x][from_coord.y] = "-"
        for x in range(from_coord.x + 1, to_coord.x):
            box[x][to_coord.y] = "-"
        for y in range(from_coord.y + 1, to_coord.y):
            box[from_coord.x][y] = "|"
        for y in range(from_coord.y + 1, to_coord.y):
            box[to_coord.x][y] = "|"
        box[from_coord.x][from_coord.y] = "+"
        box[to_coord.x][from_coord.y] = "+"
        box[from_coord.x][to_coord.y] = "+"
        box[to_coord.x][to_coord.y] = "+"

    # Center the display label inside the box
    label = node.display_label
    text_y = from_coord.y + h // 2
    text_x = from_coord.x + w // 2 - (len(label) + 1) // 2 + 1
    for i in range(len(label)):
        box[text_x + i][text_y] = label[i]

    return box


# ============================================================================
# Multi-section box drawing -- for class and ER diagram nodes
# ============================================================================


def draw_multi_box(
    sections: list[list[str]],
    use_ascii: bool,
    padding: int = 1,
) -> Canvas:
    """Draw a multi-section box with horizontal dividers between sections.

    Used by class diagrams (header | attributes | methods) and ER diagrams
    (header | attributes). Each section is a list of text lines to render
    left-aligned with padding.

    Args:
        sections: List of sections, each section is a list of text lines.
        use_ascii: ``True`` for ASCII chars, ``False`` for Unicode box-drawing.
        padding: Horizontal padding inside the box (default 1).

    Returns:
        A standalone Canvas containing the multi-section box.
    """
    # Compute width: widest line across all sections + 2*padding + 2 border chars
    max_text_width = 0
    for section in sections:
        for line in section:
            max_text_width = max(max_text_width, len(line))
    inner_width = max_text_width + 2 * padding
    box_width = inner_width + 2  # +2 for left/right border

    # Compute height: sum of all section line counts + dividers + 2 border rows
    total_lines = 0
    for section in sections:
        total_lines += max(len(section), 1)  # at least 1 row per section
    num_dividers = len(sections) - 1
    box_height = total_lines + num_dividers + 2  # +2 for top/bottom border

    # Box-drawing characters
    h_line = "-" if use_ascii else "\u2500"   # ─
    v_line = "|" if use_ascii else "\u2502"   # │
    tl = "+" if use_ascii else "\u250c"       # ┌
    tr = "+" if use_ascii else "\u2510"       # ┐
    bl = "+" if use_ascii else "\u2514"       # └
    br = "+" if use_ascii else "\u2518"       # ┘
    div_l = "+" if use_ascii else "\u251c"    # ├
    div_r = "+" if use_ascii else "\u2524"    # ┤

    canvas = mk_canvas(box_width - 1, box_height - 1)

    # Top border
    canvas[0][0] = tl
    for x in range(1, box_width - 1):
        canvas[x][0] = h_line
    canvas[box_width - 1][0] = tr

    # Bottom border
    canvas[0][box_height - 1] = bl
    for x in range(1, box_width - 1):
        canvas[x][box_height - 1] = h_line
    canvas[box_width - 1][box_height - 1] = br

    # Left and right borders (full height)
    for y in range(1, box_height - 1):
        canvas[0][y] = v_line
        canvas[box_width - 1][y] = v_line

    # Render sections with dividers
    row = 1  # current y position (starts after top border)
    for s, section in enumerate(sections):
        lines = section if len(section) > 0 else [""]

        # Draw section text lines
        for line in lines:
            start_x = 1 + padding
            for i, ch in enumerate(line):
                canvas[start_x + i][row] = ch
            row += 1

        # Draw divider after each section except the last
        if s < len(sections) - 1:
            canvas[0][row] = div_l
            for x in range(1, box_width - 1):
                canvas[x][row] = h_line
            canvas[box_width - 1][row] = div_r
            row += 1

    return canvas


# ============================================================================
# Line drawing -- 8-directional lines on the canvas
# ============================================================================


def draw_line(
    canvas: Canvas,
    from_coord: DrawingCoord,
    to_coord: DrawingCoord,
    offset_from: int,
    offset_to: int,
    use_ascii: bool,
) -> list[DrawingCoord]:
    """Draw a line between two drawing coordinates.

    Returns the list of coordinates that were drawn on.
    *offset_from* / *offset_to* control how many cells to skip at the start/end.
    """
    direction = determine_direction(from_coord, to_coord)
    drawn_coords: list[DrawingCoord] = []

    # Horizontal/vertical/diagonal character pairs
    h_char = "-" if use_ascii else "\u2500"  # ─
    v_char = "|" if use_ascii else "\u2502"  # │
    bslash = "\\" if use_ascii else "\u2572"  # ╲
    fslash = "/" if use_ascii else "\u2571"   # ╱

    if dir_equals(direction, Up):
        y = from_coord.y - offset_from
        while y >= to_coord.y - offset_to:
            drawn_coords.append(DrawingCoord(x=from_coord.x, y=y))
            canvas[from_coord.x][y] = v_char
            y -= 1
    elif dir_equals(direction, Down):
        y = from_coord.y + offset_from
        while y <= to_coord.y + offset_to:
            drawn_coords.append(DrawingCoord(x=from_coord.x, y=y))
            canvas[from_coord.x][y] = v_char
            y += 1
    elif dir_equals(direction, Left):
        x = from_coord.x - offset_from
        while x >= to_coord.x - offset_to:
            drawn_coords.append(DrawingCoord(x=x, y=from_coord.y))
            canvas[x][from_coord.y] = h_char
            x -= 1
    elif dir_equals(direction, Right):
        x = from_coord.x + offset_from
        while x <= to_coord.x + offset_to:
            drawn_coords.append(DrawingCoord(x=x, y=from_coord.y))
            canvas[x][from_coord.y] = h_char
            x += 1
    elif dir_equals(direction, UpperLeft):
        x = from_coord.x
        y = from_coord.y - offset_from
        while x >= to_coord.x - offset_to and y >= to_coord.y - offset_to:
            drawn_coords.append(DrawingCoord(x=x, y=y))
            canvas[x][y] = bslash
            x -= 1
            y -= 1
    elif dir_equals(direction, UpperRight):
        x = from_coord.x
        y = from_coord.y - offset_from
        while x <= to_coord.x + offset_to and y >= to_coord.y - offset_to:
            drawn_coords.append(DrawingCoord(x=x, y=y))
            canvas[x][y] = fslash
            x += 1
            y -= 1
    elif dir_equals(direction, LowerLeft):
        x = from_coord.x
        y = from_coord.y + offset_from
        while x >= to_coord.x - offset_to and y <= to_coord.y + offset_to:
            drawn_coords.append(DrawingCoord(x=x, y=y))
            canvas[x][y] = fslash
            x -= 1
            y += 1
    elif dir_equals(direction, LowerRight):
        x = from_coord.x
        y = from_coord.y + offset_from
        while x <= to_coord.x + offset_to and y <= to_coord.y + offset_to:
            drawn_coords.append(DrawingCoord(x=x, y=y))
            canvas[x][y] = bslash
            x += 1
            y += 1

    return drawn_coords


# ============================================================================
# Arrow drawing -- path, corners, arrowheads, box-start junctions, labels
# ============================================================================


def draw_arrow(
    graph: AsciiGraph,
    edge: AsciiEdge,
) -> tuple[Canvas, Canvas, Canvas, Canvas, Canvas]:
    """Draw a complete arrow (edge) between two nodes.

    Returns 5 separate canvases for layered compositing:
    ``(path, box_start, arrow_head, corners, label)``
    """
    if len(edge.path) == 0:
        empty = copy_canvas(graph.canvas)
        return (empty, empty, empty, empty, empty)

    label_canvas = _draw_arrow_label(graph, edge)
    path_canvas, lines_drawn, line_dirs = _draw_path(graph, edge.path)
    box_start_canvas = _draw_box_start(graph, edge.path, lines_drawn[0])
    arrow_head_canvas = _draw_arrow_head(
        graph,
        lines_drawn[len(lines_drawn) - 1],
        line_dirs[len(line_dirs) - 1],
    )
    corners_canvas = _draw_corners(graph, edge.path)

    return (path_canvas, box_start_canvas, arrow_head_canvas, corners_canvas, label_canvas)


def _draw_path(
    graph: AsciiGraph,
    path: list[GridCoord],
) -> tuple[Canvas, list[list[DrawingCoord]], list[Direction]]:
    """Draw the path lines for an edge.

    Returns the canvas, the coordinates drawn for each segment, and the
    direction of each segment.
    """
    canvas = copy_canvas(graph.canvas)
    previous_coord = path[0]
    lines_drawn: list[list[DrawingCoord]] = []
    line_dirs: list[Direction] = []

    for i in range(1, len(path)):
        next_coord = path[i]
        prev_dc = grid_to_drawing_coord(graph, previous_coord)
        next_dc = grid_to_drawing_coord(graph, next_coord)

        if drawing_coord_equals(prev_dc, next_dc):
            previous_coord = next_coord
            continue

        direction = determine_direction(previous_coord, next_coord)
        segment = draw_line(canvas, prev_dc, next_dc, 1, -1, graph.config.use_ascii)
        if len(segment) == 0:
            segment.append(prev_dc)
        lines_drawn.append(segment)
        line_dirs.append(direction)
        previous_coord = next_coord

    return (canvas, lines_drawn, line_dirs)


def _draw_box_start(
    graph: AsciiGraph,
    path: list[GridCoord],
    first_line: list[DrawingCoord],
) -> Canvas:
    """Draw the junction character where an edge exits the source node's box.

    Only applies to Unicode mode (ASCII mode just uses the line characters).
    """
    canvas = copy_canvas(graph.canvas)
    if graph.config.use_ascii:
        return canvas

    from_coord = first_line[0]
    direction = determine_direction(path[0], path[1])

    if dir_equals(direction, Up):
        canvas[from_coord.x][from_coord.y + 1] = "\u2534"      # ┴
    elif dir_equals(direction, Down):
        canvas[from_coord.x][from_coord.y - 1] = "\u252c"      # ┬
    elif dir_equals(direction, Left):
        canvas[from_coord.x + 1][from_coord.y] = "\u2524"      # ┤
    elif dir_equals(direction, Right):
        canvas[from_coord.x - 1][from_coord.y] = "\u251c"      # ├

    return canvas


def _draw_arrow_head(
    graph: AsciiGraph,
    last_line: list[DrawingCoord],
    fallback_dir: Direction,
) -> Canvas:
    """Draw the arrowhead at the end of an edge path.

    Uses triangular Unicode symbols or ASCII symbols (^v<>).
    """
    canvas = copy_canvas(graph.canvas)
    if len(last_line) == 0:
        return canvas

    from_coord = last_line[0]
    last_pos = last_line[len(last_line) - 1]
    direction = determine_direction(from_coord, last_pos)
    if len(last_line) == 1 or dir_equals(direction, Middle):
        direction = fallback_dir

    if not graph.config.use_ascii:
        char = _unicode_arrow_char(direction, fallback_dir)
    else:
        char = _ascii_arrow_char(direction, fallback_dir)

    canvas[last_pos.x][last_pos.y] = char
    return canvas


def _unicode_arrow_char(direction: Direction, fallback_dir: Direction) -> str:
    """Pick the Unicode arrowhead character for a direction."""
    if dir_equals(direction, Up):
        return "\u25b2"      # ▲
    if dir_equals(direction, Down):
        return "\u25bc"      # ▼
    if dir_equals(direction, Left):
        return "\u25c4"      # ◄
    if dir_equals(direction, Right):
        return "\u25ba"      # ►
    if dir_equals(direction, UpperRight):
        return "\u25e5"      # ◥
    if dir_equals(direction, UpperLeft):
        return "\u25e4"      # ◤
    if dir_equals(direction, LowerRight):
        return "\u25e2"      # ◢
    if dir_equals(direction, LowerLeft):
        return "\u25e3"      # ◣

    # Fallback
    if dir_equals(fallback_dir, Up):
        return "\u25b2"      # ▲
    if dir_equals(fallback_dir, Down):
        return "\u25bc"      # ▼
    if dir_equals(fallback_dir, Left):
        return "\u25c4"      # ◄
    if dir_equals(fallback_dir, Right):
        return "\u25ba"      # ►
    if dir_equals(fallback_dir, UpperRight):
        return "\u25e5"      # ◥
    if dir_equals(fallback_dir, UpperLeft):
        return "\u25e4"      # ◤
    if dir_equals(fallback_dir, LowerRight):
        return "\u25e2"      # ◢
    if dir_equals(fallback_dir, LowerLeft):
        return "\u25e3"      # ◣

    return "\u25cf"          # ●


def _ascii_arrow_char(direction: Direction, fallback_dir: Direction) -> str:
    """Pick the ASCII arrowhead character for a direction."""
    if dir_equals(direction, Up):
        return "^"
    if dir_equals(direction, Down):
        return "v"
    if dir_equals(direction, Left):
        return "<"
    if dir_equals(direction, Right):
        return ">"

    # Fallback
    if dir_equals(fallback_dir, Up):
        return "^"
    if dir_equals(fallback_dir, Down):
        return "v"
    if dir_equals(fallback_dir, Left):
        return "<"
    if dir_equals(fallback_dir, Right):
        return ">"

    return "*"


def _draw_corners(graph: AsciiGraph, path: list[GridCoord]) -> Canvas:
    """Draw corner characters at path bends (where the direction changes).

    Uses unicode box-drawing corners in Unicode mode, ``+`` in ASCII mode.
    """
    canvas = copy_canvas(graph.canvas)

    for idx in range(1, len(path) - 1):
        coord = path[idx]
        dc = grid_to_drawing_coord(graph, coord)
        prev_dir = determine_direction(path[idx - 1], coord)
        next_dir = determine_direction(coord, path[idx + 1])

        if not graph.config.use_ascii:
            if (dir_equals(prev_dir, Right) and dir_equals(next_dir, Down)) or (
                dir_equals(prev_dir, Up) and dir_equals(next_dir, Left)
            ):
                corner = "\u2510"  # ┐
            elif (dir_equals(prev_dir, Right) and dir_equals(next_dir, Up)) or (
                dir_equals(prev_dir, Down) and dir_equals(next_dir, Left)
            ):
                corner = "\u2518"  # ┘
            elif (dir_equals(prev_dir, Left) and dir_equals(next_dir, Down)) or (
                dir_equals(prev_dir, Up) and dir_equals(next_dir, Right)
            ):
                corner = "\u250c"  # ┌
            elif (dir_equals(prev_dir, Left) and dir_equals(next_dir, Up)) or (
                dir_equals(prev_dir, Down) and dir_equals(next_dir, Right)
            ):
                corner = "\u2514"  # └
            else:
                corner = "+"
        else:
            corner = "+"

        canvas[dc.x][dc.y] = corner

    return canvas


def _draw_arrow_label(graph: AsciiGraph, edge: AsciiEdge) -> Canvas:
    """Draw edge label text centered on the widest path segment."""
    canvas = copy_canvas(graph.canvas)
    if len(edge.text) == 0:
        return canvas

    drawing_line = line_to_drawing(graph, edge.label_line)
    _draw_text_on_line(canvas, drawing_line, edge.text)
    return canvas


def _draw_text_on_line(
    canvas: Canvas,
    line: list[DrawingCoord],
    label: str,
) -> None:
    """Draw text centered on a line segment defined by two drawing coordinates."""
    if len(line) < 2:
        return
    min_x = min(line[0].x, line[1].x)
    max_x = max(line[0].x, line[1].x)
    min_y = min(line[0].y, line[1].y)
    max_y = max(line[0].y, line[1].y)
    middle_x = min_x + (max_x - min_x) // 2
    middle_y = min_y + (max_y - min_y) // 2
    start_x = middle_x - len(label) // 2
    draw_text(canvas, DrawingCoord(x=start_x, y=middle_y), label)


# ============================================================================
# Subgraph drawing
# ============================================================================


def draw_subgraph_box(sg: AsciiSubgraph, graph: AsciiGraph) -> Canvas:
    """Draw a subgraph border rectangle."""
    width = sg.max_x - sg.min_x
    height = sg.max_y - sg.min_y
    if width <= 0 or height <= 0:
        return mk_canvas(0, 0)

    from_coord = DrawingCoord(x=0, y=0)
    to_coord = DrawingCoord(x=width, y=height)
    canvas = mk_canvas(width, height)

    if not graph.config.use_ascii:
        for x in range(from_coord.x + 1, to_coord.x):
            canvas[x][from_coord.y] = "\u2500"  # ─
        for x in range(from_coord.x + 1, to_coord.x):
            canvas[x][to_coord.y] = "\u2500"
        for y in range(from_coord.y + 1, to_coord.y):
            canvas[from_coord.x][y] = "\u2502"  # │
        for y in range(from_coord.y + 1, to_coord.y):
            canvas[to_coord.x][y] = "\u2502"
        canvas[from_coord.x][from_coord.y] = "\u250c"  # ┌
        canvas[to_coord.x][from_coord.y] = "\u2510"    # ┐
        canvas[from_coord.x][to_coord.y] = "\u2514"    # └
        canvas[to_coord.x][to_coord.y] = "\u2518"      # ┘
    else:
        for x in range(from_coord.x + 1, to_coord.x):
            canvas[x][from_coord.y] = "-"
        for x in range(from_coord.x + 1, to_coord.x):
            canvas[x][to_coord.y] = "-"
        for y in range(from_coord.y + 1, to_coord.y):
            canvas[from_coord.x][y] = "|"
        for y in range(from_coord.y + 1, to_coord.y):
            canvas[to_coord.x][y] = "|"
        canvas[from_coord.x][from_coord.y] = "+"
        canvas[to_coord.x][from_coord.y] = "+"
        canvas[from_coord.x][to_coord.y] = "+"
        canvas[to_coord.x][to_coord.y] = "+"

    return canvas


def draw_subgraph_label(
    sg: AsciiSubgraph,
    graph: AsciiGraph,
) -> tuple[Canvas, DrawingCoord]:
    """Draw a subgraph label centered in its header area."""
    width = sg.max_x - sg.min_x
    height = sg.max_y - sg.min_y
    if width <= 0 or height <= 0:
        return (mk_canvas(0, 0), DrawingCoord(x=0, y=0))

    canvas = mk_canvas(width, height)
    label_y = 1  # second row inside the subgraph box
    label_x = width // 2 - len(sg.name) // 2
    if label_x < 1:
        label_x = 1

    for i in range(len(sg.name)):
        if label_x + i < width:
            canvas[label_x + i][label_y] = sg.name[i]

    return (canvas, DrawingCoord(x=sg.min_x, y=sg.min_y))


# ============================================================================
# Top-level draw orchestrator
# ============================================================================


def _sort_subgraphs_by_depth(subgraphs: list[AsciiSubgraph]) -> list[AsciiSubgraph]:
    """Sort subgraphs by nesting depth (shallowest first) for correct layered rendering."""

    def _get_depth(sg: AsciiSubgraph) -> int:
        return 0 if sg.parent is None else 1 + _get_depth(sg.parent)

    sorted_sgs = list(subgraphs)
    sorted_sgs.sort(key=_get_depth)
    return sorted_sgs


def draw_graph(graph: AsciiGraph) -> Canvas:
    """Main draw function -- renders the entire graph onto the canvas.

    Drawing order matters for correct layering:

    1. Subgraph borders (bottom layer)
    2. Node boxes
    3. Edge paths (lines)
    4. Edge corners
    5. Arrowheads
    6. Box-start junctions
    7. Edge labels
    8. Subgraph labels (top layer)
    """
    use_ascii = graph.config.use_ascii

    # Draw subgraph borders
    sorted_sgs = _sort_subgraphs_by_depth(graph.subgraphs)
    for sg in sorted_sgs:
        sg_canvas = draw_subgraph_box(sg, graph)
        offset = DrawingCoord(x=sg.min_x, y=sg.min_y)
        graph.canvas = merge_canvases(graph.canvas, offset, use_ascii, sg_canvas)

    # Draw node boxes
    for node in graph.nodes:
        if not node.drawn and node.drawing_coord is not None and node.drawing is not None:
            graph.canvas = merge_canvases(
                graph.canvas, node.drawing_coord, use_ascii, node.drawing,
            )
            node.drawn = True

    # Collect all edge drawing layers
    line_canvases: list[Canvas] = []
    corner_canvases: list[Canvas] = []
    arrow_head_canvases: list[Canvas] = []
    box_start_canvases: list[Canvas] = []
    label_canvases: list[Canvas] = []

    for edge in graph.edges:
        path_c, box_start_c, arrow_head_c, corners_c, label_c = draw_arrow(graph, edge)
        line_canvases.append(path_c)
        corner_canvases.append(corners_c)
        arrow_head_canvases.append(arrow_head_c)
        box_start_canvases.append(box_start_c)
        label_canvases.append(label_c)

    # Merge edge layers in order
    zero = DrawingCoord(x=0, y=0)
    graph.canvas = merge_canvases(graph.canvas, zero, use_ascii, *line_canvases)
    graph.canvas = merge_canvases(graph.canvas, zero, use_ascii, *corner_canvases)
    graph.canvas = merge_canvases(graph.canvas, zero, use_ascii, *arrow_head_canvases)
    graph.canvas = merge_canvases(graph.canvas, zero, use_ascii, *box_start_canvases)
    graph.canvas = merge_canvases(graph.canvas, zero, use_ascii, *label_canvases)

    # Draw subgraph labels last (on top)
    for sg in graph.subgraphs:
        if len(sg.nodes) == 0:
            continue
        label_canvas, offset = draw_subgraph_label(sg, graph)
        graph.canvas = merge_canvases(graph.canvas, offset, use_ascii, label_canvas)

    return graph.canvas
