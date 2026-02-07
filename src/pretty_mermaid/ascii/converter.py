from __future__ import annotations

# ============================================================================
# ASCII renderer -- MermaidGraph -> AsciiGraph converter
#
# Bridges the existing Python parser output to the ASCII renderer's
# internal graph structure. This avoids maintaining a separate parser
# for ASCII rendering -- we reuse parse_mermaid() and convert its output.
# ============================================================================

from ..types import MermaidGraph, MermaidSubgraph

from .types import (
    AsciiGraph,
    AsciiNode,
    AsciiEdge,
    AsciiSubgraph,
    AsciiConfig,
    EMPTY_STYLE,
)
from .canvas import mk_canvas


def convert_to_ascii_graph(parsed: MermaidGraph, config: AsciiConfig) -> AsciiGraph:
    """Convert a parsed MermaidGraph into an AsciiGraph ready for grid layout.

    Key mappings:
    - MermaidGraph.nodes (dict) -> ordered AsciiNode[] preserving insertion order
    - MermaidGraph.edges -> AsciiEdge[] with resolved node references
    - MermaidGraph.subgraphs -> AsciiSubgraph[] with parent/child tree
    - Node labels are used as display names (not raw IDs)
    """
    # Build node list preserving dict insertion order
    node_map: dict[str, AsciiNode] = {}
    index = 0

    for node_id, m_node in parsed.nodes.items():
        ascii_node = AsciiNode(
            # Use the parser ID as the unique identity key to avoid collisions
            # when multiple nodes share the same label (e.g. A[Web Server], C[Web Server]).
            name=node_id,
            # The label is used for rendering inside the box.
            display_label=m_node.label,
            index=index,
        )
        node_map[node_id] = ascii_node
        index += 1

    nodes = list(node_map.values())

    # Build edges with resolved node references
    edges: list[AsciiEdge] = []
    for m_edge in parsed.edges:
        from_node = node_map.get(m_edge.source)
        to_node = node_map.get(m_edge.target)
        if from_node is None or to_node is None:
            continue

        edges.append(
            AsciiEdge(
                from_node=from_node,
                to_node=to_node,
                text=m_edge.label or "",
            )
        )

    # Convert subgraphs recursively
    subgraphs: list[AsciiSubgraph] = []
    for m_sg in parsed.subgraphs:
        _convert_subgraph(m_sg, None, node_map, subgraphs)

    # Deduplicate subgraph node membership to match Go parser behavior.
    # In Go, a node belongs only to the subgraph where it was FIRST DEFINED.
    # The TS parser adds referenced nodes to all subgraphs they appear in,
    # which causes incorrect bounding boxes when nodes span subgraph boundaries.
    _deduplicate_subgraph_nodes(parsed.subgraphs, subgraphs, node_map, parsed)

    # Apply class definitions
    for node_id, class_name in parsed.class_assignments.items():
        node = node_map.get(node_id)
        class_def = parsed.class_defs.get(class_name)
        if node is not None and class_def is not None:
            node.style_class_name = class_name
            node.style_class.name = class_name
            node.style_class.styles = class_def

    return AsciiGraph(
        nodes=nodes,
        edges=edges,
        canvas=mk_canvas(0, 0),
        subgraphs=subgraphs,
        config=config,
    )


def _convert_subgraph(
    m_sg: MermaidSubgraph,
    parent: AsciiSubgraph | None,
    node_map: dict[str, AsciiNode],
    all_subgraphs: list[AsciiSubgraph],
) -> AsciiSubgraph:
    """Recursively convert a MermaidSubgraph to AsciiSubgraph.

    Flattens the tree into the subgraphs array while maintaining parent/child
    references. This matches the Go implementation where all subgraphs are in a
    flat list but linked via parent/children pointers.
    """
    sg = AsciiSubgraph(
        name=m_sg.label,
        parent=parent,
    )

    # Resolve node references
    for node_id in m_sg.node_ids:
        node = node_map.get(node_id)
        if node is not None:
            sg.nodes.append(node)

    all_subgraphs.append(sg)

    # Recurse into children
    for child_m_sg in m_sg.children:
        child = _convert_subgraph(child_m_sg, sg, node_map, all_subgraphs)
        sg.children.append(child)

        # Child nodes are also part of parent subgraphs (Go behavior).
        # The Go parser adds nodes to ALL subgraphs in the stack, so a nested
        # node belongs to both the inner and outer subgraph.
        for child_node in child.nodes:
            if child_node not in sg.nodes:
                sg.nodes.append(child_node)

    return sg


def _deduplicate_subgraph_nodes(
    mermaid_subgraphs: list[MermaidSubgraph],
    ascii_subgraphs: list[AsciiSubgraph],
    node_map: dict[str, AsciiNode],
    parsed: MermaidGraph,
) -> None:
    """Deduplicate subgraph node membership to match Go parser behavior.

    The Go parser only adds a node to the subgraph that was active when the node
    was FIRST CREATED. If a node is later referenced inside a different subgraph,
    it is NOT added to that subgraph. The TS parser is more permissive -- it adds
    referenced nodes to whichever subgraph they appear in.

    This function fixes the discrepancy by:
    1. Walking the edges to determine which nodes were first created inside each
       subgraph
    2. Removing nodes from subgraphs where they were not first created
    """
    # Build a map from MermaidSubgraph to its corresponding AsciiSubgraph.
    # The ordering matches since we convert them in the same order.
    sg_map: dict[int, AsciiSubgraph] = {}
    _build_sg_map(mermaid_subgraphs, ascii_subgraphs, sg_map)

    # Determine which subgraph each node was "first defined" in.
    # A node is first defined in the subgraph where it first appears as a NEW node
    # in the ordered edge/node list. We approximate this by checking the global
    # node insertion order against subgraph membership.
    node_owner: dict[str, AsciiSubgraph] = {}

    def claim_nodes(m_sg: MermaidSubgraph) -> None:
        ascii_sg = sg_map.get(id(m_sg))
        if ascii_sg is None:
            return

        # Recurse into children first (they appear before parent in the Go parser
        # stack, but nodes defined in children are added to parent too -- this is
        # handled by the _convert_subgraph function which propagates child nodes to
        # parents). For dedup, we process children first so their claims propagate
        # up correctly.
        for child in m_sg.children:
            claim_nodes(child)

        # Claim unclaimed nodes in this subgraph
        for node_id in m_sg.node_ids:
            if node_id not in node_owner:
                ascii_sg_for_node = sg_map.get(id(m_sg))
                if ascii_sg_for_node is not None:
                    node_owner[node_id] = ascii_sg_for_node

    for m_sg in mermaid_subgraphs:
        claim_nodes(m_sg)

    # Build reverse map: AsciiNode -> node_id
    node_to_id: dict[int, str] = {}
    for nid, node in node_map.items():
        node_to_id[id(node)] = nid

    # Now remove nodes from subgraphs that don't own them.
    # A node should remain in: its owner subgraph + all ancestors of the owner.
    for ascii_sg in ascii_subgraphs:
        ascii_sg.nodes = [
            node
            for node in ascii_sg.nodes
            if _should_keep_node(node, ascii_sg, node_to_id, node_owner)
        ]


def _should_keep_node(
    node: AsciiNode,
    ascii_sg: AsciiSubgraph,
    node_to_id: dict[int, str],
    node_owner: dict[str, AsciiSubgraph],
) -> bool:
    """Determine if a node should remain in a subgraph."""
    node_id = node_to_id.get(id(node))
    if node_id is None:
        return False

    owner = node_owner.get(node_id)
    if owner is None:
        return True  # not in any subgraph claim -- keep as-is

    # Keep the node if this subgraph is the owner or an ancestor of the owner
    return _is_ancestor_or_self(ascii_sg, owner)


def _is_ancestor_or_self(candidate: AsciiSubgraph, target: AsciiSubgraph) -> bool:
    """Check if *candidate* is the same as or an ancestor of *target*."""
    current: AsciiSubgraph | None = target
    while current is not None:
        if current is candidate:
            return True
        current = current.parent
    return False


def _build_sg_map(
    m_sgs: list[MermaidSubgraph],
    a_sgs: list[AsciiSubgraph],
    result: dict[int, AsciiSubgraph],
) -> None:
    """Build a mapping from MermaidSubgraph -> AsciiSubgraph (matching by position).

    Uses id() of MermaidSubgraph objects as keys since they are not hashable by value.
    """
    # The ascii_subgraphs array is flat (all subgraphs including nested ones),
    # while mermaid_subgraphs is hierarchical. We need to flatten the mermaid tree
    # in the same order the converter processes them (pre-order DFS).
    flat_mermaid: list[MermaidSubgraph] = []

    def flatten(sgs: list[MermaidSubgraph]) -> None:
        for sg in sgs:
            flat_mermaid.append(sg)
            flatten(sg.children)

    flatten(m_sgs)

    for i in range(min(len(flat_mermaid), len(a_sgs))):
        result[id(flat_mermaid[i])] = a_sgs[i]
