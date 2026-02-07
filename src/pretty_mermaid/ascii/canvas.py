from __future__ import annotations

# ============================================================================
# ASCII renderer -- 2D text canvas
#
# Ported from AlexanderGrooff/mermaid-ascii cmd/draw.go.
# The canvas is a column-major 2D array of single-character strings.
# canvas[x][y] gives the character at column x, row y.
# ============================================================================

from .types import Canvas, DrawingCoord


def mk_canvas(x: int, y: int) -> Canvas:
    """Create a blank canvas filled with spaces.

    Dimensions are inclusive: mk_canvas(3, 2) creates a 4x3 grid
    (indices 0..3, 0..2).
    """
    canvas: Canvas = []
    for _ in range(x + 1):
        col: list[str] = [" "] * (y + 1)
        canvas.append(col)
    return canvas


def copy_canvas(source: Canvas) -> Canvas:
    """Create a blank canvas with the same dimensions as the given canvas."""
    max_x, max_y = get_canvas_size(source)
    return mk_canvas(max_x, max_y)


def get_canvas_size(canvas: Canvas) -> tuple[int, int]:
    """Return (max_x, max_y) -- the highest valid indices in each dimension."""
    max_x = len(canvas) - 1
    max_y = (len(canvas[0]) if canvas else 1) - 1
    return (max_x, max_y)


def increase_size(canvas: Canvas, new_x: int, new_y: int) -> Canvas:
    """Grow the canvas to fit at least (new_x, new_y), preserving content.

    Mutates the canvas in place and returns it.
    """
    curr_x, curr_y = get_canvas_size(canvas)
    target_x = max(new_x, curr_x)
    target_y = max(new_y, curr_y)
    grown = mk_canvas(target_x, target_y)
    for x in range(len(grown)):
        for y in range(len(grown[0])):
            if x < len(canvas) and y < len(canvas[0]):
                grown[x][y] = canvas[x][y]
    # Mutate in place
    canvas.clear()
    canvas.extend(grown)
    return canvas


# ============================================================================
# Junction merging -- Unicode box-drawing character compositing
# ============================================================================

_JUNCTION_CHARS = frozenset(
    "─│┌┐└┘├┤┬┴┼╴╵╶╷"
)


def is_junction_char(c: str) -> bool:
    return c in _JUNCTION_CHARS


_JUNCTION_MAP: dict[str, dict[str, str]] = {
    "─": {"│": "┼", "┌": "┬", "┐": "┬", "└": "┴", "┘": "┴", "├": "┼", "┤": "┼", "┬": "┬", "┴": "┴"},
    "│": {"─": "┼", "┌": "├", "┐": "┤", "└": "├", "┘": "┤", "├": "├", "┤": "┤", "┬": "┼", "┴": "┼"},
    "┌": {"─": "┬", "│": "├", "┐": "┬", "└": "├", "┘": "┼", "├": "├", "┤": "┼", "┬": "┬", "┴": "┼"},
    "┐": {"─": "┬", "│": "┤", "┌": "┬", "└": "┼", "┘": "┤", "├": "┼", "┤": "┤", "┬": "┬", "┴": "┼"},
    "└": {"─": "┴", "│": "├", "┌": "├", "┐": "┼", "┘": "┴", "├": "├", "┤": "┼", "┬": "┼", "┴": "┴"},
    "┘": {"─": "┴", "│": "┤", "┌": "┼", "┐": "┤", "└": "┴", "├": "┼", "┤": "┤", "┬": "┼", "┴": "┴"},
    "├": {"─": "┼", "│": "├", "┌": "├", "┐": "┼", "└": "├", "┘": "┼", "┤": "┼", "┬": "┼", "┴": "┼"},
    "┤": {"─": "┼", "│": "┤", "┌": "┼", "┐": "┤", "└": "┼", "┘": "┤", "├": "┼", "┬": "┼", "┴": "┼"},
    "┬": {"─": "┬", "│": "┼", "┌": "┬", "┐": "┬", "└": "┼", "┘": "┼", "├": "┼", "┤": "┼", "┴": "┼"},
    "┴": {"─": "┴", "│": "┼", "┌": "┼", "┐": "┼", "└": "┴", "┘": "┴", "├": "┼", "┤": "┼", "┬": "┼"},
}


def merge_junctions(c1: str, c2: str) -> str:
    """When two junction characters overlap during canvas merging,
    resolve them to the correct combined junction.
    E.g., '-' overlapping '|' becomes '+'.
    """
    row = _JUNCTION_MAP.get(c1)
    if row is not None:
        merged = row.get(c2)
        if merged is not None:
            return merged
    return c1


# ============================================================================
# Canvas merging -- composite multiple canvases with offset
# ============================================================================


def merge_canvases(
    base: Canvas,
    offset: DrawingCoord,
    use_ascii: bool,
    *overlays: Canvas,
) -> Canvas:
    """Merge overlay canvases onto a base canvas at the given offset.

    Non-space characters in overlays overwrite the base.
    When both characters are Unicode junction chars, they are merged
    intelligently.
    """
    max_x, max_y = get_canvas_size(base)
    for overlay in overlays:
        o_x, o_y = get_canvas_size(overlay)
        max_x = max(max_x, o_x + offset.x)
        max_y = max(max_y, o_y + offset.y)

    merged = mk_canvas(max_x, max_y)

    # Copy base
    for x in range(max_x + 1):
        for y in range(max_y + 1):
            if x < len(base) and y < len(base[0]):
                merged[x][y] = base[x][y]

    # Apply overlays
    for overlay in overlays:
        for x in range(len(overlay)):
            for y in range(len(overlay[0])):
                c = overlay[x][y]
                if c != " ":
                    mx = x + offset.x
                    my = y + offset.y
                    current = merged[mx][my]
                    if not use_ascii and is_junction_char(c) and is_junction_char(current):
                        merged[mx][my] = merge_junctions(current, c)
                    else:
                        merged[mx][my] = c

    return merged


# ============================================================================
# Canvas -> string conversion
# ============================================================================


def canvas_to_string(canvas: Canvas) -> str:
    """Convert the canvas to a multi-line string (row by row, left to right)."""
    max_x, max_y = get_canvas_size(canvas)
    lines: list[str] = []
    for y in range(max_y + 1):
        line = ""
        for x in range(max_x + 1):
            line += canvas[x][y]
        lines.append(line)
    return "\n".join(lines)


# ============================================================================
# Canvas vertical flip -- used for BT (bottom-to-top) direction support.
#
# The ASCII renderer lays out graphs top-down (TD). For BT direction, we
# flip the finished canvas vertically and remap directional characters so
# arrows point upward and corners are mirrored correctly.
# ============================================================================

_VERTICAL_FLIP_MAP: dict[str, str] = {
    # Unicode arrows
    "\u25b2": "\u25bc", "\u25bc": "\u25b2",  # blacktriangle up/down
    "\u25e4": "\u25e3", "\u25e3": "\u25e4",
    "\u25e5": "\u25e2", "\u25e2": "\u25e5",
    # ASCII arrows
    "^": "v", "v": "^",
    # Unicode corners
    "\u250c": "\u2514", "\u2514": "\u250c",  # top-left <-> bottom-left
    "\u2510": "\u2518", "\u2518": "\u2510",  # top-right <-> bottom-right
    # Unicode junctions (T-pieces flip vertically)
    "\u252c": "\u2534", "\u2534": "\u252c",  # top-T <-> bottom-T
    # Box-start junctions (exit points from node boxes)
    "\u2575": "\u2577", "\u2577": "\u2575",
}


def flip_canvas_vertically(canvas: Canvas) -> Canvas:
    """Flip the canvas vertically (mirror across the horizontal center).

    Reverses row order within each column and remaps directional characters
    (arrows, corners, junctions) so they point the correct way after flip.

    Used to transform a TD-rendered canvas into BT output.
    Mutates the canvas in place and returns it.
    """
    # Reverse each column array (Y-axis flip in column-major layout)
    for col in canvas:
        col.reverse()

    # Remap directional characters that change meaning after vertical flip
    for col in canvas:
        for y in range(len(col)):
            flipped = _VERTICAL_FLIP_MAP.get(col[y])
            if flipped is not None:
                col[y] = flipped

    return canvas


def draw_text(canvas: Canvas, start: DrawingCoord, text: str) -> None:
    """Draw text string onto the canvas starting at the given coordinate."""
    increase_size(canvas, start.x + len(text), start.y)
    for i, ch in enumerate(text):
        canvas[start.x + i][start.y] = ch


def set_canvas_size_to_grid(
    canvas: Canvas,
    column_width: dict[int, int],
    row_height: dict[int, int],
) -> None:
    """Set the canvas size to fit all grid columns and rows.

    Called after layout to ensure the canvas covers the full drawing area.
    """
    max_x = 0
    max_y = 0
    for w in column_width.values():
        max_x += w
    for h in row_height.values():
        max_y += h
    increase_size(canvas, max_x - 1, max_y - 1)
