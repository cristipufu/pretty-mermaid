from __future__ import annotations

# ============================================================================
# ASCII renderer -- type definitions
#
# Ported from AlexanderGrooff/mermaid-ascii (Go).
# These types model the grid-based coordinate system, 2D text canvas,
# and graph structures used by the ASCII/Unicode renderer.
# ============================================================================

from dataclasses import dataclass, field
from typing import Literal

# ============================================================================
# Coordinate types
# ============================================================================


@dataclass(slots=True)
class GridCoord:
    """Logical grid coordinate -- nodes occupy 3x3 blocks on this grid."""

    x: int
    y: int


@dataclass(slots=True)
class DrawingCoord:
    """Character-level coordinate on the 2D text canvas."""

    x: int
    y: int


# ============================================================================
# Direction constants
#
# Model positions on a node's 3x3 grid block.
# Each node occupies grid cells [x..x+2, y..y+2].
# Directions are offsets into that block, used for edge attachment points.
#
#   (0,0) UL   (1,0) Up   (2,0) UR
#   (0,1) Left (1,1) Mid  (2,1) Right
#   (0,2) LL   (1,2) Down (2,2) LR
# ============================================================================


@dataclass(slots=True, frozen=True)
class Direction:
    x: int
    y: int


Up = Direction(x=1, y=0)
Down = Direction(x=1, y=2)
Left = Direction(x=0, y=1)
Right = Direction(x=2, y=1)
UpperRight = Direction(x=2, y=0)
UpperLeft = Direction(x=0, y=0)
LowerRight = Direction(x=2, y=2)
LowerLeft = Direction(x=0, y=2)
Middle = Direction(x=1, y=1)

ALL_DIRECTIONS: tuple[Direction, ...] = (
    Up, Down, Left, Right, UpperRight, UpperLeft, LowerRight, LowerLeft, Middle,
)

# ============================================================================
# Canvas type alias
# ============================================================================

Canvas = list[list[str]]
"""2D text canvas -- column-major (canvas[x][y]).
Each cell holds a single character (or space)."""

# ============================================================================
# Graph structures
# ============================================================================


@dataclass(slots=True)
class AsciiStyleClass:
    """Style class for colored node text (ported from Go's classDef)."""

    name: str
    styles: dict[str, str]


EMPTY_STYLE = AsciiStyleClass(name="", styles={})


@dataclass(slots=True)
class AsciiNode:
    """A node in the ASCII graph, positioned on the grid."""

    # Unique identity key -- the original node ID from the parser (e.g. "A", "B").
    name: str
    # Human-readable label for rendering inside the box (e.g. "Web Server").
    display_label: str
    index: int
    grid_coord: GridCoord | None = None
    drawing_coord: DrawingCoord | None = None
    drawing: Canvas | None = None
    drawn: bool = False
    style_class_name: str = ""
    style_class: AsciiStyleClass = field(
        default_factory=lambda: AsciiStyleClass(name="", styles={}),
    )


@dataclass(slots=True)
class AsciiEdge:
    """An edge in the ASCII graph, with a routed path."""

    from_node: AsciiNode
    to_node: AsciiNode
    text: str
    path: list[GridCoord] = field(default_factory=list)
    label_line: list[GridCoord] = field(default_factory=list)
    start_dir: Direction = field(default_factory=lambda: Direction(x=0, y=0))
    end_dir: Direction = field(default_factory=lambda: Direction(x=0, y=0))


@dataclass(slots=True)
class AsciiSubgraph:
    """A subgraph container with bounding box for rendering."""

    name: str
    nodes: list[AsciiNode] = field(default_factory=list)
    parent: AsciiSubgraph | None = None
    children: list[AsciiSubgraph] = field(default_factory=list)
    min_x: int = 0
    min_y: int = 0
    max_x: int = 0
    max_y: int = 0


GraphDirection = Literal["LR", "TD"]


@dataclass(slots=True)
class AsciiConfig:
    """Configuration for ASCII rendering."""

    # true = ASCII chars (+,-,|), false = Unicode box-drawing. Default: false
    use_ascii: bool = False
    # Horizontal spacing between nodes. Default: 5
    padding_x: int = 5
    # Vertical spacing between nodes. Default: 5
    padding_y: int = 5
    # Padding inside node boxes. Default: 1
    box_border_padding: int = 1
    # Graph direction: "LR" or "TD".
    graph_direction: GraphDirection = "TD"


@dataclass(slots=True)
class AsciiGraph:
    """Full ASCII graph state used during layout and rendering."""

    nodes: list[AsciiNode]
    edges: list[AsciiEdge]
    canvas: Canvas
    # Grid occupancy map -- maps "x,y" keys to node references.
    grid: dict[str, AsciiNode] = field(default_factory=dict)
    column_width: dict[int, int] = field(default_factory=dict)
    row_height: dict[int, int] = field(default_factory=dict)
    subgraphs: list[AsciiSubgraph] = field(default_factory=list)
    config: AsciiConfig = field(default_factory=AsciiConfig)
    # Offset applied to all drawing coords to accommodate subgraph borders.
    offset_x: int = 0
    offset_y: int = 0


# ============================================================================
# Coordinate helpers
# ============================================================================


def grid_coord_equals(a: GridCoord, b: GridCoord) -> bool:
    return a.x == b.x and a.y == b.y


def drawing_coord_equals(a: DrawingCoord, b: DrawingCoord) -> bool:
    return a.x == b.x and a.y == b.y


def grid_coord_direction(c: GridCoord, d: Direction) -> GridCoord:
    """Apply a direction offset to a grid coordinate (move into the 3x3 block)."""
    return GridCoord(x=c.x + d.x, y=c.y + d.y)


def grid_key(c: GridCoord) -> str:
    """Key for storing GridCoord in a dict."""
    return f"{c.x},{c.y}"
