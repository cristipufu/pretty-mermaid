from __future__ import annotations

# ============================================================================
# beautiful-mermaid -- ASCII renderer public API
#
# Renders Mermaid diagrams to ASCII or Unicode box-drawing art.
# No external dependencies -- pure Python.
#
# Supported diagram types:
#   - Flowcharts (graph TD / flowchart LR) -- grid-based layout with A* pathfinding
#   - State diagrams (stateDiagram-v2) -- same pipeline as flowcharts
#   - Sequence diagrams (sequenceDiagram) -- column-based timeline layout
#   - Class diagrams (classDiagram) -- level-based UML layout
#   - ER diagrams (erDiagram) -- grid layout with crow's foot notation
#
# Usage:
#   from pretty_mermaid.ascii import render_mermaid_ascii
#   ascii_art = render_mermaid_ascii('graph LR\n  A --> B')
# ============================================================================

import re
from dataclasses import dataclass
from typing import Literal

from ..parser import parse_mermaid
from .types import AsciiConfig
from .converter import convert_to_ascii_graph
from .grid import create_mapping
from .draw import draw_graph
from .canvas import canvas_to_string, flip_canvas_vertically
from .sequence import render_sequence_ascii
from .class_diagram import render_class_ascii
from .er_diagram import render_er_ascii


@dataclass(slots=True)
class AsciiRenderOptions:
    """Options for ASCII/Unicode rendering."""

    # true = ASCII chars (+,-,|,>), false = Unicode box-drawing. Default: false
    use_ascii: bool = False
    # Horizontal spacing between nodes. Default: 5
    padding_x: int = 5
    # Vertical spacing between nodes. Default: 5
    padding_y: int = 5
    # Padding inside node boxes. Default: 1
    box_border_padding: int = 1


DiagramType = Literal["flowchart", "sequence", "class", "er"]


def _detect_diagram_type(text: str) -> DiagramType:
    """Detect the diagram type from the mermaid source text.

    Mirrors the detection logic in the SVG renderer.
    """
    first_line = re.split(r"[\n;]", text.strip())[0].strip().lower()

    if re.match(r"^sequencediagram\s*$", first_line):
        return "sequence"
    if re.match(r"^classdiagram\s*$", first_line):
        return "class"
    if re.match(r"^erdiagram\s*$", first_line):
        return "er"

    # Default: flowchart/state (handled by parse_mermaid internally)
    return "flowchart"


def _text_to_lines(text: str) -> list[str]:
    """Split text into cleaned lines (trimmed, non-empty, no comments)."""
    return [
        line.strip()
        for line in re.split(r"[\n;]", text)
        if line.strip() and not line.strip().startswith("%%")
    ]


def render_mermaid_ascii(
    text: str,
    options: AsciiRenderOptions | dict | None = None,
) -> str:
    """Render Mermaid diagram text to an ASCII/Unicode string.

    Synchronous -- no async layout engine needed (unlike the SVG renderer).
    Auto-detects diagram type from the header line and dispatches to
    the appropriate renderer.

    Args:
        text: Mermaid source text (any supported diagram type).
        options: Rendering options. Can be an ``AsciiRenderOptions`` instance
            or a plain dict with the same keys.

    Returns:
        Multi-line ASCII/Unicode string.

    Example::

        result = render_mermaid_ascii(
            "graph LR\\n  A --> B --> C",
            AsciiRenderOptions(use_ascii=True),
        )
        # Output:
        # +---+     +---+     +---+
        # |   |     |   |     |   |
        # | A |---->| B |---->| C |
        # |   |     |   |     |   |
        # +---+     +---+     +---+
    """
    # Normalize options
    if options is None:
        opts = AsciiRenderOptions()
    elif isinstance(options, dict):
        opts = AsciiRenderOptions(
            use_ascii=options.get("use_ascii", options.get("useAscii", False)),
            padding_x=options.get("padding_x", options.get("paddingX", 5)),
            padding_y=options.get("padding_y", options.get("paddingY", 5)),
            box_border_padding=options.get(
                "box_border_padding",
                options.get("boxBorderPadding", 1),
            ),
        )
    else:
        opts = options

    config = AsciiConfig(
        use_ascii=opts.use_ascii,
        padding_x=opts.padding_x,
        padding_y=opts.padding_y,
        box_border_padding=opts.box_border_padding,
        graph_direction="TD",  # default, overridden for flowcharts below
    )

    diagram_type = _detect_diagram_type(text)

    if diagram_type == "sequence":
        lines = _text_to_lines(text)
        return render_sequence_ascii(lines, config)

    if diagram_type == "class":
        lines = _text_to_lines(text)
        return render_class_ascii(lines, config)

    if diagram_type == "er":
        lines = _text_to_lines(text)
        return render_er_ascii(lines, config)

    # Flowchart + state diagram pipeline (original)
    parsed = parse_mermaid(text)

    # Normalize direction for grid layout.
    # BT is laid out as TD then flipped vertically after drawing.
    # RL is treated as LR (full RL support not yet implemented).
    if parsed.direction in ("LR", "RL"):
        config.graph_direction = "LR"
    else:
        config.graph_direction = "TD"

    graph = convert_to_ascii_graph(parsed, config)
    create_mapping(graph)
    draw_graph(graph)

    # BT: flip the finished canvas vertically so the flow runs bottom->top.
    # The grid layout ran as TD; flipping + character remapping produces BT.
    if parsed.direction == "BT":
        flip_canvas_vertically(graph.canvas)

    return canvas_to_string(graph.canvas)
