"""pretty-mermaid — Render Mermaid diagrams to beautiful SVG and ASCII/Unicode art."""

from __future__ import annotations

import re

from .types import RenderOptions, MermaidGraph, PositionedGraph
from .theme import DiagramColors, THEMES, DEFAULTS, from_shiki_theme
from .parser import parse_mermaid
from .layout import layout_graph
from .renderer import render_svg

from .sequence.parser import parse_sequence_diagram
from .sequence.layout import layout_sequence_diagram
from .sequence.renderer import render_sequence_svg

from .class_diagram.parser import parse_class_diagram
from .class_diagram.layout import layout_class_diagram
from .class_diagram.renderer import render_class_svg

from .er.parser import parse_er_diagram
from .er.layout import layout_er_diagram
from .er.renderer import render_er_svg

__all__ = [
    "render_mermaid",
    "render_mermaid_ascii",
    "parse_mermaid",
    "from_shiki_theme",
    "THEMES",
    "DEFAULTS",
    "RenderOptions",
    "MermaidGraph",
    "PositionedGraph",
    "DiagramColors",
]


def _detect_diagram_type(text: str) -> str:
    """Detect diagram type from mermaid source text."""
    first_line = (text.strip().split("\n")[0] or "").strip().lower()
    # Also handle semicolon-separated
    first_line = first_line.split(";")[0].strip()

    if re.match(r"^sequencediagram\s*$", first_line):
        return "sequence"
    if re.match(r"^classdiagram\s*$", first_line):
        return "class"
    if re.match(r"^erdiagram\s*$", first_line):
        return "er"

    return "flowchart"


def _build_colors(options: RenderOptions) -> DiagramColors:
    """Build DiagramColors from render options."""
    return DiagramColors(
        bg=options.bg or DEFAULTS["bg"],
        fg=options.fg or DEFAULTS["fg"],
        line=options.line,
        accent=options.accent,
        muted=options.muted,
        surface=options.surface,
        border=options.border,
    )


def render_mermaid(
    text: str,
    options: RenderOptions | None = None,
) -> str:
    """Render Mermaid diagram text to an SVG string.

    Auto-detects diagram type from the header line.
    """
    if options is None:
        options = RenderOptions()

    colors = _build_colors(options)
    font = options.font or "Inter"
    transparent = options.transparent or False
    diagram_type = _detect_diagram_type(text)

    lines = [
        l.strip()
        for l in re.split(r"[\n;]", text)
        if l.strip() and not l.strip().startswith("%%")
    ]

    if diagram_type == "sequence":
        diagram = parse_sequence_diagram(lines)
        positioned = layout_sequence_diagram(diagram, options)
        return render_sequence_svg(positioned, colors, font, transparent)
    elif diagram_type == "class":
        diagram = parse_class_diagram(lines)
        positioned = layout_class_diagram(diagram, options)
        return render_class_svg(positioned, colors, font, transparent)
    elif diagram_type == "er":
        diagram = parse_er_diagram(lines)
        positioned = layout_er_diagram(diagram, options)
        return render_er_svg(positioned, colors, font, transparent)
    else:
        graph = parse_mermaid(text)
        positioned = layout_graph(graph, options)
        return render_svg(positioned, colors, font, transparent)


def render_mermaid_ascii(
    text: str,
    options: dict | None = None,
) -> str:
    """Render Mermaid diagram text to ASCII/Unicode art string."""
    from .ascii import render_mermaid_ascii as _render_ascii
    return _render_ascii(text, options)
