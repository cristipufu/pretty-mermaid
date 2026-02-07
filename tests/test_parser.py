"""Tests for the Mermaid parser."""

from __future__ import annotations

import pytest

from pretty_mermaid.parser import parse_mermaid


# ============================================================================
# Graph header parsing
# ============================================================================


class TestGraphHeader:
    def test_parses_graph_td_header(self):
        g = parse_mermaid("graph TD\n  A --> B")
        assert g.direction == "TD"

    def test_parses_flowchart_lr_header(self):
        g = parse_mermaid("flowchart LR\n  A --> B")
        assert g.direction == "LR"

    @pytest.mark.parametrize("direction", ["TD", "TB", "LR", "BT", "RL"])
    def test_accepts_all_directions(self, direction):
        g = parse_mermaid(f"graph {direction}\n  A --> B")
        assert g.direction == direction

    def test_case_insensitive_keyword(self):
        g = parse_mermaid("graph td\n  A --> B")
        assert g.direction == "TD"

    def test_throws_on_empty_input(self):
        with pytest.raises(ValueError, match="Empty mermaid diagram"):
            parse_mermaid("")

    def test_throws_on_invalid_header(self):
        with pytest.raises(ValueError, match="Invalid mermaid header"):
            parse_mermaid("sequenceDiagram\n  A ->> B")

    def test_throws_on_header_without_direction(self):
        with pytest.raises(ValueError, match="Invalid mermaid header"):
            parse_mermaid("graph\n  A --> B")


# ============================================================================
# Original node shapes
# ============================================================================


class TestOriginalNodeShapes:
    def test_parses_rectangle_nodes(self):
        g = parse_mermaid("graph TD\n  A[Hello World]")
        node = g.nodes["A"]
        assert node.shape == "rectangle"
        assert node.label == "Hello World"

    def test_parses_rounded_nodes(self):
        g = parse_mermaid("graph TD\n  A(Rounded)")
        assert g.nodes["A"].shape == "rounded"
        assert g.nodes["A"].label == "Rounded"

    def test_parses_diamond_nodes(self):
        g = parse_mermaid("graph TD\n  A{Decision}")
        assert g.nodes["A"].shape == "diamond"
        assert g.nodes["A"].label == "Decision"

    def test_parses_stadium_nodes(self):
        g = parse_mermaid("graph TD\n  A([Stadium])")
        assert g.nodes["A"].shape == "stadium"
        assert g.nodes["A"].label == "Stadium"

    def test_parses_circle_nodes(self):
        g = parse_mermaid("graph TD\n  A((Circle))")
        assert g.nodes["A"].shape == "circle"
        assert g.nodes["A"].label == "Circle"

    def test_creates_default_rectangle_for_bare_nodes(self):
        g = parse_mermaid("graph TD\n  A --> B")
        assert g.nodes["A"].shape == "rectangle"
        assert g.nodes["A"].label == "A"
        assert g.nodes["B"].shape == "rectangle"
        assert g.nodes["B"].label == "B"

    def test_supports_hyphenated_node_ids(self):
        g = parse_mermaid("graph TD\n  my-node[My Node]")
        assert "my-node" in g.nodes
        assert g.nodes["my-node"].label == "My Node"

    def test_first_definition_wins(self):
        g = parse_mermaid("graph TD\n  A[Start] --> B\n  A --> B")
        assert g.nodes["A"].shape == "rectangle"
        assert g.nodes["A"].label == "Start"


# ============================================================================
# Batch 1 node shapes
# ============================================================================


class TestBatch1NodeShapes:
    def test_parses_subroutine_nodes(self):
        g = parse_mermaid("graph TD\n  A[[Subroutine]]")
        assert g.nodes["A"].shape == "subroutine"
        assert g.nodes["A"].label == "Subroutine"

    def test_parses_double_circle_nodes(self):
        g = parse_mermaid("graph TD\n  A(((Double)))")
        assert g.nodes["A"].shape == "doublecircle"
        assert g.nodes["A"].label == "Double"

    def test_parses_hexagon_nodes(self):
        g = parse_mermaid("graph TD\n  A{{Hexagon}}")
        assert g.nodes["A"].shape == "hexagon"
        assert g.nodes["A"].label == "Hexagon"


# ============================================================================
# Batch 2 node shapes
# ============================================================================


class TestBatch2NodeShapes:
    def test_parses_cylinder_nodes(self):
        g = parse_mermaid("graph TD\n  A[(Database)]")
        assert g.nodes["A"].shape == "cylinder"
        assert g.nodes["A"].label == "Database"

    def test_parses_asymmetric_nodes(self):
        g = parse_mermaid("graph TD\n  A>Flag Shape]")
        assert g.nodes["A"].shape == "asymmetric"
        assert g.nodes["A"].label == "Flag Shape"

    def test_parses_trapezoid_nodes(self):
        g = parse_mermaid("graph TD\n  A[/Trapezoid\\]")
        assert g.nodes["A"].shape == "trapezoid"
        assert g.nodes["A"].label == "Trapezoid"

    def test_parses_trapezoid_alt_nodes(self):
        g = parse_mermaid("graph TD\n  A[\\Alt Trapezoid/]")
        assert g.nodes["A"].shape == "trapezoid-alt"
        assert g.nodes["A"].label == "Alt Trapezoid"


# ============================================================================
# All shapes combined
# ============================================================================


class TestAllShapesCombined:
    def test_parses_all_13_shapes(self):
        g = parse_mermaid(
            "graph TD\n"
            "  A[Rectangle]\n"
            "  B(Rounded)\n"
            "  C{Diamond}\n"
            "  D([Stadium])\n"
            "  E((Circle))\n"
            "  F[[Subroutine]]\n"
            "  G(((DoubleCircle)))\n"
            "  H{{Hexagon}}\n"
            "  I[(Cylinder)]\n"
            "  J>Asymmetric]\n"
            "  K[/Trapezoid\\]\n"
            "  L[\\TrapAlt/]"
        )
        assert g.nodes["A"].shape == "rectangle"
        assert g.nodes["B"].shape == "rounded"
        assert g.nodes["C"].shape == "diamond"
        assert g.nodes["D"].shape == "stadium"
        assert g.nodes["E"].shape == "circle"
        assert g.nodes["F"].shape == "subroutine"
        assert g.nodes["G"].shape == "doublecircle"
        assert g.nodes["H"].shape == "hexagon"
        assert g.nodes["I"].shape == "cylinder"
        assert g.nodes["J"].shape == "asymmetric"
        assert g.nodes["K"].shape == "trapezoid"
        assert g.nodes["L"].shape == "trapezoid-alt"


# ============================================================================
# Edge parsing
# ============================================================================


class TestEdgeParsing:
    def test_parses_solid_edge(self):
        g = parse_mermaid("graph TD\n  A --> B")
        assert len(g.edges) == 1
        assert g.edges[0].source == "A"
        assert g.edges[0].target == "B"
        assert g.edges[0].style == "solid"
        assert g.edges[0].label is None

    def test_parses_dotted_edge(self):
        g = parse_mermaid("graph TD\n  A -.-> B")
        assert g.edges[0].style == "dotted"

    def test_parses_thick_edge(self):
        g = parse_mermaid("graph TD\n  A ==> B")
        assert g.edges[0].style == "thick"

    def test_parses_edge_label(self):
        g = parse_mermaid("graph TD\n  A -->|Yes| B")
        assert g.edges[0].label == "Yes"

    def test_parses_edge_label_on_dotted(self):
        g = parse_mermaid("graph TD\n  A -.->|Maybe| B")
        assert g.edges[0].label == "Maybe"
        assert g.edges[0].style == "dotted"

    def test_parses_chained_edges(self):
        g = parse_mermaid("graph TD\n  A --> B --> C")
        assert len(g.edges) == 2
        assert g.edges[0].source == "A"
        assert g.edges[0].target == "B"
        assert g.edges[1].source == "B"
        assert g.edges[1].target == "C"

    def test_parses_chained_edges_with_shapes(self):
        g = parse_mermaid("graph TD\n  A[Start] --> B{Check} --> C(End)")
        assert len(g.edges) == 2
        assert g.nodes["A"].shape == "rectangle"
        assert g.nodes["B"].shape == "diamond"
        assert g.nodes["C"].shape == "rounded"

    def test_handles_multiple_edge_lines(self):
        g = parse_mermaid("graph TD\n  A --> B\n  B --> C\n  C --> D")
        assert len(g.edges) == 3

    def test_has_arrow_end_true(self):
        g = parse_mermaid("graph TD\n  A --> B")
        assert g.edges[0].has_arrow_end is True
        assert g.edges[0].has_arrow_start is False


# ============================================================================
# No-arrow edges
# ============================================================================


class TestNoArrowEdges:
    def test_solid_line_without_arrow(self):
        g = parse_mermaid("graph TD\n  A --- B")
        assert len(g.edges) == 1
        assert g.edges[0].style == "solid"
        assert g.edges[0].has_arrow_end is False
        assert g.edges[0].has_arrow_start is False

    def test_dotted_line_without_arrow(self):
        g = parse_mermaid("graph TD\n  A -.- B")
        assert g.edges[0].style == "dotted"
        assert g.edges[0].has_arrow_end is False

    def test_thick_line_without_arrow(self):
        g = parse_mermaid("graph TD\n  A === B")
        assert g.edges[0].style == "thick"
        assert g.edges[0].has_arrow_end is False

    def test_no_arrow_with_label(self):
        g = parse_mermaid("graph TD\n  A ---|connects| B")
        assert g.edges[0].label == "connects"
        assert g.edges[0].has_arrow_end is False


# ============================================================================
# Bidirectional arrows
# ============================================================================


class TestBidirectionalArrows:
    def test_solid_bidirectional(self):
        g = parse_mermaid("graph TD\n  A <--> B")
        assert len(g.edges) == 1
        assert g.edges[0].style == "solid"
        assert g.edges[0].has_arrow_start is True
        assert g.edges[0].has_arrow_end is True

    def test_dotted_bidirectional(self):
        g = parse_mermaid("graph TD\n  A <-.-> B")
        assert g.edges[0].style == "dotted"
        assert g.edges[0].has_arrow_start is True
        assert g.edges[0].has_arrow_end is True

    def test_thick_bidirectional(self):
        g = parse_mermaid("graph TD\n  A <==> B")
        assert g.edges[0].style == "thick"
        assert g.edges[0].has_arrow_start is True
        assert g.edges[0].has_arrow_end is True

    def test_bidirectional_with_label(self):
        g = parse_mermaid("graph TD\n  A <-->|sync| B")
        assert g.edges[0].label == "sync"
        assert g.edges[0].has_arrow_start is True
        assert g.edges[0].has_arrow_end is True


# ============================================================================
# Parallel links with &
# ============================================================================


class TestParallelLinks:
    def test_a_and_b_to_c(self):
        g = parse_mermaid("graph TD\n  A & B --> C")
        assert len(g.edges) == 2
        assert g.edges[0].source == "A"
        assert g.edges[0].target == "C"
        assert g.edges[1].source == "B"
        assert g.edges[1].target == "C"

    def test_a_to_c_and_d(self):
        g = parse_mermaid("graph TD\n  A --> C & D")
        assert len(g.edges) == 2
        assert g.edges[0].source == "A"
        assert g.edges[0].target == "C"
        assert g.edges[1].source == "A"
        assert g.edges[1].target == "D"

    def test_cartesian_product(self):
        g = parse_mermaid("graph TD\n  A & B --> C & D")
        assert len(g.edges) == 4
        pairs = [f"{e.source}->{e.target}" for e in g.edges]
        assert "A->C" in pairs
        assert "A->D" in pairs
        assert "B->C" in pairs
        assert "B->D" in pairs


# ============================================================================
# ::: class shorthand
# ============================================================================


class TestClassShorthand:
    def test_assigns_class_on_shaped_nodes(self):
        g = parse_mermaid("graph TD\n  A[Start]:::highlight --> B")
        assert g.class_assignments["A"] == "highlight"

    def test_assigns_class_on_bare_nodes(self):
        g = parse_mermaid("graph TD\n  A:::important --> B")
        assert g.class_assignments["A"] == "important"

    def test_works_in_chained_edges(self):
        g = parse_mermaid("graph TD\n  A:::start --> B:::mid --> C:::end")
        assert g.class_assignments["A"] == "start"
        assert g.class_assignments["B"] == "mid"
        assert g.class_assignments["C"] == "end"


# ============================================================================
# Inline style statements
# ============================================================================


class TestStyleStatements:
    def test_parses_style_for_single_node(self):
        g = parse_mermaid("graph TD\n  A --> B\n  style A fill:#ff0000,stroke:#333")
        assert g.node_styles["A"] == {"fill": "#ff0000", "stroke": "#333"}

    def test_parses_style_for_multiple_nodes(self):
        g = parse_mermaid("graph TD\n  A --> B\n  style A,B fill:#0f0")
        assert g.node_styles["A"] == {"fill": "#0f0"}
        assert g.node_styles["B"] == {"fill": "#0f0"}

    def test_merges_multiple_style_statements(self):
        g = parse_mermaid("graph TD\n  A --> B\n  style A fill:#f00\n  style A stroke:#333")
        assert g.node_styles["A"] == {"fill": "#f00", "stroke": "#333"}


# ============================================================================
# Subgraph direction override
# ============================================================================


class TestSubgraphDirection:
    def test_direction_override_inside_subgraph(self):
        g = parse_mermaid(
            "graph TD\n"
            "  subgraph sub1 [Left-Right Group]\n"
            "    direction LR\n"
            "    A --> B\n"
            "  end"
        )
        assert g.subgraphs[0].direction == "LR"

    def test_direction_not_applied_outside_subgraph(self):
        g = parse_mermaid("graph TD\n  A --> B")
        assert g.direction == "TD"


# ============================================================================
# Subgraphs
# ============================================================================


class TestSubgraphs:
    def test_parses_basic_subgraph(self):
        g = parse_mermaid(
            "graph TD\n"
            "  subgraph Backend\n"
            "    A --> B\n"
            "  end"
        )
        assert len(g.subgraphs) == 1
        assert g.subgraphs[0].label == "Backend"
        assert "A" in g.subgraphs[0].node_ids
        assert "B" in g.subgraphs[0].node_ids

    def test_parses_subgraph_with_bracket_id(self):
        g = parse_mermaid(
            "graph TD\n"
            "  subgraph be [Backend Services]\n"
            "    A --> B\n"
            "  end"
        )
        assert g.subgraphs[0].id == "be"
        assert g.subgraphs[0].label == "Backend Services"

    def test_parses_subgraph_hyphenated_id(self):
        g = parse_mermaid(
            "graph TD\n"
            "  subgraph us-east [US East Region]\n"
            "    A --> B\n"
            "  end"
        )
        assert g.subgraphs[0].id == "us-east"
        assert g.subgraphs[0].label == "US East Region"

    def test_slugifies_label_as_id(self):
        g = parse_mermaid(
            "graph TD\n"
            "  subgraph My Group\n"
            "    A --> B\n"
            "  end"
        )
        assert g.subgraphs[0].id == "My_Group"
        assert g.subgraphs[0].label == "My Group"

    def test_parses_nested_subgraphs(self):
        g = parse_mermaid(
            "graph TD\n"
            "  subgraph Outer\n"
            "    subgraph Inner\n"
            "      A --> B\n"
            "    end\n"
            "    C --> D\n"
            "  end"
        )
        assert len(g.subgraphs) == 1
        outer = g.subgraphs[0]
        assert outer.label == "Outer"
        assert len(outer.children) == 1
        assert outer.children[0].label == "Inner"
        assert "A" in outer.children[0].node_ids
        assert "B" in outer.children[0].node_ids
        assert "C" in outer.node_ids
        assert "D" in outer.node_ids


# ============================================================================
# classDef and class assignments
# ============================================================================


class TestClassDef:
    def test_parses_classdef_with_properties(self):
        g = parse_mermaid(
            "graph TD\n"
            "  classDef highlight fill:#f96,stroke:#333\n"
            "  A --> B"
        )
        assert "highlight" in g.class_defs
        props = g.class_defs["highlight"]
        assert props["fill"] == "#f96"
        assert props["stroke"] == "#333"

    def test_parses_class_assignments_single(self):
        g = parse_mermaid("graph TD\n  A --> B\n  class A highlight")
        assert g.class_assignments["A"] == "highlight"

    def test_parses_class_assignments_multiple(self):
        g = parse_mermaid("graph TD\n  A --> B --> C\n  class A,B highlight")
        assert g.class_assignments["A"] == "highlight"
        assert g.class_assignments["B"] == "highlight"


# ============================================================================
# Comments
# ============================================================================


class TestComments:
    def test_ignores_comment_lines(self):
        g = parse_mermaid(
            "graph TD\n"
            "  %% This is a comment\n"
            "  A --> B\n"
            "  %% Another comment"
        )
        assert len(g.nodes) == 2
        assert len(g.edges) == 1


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_handles_extra_whitespace(self):
        g = parse_mermaid("  graph TD  \n    A  -->  B  ")
        assert len(g.edges) == 1
        assert len(g.nodes) == 2

    def test_handles_empty_lines(self):
        g = parse_mermaid("graph TD\n\n  A --> B\n\n  B --> C")
        assert len(g.edges) == 2

    def test_handles_only_nodes(self):
        g = parse_mermaid("graph TD\n  A[Only Node]")
        assert len(g.nodes) == 1
        assert len(g.edges) == 0

    def test_preserves_node_order(self):
        g = parse_mermaid("graph TD\n  Z[Last] --> A[First]")
        ids = list(g.nodes.keys())
        assert ids[0] == "Z"
        assert ids[1] == "A"


# ============================================================================
# State diagrams
# ============================================================================


class TestStateDiagrams:
    def test_detects_state_diagram_v2(self):
        g = parse_mermaid("stateDiagram-v2\n  s1 --> s2")
        assert g.direction == "TD"

    def test_detects_state_diagram_without_v2(self):
        g = parse_mermaid("stateDiagram\n  s1 --> s2")
        assert g.direction == "TD"

    def test_parses_basic_transitions(self):
        g = parse_mermaid("stateDiagram-v2\n  Idle --> Active\n  Active --> Done")
        assert len(g.edges) == 2
        assert g.edges[0].source == "Idle"
        assert g.edges[0].target == "Active"
        assert g.edges[1].source == "Active"
        assert g.edges[1].target == "Done"
        assert g.nodes["Idle"].shape == "rounded"

    def test_parses_transition_labels(self):
        g = parse_mermaid("stateDiagram-v2\n  Idle --> Active : start")
        assert g.edges[0].label == "start"

    def test_parses_start_pseudostate(self):
        g = parse_mermaid("stateDiagram-v2\n  [*] --> Idle")
        start_node = g.nodes.get("_start")
        assert start_node is not None
        assert start_node.shape == "state-start"
        assert g.edges[0].source == "_start"

    def test_parses_end_pseudostate(self):
        g = parse_mermaid("stateDiagram-v2\n  Done --> [*]")
        end_node = g.nodes.get("_end")
        assert end_node is not None
        assert end_node.shape == "state-end"
        assert g.edges[0].target == "_end"

    def test_unique_ids_for_multiple_pseudostates(self):
        g = parse_mermaid("stateDiagram-v2\n  [*] --> A\n  [*] --> B")
        assert "_start" in g.nodes
        assert "_start2" in g.nodes

    def test_parses_state_description(self):
        g = parse_mermaid("stateDiagram-v2\n  s1 : Idle State\n  s1 --> s2")
        assert g.nodes["s1"].label == "Idle State"
        assert g.nodes["s1"].shape == "rounded"

    def test_parses_state_alias(self):
        g = parse_mermaid(
            'stateDiagram-v2\n  state "Waiting for input" as waiting\n  waiting --> active'
        )
        assert g.nodes["waiting"].label == "Waiting for input"

    def test_parses_composite_states(self):
        g = parse_mermaid(
            "stateDiagram-v2\n"
            "  state Processing {\n"
            "    parse --> validate\n"
            "    validate --> execute\n"
            "  }"
        )
        assert len(g.subgraphs) == 1
        assert g.subgraphs[0].id == "Processing"
        assert g.subgraphs[0].label == "Processing"
        assert "parse" in g.subgraphs[0].node_ids
        assert "validate" in g.subgraphs[0].node_ids
        assert "execute" in g.subgraphs[0].node_ids

    def test_parses_composite_states_with_alias(self):
        g = parse_mermaid(
            'stateDiagram-v2\n'
            '  state "Active Processing" as AP {\n'
            "    inner1 --> inner2\n"
            "  }"
        )
        assert g.subgraphs[0].id == "AP"
        assert g.subgraphs[0].label == "Active Processing"

    def test_direction_override_root(self):
        g = parse_mermaid("stateDiagram-v2\n  direction LR\n  s1 --> s2")
        assert g.direction == "LR"

    def test_direction_override_composite(self):
        g = parse_mermaid(
            "stateDiagram-v2\n"
            "  state Processing {\n"
            "    direction LR\n"
            "    parse --> validate\n"
            "  }"
        )
        assert g.subgraphs[0].direction == "LR"

    def test_full_state_diagram(self):
        g = parse_mermaid(
            "stateDiagram-v2\n"
            "  [*] --> Idle\n"
            "  Idle --> Processing : submit\n"
            "  state Processing {\n"
            "    parse --> validate\n"
            "    validate --> execute\n"
            "  }\n"
            "  Processing --> Complete : done\n"
            "  Complete --> [*]"
        )
        assert "_start" in g.nodes
        assert "_end" in g.nodes
        assert "Idle" in g.nodes
        assert "Complete" in g.nodes
        assert len(g.subgraphs) == 1
        assert g.subgraphs[0].id == "Processing"
        assert len(g.edges) == 6
