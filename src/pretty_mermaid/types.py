from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ============================================================================
# Parsed graph — logical structure extracted from Mermaid text
# ============================================================================

Direction = Literal["TD", "TB", "LR", "BT", "RL"]

NodeShape = Literal[
    "rectangle",
    "rounded",
    "diamond",
    "stadium",
    "circle",
    # Batch 1
    "subroutine",     # [[text]]
    "doublecircle",   # (((text)))
    "hexagon",        # {{text}}
    # Batch 2
    "cylinder",       # [(text)]
    "asymmetric",     # >text]
    "trapezoid",      # [/text\]
    "trapezoid-alt",  # [\text/]
    # Batch 3 state diagram pseudostates
    "state-start",    # filled circle
    "state-end",      # bullseye circle
]

EdgeStyle = Literal["solid", "dotted", "thick"]


@dataclass(slots=True)
class MermaidNode:
    id: str
    label: str
    shape: NodeShape


@dataclass(slots=True)
class MermaidEdge:
    source: str
    target: str
    label: str | None
    style: EdgeStyle
    has_arrow_start: bool
    has_arrow_end: bool


@dataclass(slots=True)
class MermaidSubgraph:
    id: str
    label: str
    node_ids: list[str]
    children: list[MermaidSubgraph]
    direction: Direction | None = None


@dataclass(slots=True)
class MermaidGraph:
    direction: Direction
    nodes: dict[str, MermaidNode]
    edges: list[MermaidEdge]
    subgraphs: list[MermaidSubgraph]
    class_defs: dict[str, dict[str, str]]
    class_assignments: dict[str, str]
    node_styles: dict[str, dict[str, str]]


# ============================================================================
# Positioned graph — after layout, ready for SVG rendering
# ============================================================================

@dataclass(slots=True)
class Point:
    x: float
    y: float


@dataclass(slots=True)
class PositionedNode:
    id: str
    label: str
    shape: NodeShape
    x: float
    y: float
    width: float
    height: float
    inline_style: dict[str, str] | None = None


@dataclass(slots=True)
class PositionedEdge:
    source: str
    target: str
    label: str | None
    style: EdgeStyle
    has_arrow_start: bool
    has_arrow_end: bool
    points: list[Point]
    label_position: Point | None = None


@dataclass(slots=True)
class PositionedGroup:
    id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    children: list[PositionedGroup]


@dataclass(slots=True)
class PositionedGraph:
    width: float
    height: float
    nodes: list[PositionedNode]
    edges: list[PositionedEdge]
    groups: list[PositionedGroup]


# ============================================================================
# Render options — user-facing configuration
# ============================================================================

@dataclass(slots=True)
class RenderOptions:
    bg: str | None = None
    fg: str | None = None
    line: str | None = None
    accent: str | None = None
    muted: str | None = None
    surface: str | None = None
    border: str | None = None
    font: str | None = None
    padding: int | None = None
    node_spacing: int | None = None
    layer_spacing: int | None = None
    transparent: bool | None = None
