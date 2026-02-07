from __future__ import annotations

import re
from typing import Literal

from .types import (
    MermaidGraph,
    MermaidNode,
    MermaidEdge,
    MermaidSubgraph,
    Direction,
    NodeShape,
    EdgeStyle,
)

# ============================================================================
# Mermaid parser — flowcharts and state diagrams
# ============================================================================


def parse_mermaid(text: str) -> MermaidGraph:
    """Parse Mermaid text into a logical graph structure.

    Auto-detects diagram type (flowchart or state diagram).
    """
    lines = [
        l.strip()
        for l in re.split(r"[\n;]", text)
        if l.strip() and not l.strip().startswith("%%")
    ]

    if not lines:
        raise ValueError("Empty mermaid diagram")

    header = lines[0]

    # State diagram
    if re.match(r"^stateDiagram(-v2)?\s*$", header, re.IGNORECASE):
        return _parse_state_diagram(lines)

    # Flowchart
    return _parse_flowchart(lines)


# ============================================================================
# Flowchart parser
# ============================================================================


def _parse_flowchart(lines: list[str]) -> MermaidGraph:
    header_match = re.match(
        r"^(?:graph|flowchart)\s+(TD|TB|LR|BT|RL)\s*$", lines[0], re.IGNORECASE
    )
    if not header_match:
        raise ValueError(
            f'Invalid mermaid header: "{lines[0]}". '
            'Expected "graph TD", "flowchart LR", "stateDiagram-v2", etc.'
        )

    direction: Direction = header_match.group(1).upper()  # type: ignore[assignment]

    graph = MermaidGraph(
        direction=direction,
        nodes={},
        edges=[],
        subgraphs=[],
        class_defs={},
        class_assignments={},
        node_styles={},
    )

    subgraph_stack: list[MermaidSubgraph] = []

    for i in range(1, len(lines)):
        line = lines[i]

        # --- classDef ---
        m = re.match(r"^classDef\s+(\w+)\s+(.+)$", line)
        if m:
            name = m.group(1)
            props = _parse_style_props(m.group(2))
            graph.class_defs[name] = props
            continue

        # --- class assignment ---
        m = re.match(r"^class\s+([\w,-]+)\s+(\w+)$", line)
        if m:
            node_ids = [s.strip() for s in m.group(1).split(",")]
            class_name = m.group(2)
            for nid in node_ids:
                graph.class_assignments[nid] = class_name
            continue

        # --- style statement ---
        m = re.match(r"^style\s+([\w,-]+)\s+(.+)$", line)
        if m:
            node_ids = [s.strip() for s in m.group(1).split(",")]
            props = _parse_style_props(m.group(2))
            for nid in node_ids:
                existing = graph.node_styles.get(nid, {})
                existing.update(props)
                graph.node_styles[nid] = existing
            continue

        # --- direction override ---
        m = re.match(r"^direction\s+(TD|TB|LR|BT|RL)\s*$", line, re.IGNORECASE)
        if m and subgraph_stack:
            subgraph_stack[-1].direction = m.group(1).upper()  # type: ignore[assignment]
            continue

        # --- subgraph start ---
        m = re.match(r"^subgraph\s+(.+)$", line)
        if m:
            rest = m.group(1).strip()
            bracket_match = re.match(r"^([\w-]+)\s*\[(.+)\]$", rest)
            if bracket_match:
                sg_id = bracket_match.group(1)
                label = bracket_match.group(2)
            else:
                label = rest
                sg_id = re.sub(r"[^\w]", "", rest.replace(" ", "_"))
            sg = MermaidSubgraph(id=sg_id, label=label, node_ids=[], children=[])
            subgraph_stack.append(sg)
            continue

        # --- subgraph end ---
        if line == "end":
            if subgraph_stack:
                completed = subgraph_stack.pop()
                if subgraph_stack:
                    subgraph_stack[-1].children.append(completed)
                else:
                    graph.subgraphs.append(completed)
            continue

        # --- Edge/node definitions ---
        _parse_edge_line(line, graph, subgraph_stack)

    return graph


# ============================================================================
# State diagram parser
# ============================================================================


def _parse_state_diagram(lines: list[str]) -> MermaidGraph:
    graph = MermaidGraph(
        direction="TD",
        nodes={},
        edges=[],
        subgraphs=[],
        class_defs={},
        class_assignments={},
        node_styles={},
    )

    composite_stack: list[MermaidSubgraph] = []
    start_count = 0
    end_count = 0

    for i in range(1, len(lines)):
        line = lines[i]

        # --- direction override ---
        m = re.match(r"^direction\s+(TD|TB|LR|BT|RL)\s*$", line, re.IGNORECASE)
        if m:
            d: Direction = m.group(1).upper()  # type: ignore[assignment]
            if composite_stack:
                composite_stack[-1].direction = d
            else:
                graph.direction = d
            continue

        # --- composite state start ---
        m = re.match(r'^state\s+(?:"([^"]+)"\s+as\s+)?(\w+)\s*\{$', line)
        if m:
            label = m.group(1) or m.group(2)
            sid = m.group(2)
            sg = MermaidSubgraph(id=sid, label=label, node_ids=[], children=[])
            composite_stack.append(sg)
            continue

        # --- composite state end ---
        if line == "}":
            if composite_stack:
                completed = composite_stack.pop()
                if composite_stack:
                    composite_stack[-1].children.append(completed)
                else:
                    graph.subgraphs.append(completed)
            continue

        # --- state alias ---
        m = re.match(r'^state\s+"([^"]+)"\s+as\s+(\w+)\s*$', line)
        if m:
            label = m.group(1)
            sid = m.group(2)
            _register_state_node(
                graph, composite_stack, MermaidNode(id=sid, label=label, shape="rounded")
            )
            continue

        # --- transition ---
        m = re.match(
            r"^(\[\*\]|[\w-]+)\s*(-->)\s*(\[\*\]|[\w-]+)(?:\s*:\s*(.+))?$", line
        )
        if m:
            source_id = m.group(1)
            target_id = m.group(3)
            edge_label = (m.group(4) or "").strip() or None

            if source_id == "[*]":
                start_count += 1
                source_id = f"_start{start_count if start_count > 1 else ''}"
                _register_state_node(
                    graph,
                    composite_stack,
                    MermaidNode(id=source_id, label="", shape="state-start"),
                )
            else:
                _ensure_state_node(graph, composite_stack, source_id)

            if target_id == "[*]":
                end_count += 1
                target_id = f"_end{end_count if end_count > 1 else ''}"
                _register_state_node(
                    graph,
                    composite_stack,
                    MermaidNode(id=target_id, label="", shape="state-end"),
                )
            else:
                _ensure_state_node(graph, composite_stack, target_id)

            graph.edges.append(
                MermaidEdge(
                    source=source_id,
                    target=target_id,
                    label=edge_label,
                    style="solid",
                    has_arrow_start=False,
                    has_arrow_end=True,
                )
            )
            continue

        # --- state description ---
        m = re.match(r"^([\w-]+)\s*:\s*(.+)$", line)
        if m:
            sid = m.group(1)
            label = m.group(2).strip()
            _register_state_node(
                graph, composite_stack, MermaidNode(id=sid, label=label, shape="rounded")
            )
            continue

    return graph


def _register_state_node(
    graph: MermaidGraph,
    composite_stack: list[MermaidSubgraph],
    node: MermaidNode,
) -> None:
    if node.id not in graph.nodes:
        graph.nodes[node.id] = node
    if composite_stack:
        current = composite_stack[-1]
        if node.id not in current.node_ids:
            current.node_ids.append(node.id)


def _ensure_state_node(
    graph: MermaidGraph,
    composite_stack: list[MermaidSubgraph],
    node_id: str,
) -> None:
    if node_id not in graph.nodes:
        _register_state_node(
            graph,
            composite_stack,
            MermaidNode(id=node_id, label=node_id, shape="rounded"),
        )
    elif composite_stack:
        current = composite_stack[-1]
        if node_id not in current.node_ids:
            current.node_ids.append(node_id)


# ============================================================================
# Shared utilities
# ============================================================================


def _parse_style_props(props_str: str) -> dict[str, str]:
    """Parse 'fill:#f00,stroke:#333' into a dict."""
    props: dict[str, str] = {}
    for pair in props_str.split(","):
        colon_idx = pair.find(":")
        if colon_idx > 0:
            key = pair[:colon_idx].strip()
            val = pair[colon_idx + 1 :].strip()
            if key and val:
                props[key] = val
    return props


# ============================================================================
# Flowchart edge line parser
# ============================================================================

ARROW_REGEX = re.compile(r"^(<)?(-->|-.->|==>|---|-\.-|===)(?:\|([^|]*)\|)?")

NODE_PATTERNS: list[tuple[re.Pattern[str], NodeShape]] = [
    # Triple delimiters
    (re.compile(r"^([\w-]+)\(\(\((.+?)\)\)\)"), "doublecircle"),
    # Double delimiters with mixed brackets
    (re.compile(r"^([\w-]+)\(\[(.+?)\]\)"), "stadium"),
    (re.compile(r"^([\w-]+)\(\((.+?)\)\)"), "circle"),
    (re.compile(r"^([\w-]+)\[\[(.+?)\]\]"), "subroutine"),
    (re.compile(r"^([\w-]+)\[\((.+?)\)\]"), "cylinder"),
    # Trapezoid variants
    (re.compile(r"^([\w-]+)\[/(.+?)\\\]"), "trapezoid"),
    (re.compile(r"^([\w-]+)\[\\(.+?)/\]"), "trapezoid-alt"),
    # Asymmetric flag
    (re.compile(r"^([\w-]+)>(.+?)\]"), "asymmetric"),
    # Double curly braces (hexagon)
    (re.compile(r"^([\w-]+)\{\{(.+?)\}\}"), "hexagon"),
    # Single-char delimiters
    (re.compile(r"^([\w-]+)\[(.+?)\]"), "rectangle"),
    (re.compile(r"^([\w-]+)\((.+?)\)"), "rounded"),
    (re.compile(r"^([\w-]+)\{(.+?)\}"), "diamond"),
]

BARE_NODE_REGEX = re.compile(r"^([\w-]+)")
CLASS_SHORTHAND_REGEX = re.compile(r"^:::([\w][\w-]*)")


def _parse_edge_line(
    line: str,
    graph: MermaidGraph,
    subgraph_stack: list[MermaidSubgraph],
) -> None:
    remaining = line.strip()

    first_group = _consume_node_group(remaining, graph, subgraph_stack)
    if not first_group or not first_group[0]:
        return

    prev_group_ids, remaining = first_group
    remaining = remaining.strip()

    while remaining:
        arrow_match = ARROW_REGEX.match(remaining)
        if not arrow_match:
            break

        has_arrow_start = bool(arrow_match.group(1))
        arrow_op = arrow_match.group(2)
        edge_label = (arrow_match.group(3) or "").strip() or None
        remaining = remaining[arrow_match.end() :].strip()

        style = _arrow_style_from_op(arrow_op)
        has_arrow_end = arrow_op.endswith(">")

        next_group = _consume_node_group(remaining, graph, subgraph_stack)
        if not next_group or not next_group[0]:
            break

        next_ids, remaining = next_group
        remaining = remaining.strip()

        for source_id in prev_group_ids:
            for target_id in next_ids:
                graph.edges.append(
                    MermaidEdge(
                        source=source_id,
                        target=target_id,
                        label=edge_label,
                        style=style,
                        has_arrow_start=has_arrow_start,
                        has_arrow_end=has_arrow_end,
                    )
                )

        prev_group_ids = next_ids


def _consume_node_group(
    text: str,
    graph: MermaidGraph,
    subgraph_stack: list[MermaidSubgraph],
) -> tuple[list[str], str] | None:
    first = _consume_node(text, graph, subgraph_stack)
    if not first:
        return None

    ids = [first[0]]
    remaining = first[1].strip()

    while remaining.startswith("&"):
        remaining = remaining[1:].strip()
        nxt = _consume_node(remaining, graph, subgraph_stack)
        if not nxt:
            break
        ids.append(nxt[0])
        remaining = nxt[1].strip()

    return ids, remaining


def _consume_node(
    text: str,
    graph: MermaidGraph,
    subgraph_stack: list[MermaidSubgraph],
) -> tuple[str, str] | None:
    node_id: str | None = None
    remaining = text

    for pattern, shape in NODE_PATTERNS:
        m = pattern.match(text)
        if m:
            node_id = m.group(1)
            label = m.group(2)
            _register_node(
                graph, subgraph_stack, MermaidNode(id=node_id, label=label, shape=shape)
            )
            remaining = text[m.end() :]
            break

    if node_id is None:
        bare_match = BARE_NODE_REGEX.match(text)
        if bare_match:
            node_id = bare_match.group(1)
            if node_id not in graph.nodes:
                _register_node(
                    graph,
                    subgraph_stack,
                    MermaidNode(id=node_id, label=node_id, shape="rectangle"),
                )
            else:
                _track_in_subgraph(subgraph_stack, node_id)
            remaining = text[bare_match.end() :]

    if node_id is None:
        return None

    class_match = CLASS_SHORTHAND_REGEX.match(remaining)
    if class_match:
        graph.class_assignments[node_id] = class_match.group(1)
        remaining = remaining[class_match.end() :]

    return node_id, remaining


def _register_node(
    graph: MermaidGraph,
    subgraph_stack: list[MermaidSubgraph],
    node: MermaidNode,
) -> None:
    if node.id not in graph.nodes:
        graph.nodes[node.id] = node
    _track_in_subgraph(subgraph_stack, node.id)


def _track_in_subgraph(subgraph_stack: list[MermaidSubgraph], node_id: str) -> None:
    if subgraph_stack:
        current = subgraph_stack[-1]
        if node_id not in current.node_ids:
            current.node_ids.append(node_id)


def _arrow_style_from_op(op: str) -> EdgeStyle:
    if op in ("-.->", "-.-"):
        return "dotted"
    if op in ("==>", "==="):
        return "thick"
    return "solid"
