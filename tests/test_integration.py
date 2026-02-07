"""Integration tests for the full render_mermaid pipeline.

These tests exercise parse -> layout -> render end-to-end.
Covers: original features, Batch 1 (new shapes), Batch 2 (edges, styles),
and Batch 3 (state diagrams).
"""
from __future__ import annotations

import re

import pytest

from pretty_mermaid import render_mermaid
from pretty_mermaid.types import RenderOptions


# ============================================================================
# Basic rendering
# ============================================================================


class TestBasic:
    def test_renders_a_simple_graph_to_valid_svg(self):
        svg = render_mermaid("graph TD\n  A --> B")
        assert '<svg xmlns="http://www.w3.org/2000/svg"' in svg
        assert "</svg>" in svg
        assert ">A</text>" in svg
        assert ">B</text>" in svg

    def test_renders_a_graph_with_labeled_nodes(self):
        svg = render_mermaid("graph TD\n  A[Start] --> B[End]")
        assert ">Start</text>" in svg
        assert ">End</text>" in svg

    def test_renders_edges_with_labels(self):
        svg = render_mermaid("graph TD\n  A -->|Yes| B")
        assert ">Yes</text>" in svg


# ============================================================================
# Options
# ============================================================================


class TestOptions:
    def test_applies_dark_colors(self):
        svg = render_mermaid("graph TD\n  A --> B", RenderOptions(bg="#18181B", fg="#FAFAFA"))
        assert "--bg:#18181B" in svg

    def test_applies_default_light_colors(self):
        svg = render_mermaid("graph TD\n  A --> B")
        assert "--bg:#FFFFFF" in svg

    def test_applies_custom_font(self):
        svg = render_mermaid("graph TD\n  A --> B", RenderOptions(font="JetBrains Mono"))
        assert "'JetBrains Mono'" in svg

    def test_respects_padding_option(self):
        small = render_mermaid("graph TD\n  A --> B", RenderOptions(padding=10))
        large = render_mermaid("graph TD\n  A --> B", RenderOptions(padding=80))

        def get_width(svg: str) -> float:
            match = re.search(r'width="([\d.]+)"', svg)
            return float(match.group(1)) if match else 0

        assert get_width(large) > get_width(small)


# ============================================================================
# Complex diagrams
# ============================================================================


class TestComplexDiagrams:
    def test_renders_all_original_node_shapes(self):
        svg = render_mermaid(
            "graph TD\n"
            "  A[Rectangle] --> B(Rounded)\n"
            "  B --> C{Diamond}\n"
            "  C --> D([Stadium])\n"
            "  D --> E((Circle))"
        )

        assert ">Rectangle</text>" in svg
        assert ">Rounded</text>" in svg
        assert ">Diamond</text>" in svg
        assert ">Stadium</text>" in svg
        assert ">Circle</text>" in svg
        assert "<polygon" in svg
        assert "<circle" in svg

    def test_renders_all_edge_styles(self):
        svg = render_mermaid(
            "graph TD\n"
            "  A -->|solid| B\n"
            "  B -.->|dotted| C\n"
            "  C ==>|thick| D"
        )

        assert ">solid</text>" in svg
        assert ">dotted</text>" in svg
        assert ">thick</text>" in svg
        assert 'stroke-dasharray="4 4"' in svg

    def test_renders_subgraphs(self):
        svg = render_mermaid(
            "graph TD\n"
            "  subgraph Backend\n"
            "    A[API] --> B[DB]\n"
            "  end\n"
            "  C[Client] --> A"
        )

        assert ">Backend</text>" in svg
        assert ">API</text>" in svg
        assert ">DB</text>" in svg
        assert ">Client</text>" in svg

    def test_renders_a_complex_real_world_diagram(self):
        svg = render_mermaid(
            "graph TD\n"
            "  subgraph ci [CI Pipeline]\n"
            "    A[Push Code] --> B{Tests Pass?}\n"
            "    B -->|Yes| C[Build Docker]\n"
            "    B -->|No| D[Fix & Retry]\n"
            "    D --> A\n"
            "  end\n"
            "  C --> E([Deploy to Staging])\n"
            "  E --> F{QA Approved?}\n"
            "  F -->|Yes| G((Production))\n"
            "  F -->|No| D"
        )

        assert "<svg" in svg
        assert "</svg>" in svg
        assert ">CI Pipeline</text>" in svg
        assert ">Push Code</text>" in svg
        assert ">Tests Pass?</text>" in svg
        assert ">Yes</text>" in svg
        assert ">No</text>" in svg
        assert ">Production</text>" in svg

    def test_renders_different_directions(self):
        lr = render_mermaid("graph LR\n  A --> B --> C")
        td = render_mermaid("graph TD\n  A --> B --> C")

        def get_dimensions(svg: str):
            w = re.search(r'width="([\d.]+)"', svg)
            h = re.search(r'height="([\d.]+)"', svg)
            return {
                "width": float(w.group(1)) if w else 0,
                "height": float(h.group(1)) if h else 0,
            }

        lr_dims = get_dimensions(lr)
        td_dims = get_dimensions(td)

        assert lr_dims["width"] > td_dims["width"]
        assert td_dims["height"] > lr_dims["height"]


# ============================================================================
# Batch 1: New shapes (end-to-end)
# ============================================================================


class TestBatch1Shapes:
    def test_renders_subroutine_shape_with_inner_vertical_lines(self):
        svg = render_mermaid("graph TD\n  A[[Subroutine]] --> B")
        assert ">Subroutine</text>" in svg
        assert "<line" in svg

    def test_renders_double_circle_with_two_circle_elements(self):
        svg = render_mermaid("graph TD\n  A(((Important))) --> B")
        assert ">Important</text>" in svg
        circle_count = len(re.findall(r"<circle", svg))
        assert circle_count >= 2

    def test_renders_hexagon_as_a_polygon(self):
        svg = render_mermaid("graph TD\n  A{{Decision}} --> B")
        assert ">Decision</text>" in svg
        assert "<polygon" in svg


# ============================================================================
# Batch 2: New shapes and edge features (end-to-end)
# ============================================================================


class TestBatch2Shapes:
    def test_renders_cylinder_database(self):
        svg = render_mermaid("graph TD\n  A[(Database)] --> B")
        assert ">Database</text>" in svg
        assert "<ellipse" in svg

    def test_renders_asymmetric_flag(self):
        svg = render_mermaid("graph TD\n  A>Flag Shape] --> B")
        assert ">Flag Shape</text>" in svg
        assert "<polygon" in svg

    def test_renders_trapezoid_shapes(self):
        svg = render_mermaid("graph TD\n  A[/Wider Bottom\\] --> B[\\Wider Top/]")
        assert ">Wider Bottom</text>" in svg
        assert ">Wider Top</text>" in svg


class TestBatch2EdgeFeatures:
    def test_renders_no_arrow_edges(self):
        svg = render_mermaid("graph TD\n  A --- B")
        assert "<polyline" in svg
        assert "marker-end" not in svg

    def test_renders_bidirectional_arrows(self):
        svg = render_mermaid("graph TD\n  A <--> B")
        assert 'marker-end="url(#arrowhead)"' in svg
        assert 'marker-start="url(#arrowhead-start)"' in svg

    def test_renders_parallel_links_with_ampersand(self):
        svg = render_mermaid("graph TD\n  A & B --> C")
        assert ">A</text>" in svg
        assert ">B</text>" in svg
        assert ">C</text>" in svg
        polylines = len(re.findall(r"<polyline", svg))
        assert polylines == 2

    def test_applies_inline_style_overrides(self):
        svg = render_mermaid(
            "graph TD\n"
            "  A[Red Node] --> B\n"
            "  style A fill:#ff0000,stroke:#cc0000"
        )
        assert 'fill="#ff0000"' in svg
        assert 'stroke="#cc0000"' in svg


# ============================================================================
# Batch 3: State diagrams (end-to-end)
# ============================================================================


class TestStateDiagrams:
    def test_renders_a_basic_state_diagram(self):
        svg = render_mermaid(
            "stateDiagram-v2\n"
            "  [*] --> Idle\n"
            "  Idle --> Active : start\n"
            "  Active --> Done"
        )

        assert "<svg" in svg
        assert "</svg>" in svg
        assert ">Idle</text>" in svg
        assert ">Active</text>" in svg
        assert ">Done</text>" in svg
        assert ">start</text>" in svg

    def test_renders_start_pseudostate_as_filled_circle(self):
        svg = render_mermaid(
            "stateDiagram-v2\n"
            "  [*] --> Ready"
        )
        assert 'stroke="none"' in svg
        assert "<circle" in svg

    def test_renders_end_pseudostate_as_bullseye(self):
        svg = render_mermaid(
            "stateDiagram-v2\n"
            "  Done --> [*]"
        )
        circle_count = len(re.findall(r"<circle", svg))
        assert circle_count >= 2

    def test_renders_composite_state_with_inner_nodes(self):
        svg = render_mermaid(
            "stateDiagram-v2\n"
            "  state Processing {\n"
            "    parse --> validate\n"
            "    validate --> execute\n"
            "  }\n"
            "  [*] --> Processing"
        )

        assert ">Processing</text>" in svg
        assert ">parse</text>" in svg
        assert ">validate</text>" in svg
        assert ">execute</text>" in svg

    def test_renders_full_state_diagram_lifecycle(self):
        svg = render_mermaid(
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

        assert "<svg" in svg
        assert "</svg>" in svg
        assert ">Idle</text>" in svg
        assert ">Complete</text>" in svg
        assert ">Processing</text>" in svg
        assert ">submit</text>" in svg
        assert ">done</text>" in svg

    @pytest.mark.xfail(reason="grandalf layout may produce overlapping labels in cycles (differs from dagre)")
    def test_cycle_edge_labels_do_not_overlap(self):
        svg = render_mermaid(
            "stateDiagram-v2\n"
            "  [*] --> Ready\n"
            "  Ready --> Running : start\n"
            "  Running --> Paused : pause\n"
            "  Paused --> Running : resume\n"
            "  Running --> Stopped : stop\n"
            "  Stopped --> [*]"
        )

        pill_pattern = re.compile(
            r'<rect x="([^"]+)" y="([^"]+)" width="([^"]+)" height="([^"]+)" rx="4"'
        )
        pills = []
        for m in pill_pattern.finditer(svg):
            pills.append({
                "x": float(m.group(1)),
                "y": float(m.group(2)),
                "w": float(m.group(3)),
                "h": float(m.group(4)),
            })

        assert len(pills) >= 3

        for i in range(len(pills)):
            for j in range(i + 1, len(pills)):
                a = pills[i]
                b = pills[j]
                overlap_x = a["x"] < b["x"] + b["w"] and a["x"] + a["w"] > b["x"]
                overlap_y = a["y"] < b["y"] + b["h"] and a["y"] + a["h"] > b["y"]
                assert not (overlap_x and overlap_y), (
                    f"Label pills {i} and {j} overlap"
                )


# ============================================================================
# Source order and deduplication
# ============================================================================


class TestSourceOrder:
    def test_does_not_duplicate_composite_state_nodes_in_svg(self):
        svg = render_mermaid(
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

        processing_labels = len(re.findall(r">Processing</text>", svg))
        assert processing_labels == 1

    def test_renders_subgraph_first_diagrams_with_subgraph_at_top(self):
        svg = render_mermaid(
            "graph TD\n"
            "  subgraph ci [CI Pipeline]\n"
            "    A[Push Code] --> B{Tests Pass?}\n"
            "    B -->|Yes| C[Build Image]\n"
            "  end\n"
            "  C --> D([Deploy])\n"
            "  D --> E{QA?}\n"
            "  E -->|Yes| F((Production))"
        )

        assert ">CI Pipeline</text>" in svg
        assert ">Push Code</text>" in svg
        assert ">Deploy</text>" in svg
        assert ">Production</text>" in svg


# ============================================================================
# Edge cases: self-loops, empty subgraphs, nesting depth
# ============================================================================


class TestEdgeCases:
    def test_renders_a_self_loop(self):
        svg = render_mermaid("graph TD\n  A[Node] --> A")
        assert "<svg" in svg
        assert ">Node</text>" in svg
        assert "<polyline" in svg

    def test_renders_a_self_loop_with_label(self):
        svg = render_mermaid("graph TD\n  A[Retry] -->|again| A")
        assert ">Retry</text>" in svg
        assert ">again</text>" in svg

    def test_renders_an_empty_subgraph_without_crashing(self):
        svg = render_mermaid(
            "graph TD\n"
            "  subgraph Empty\n"
            "  end\n"
            "  A --> B"
        )
        assert "<svg" in svg
        assert ">Empty</text>" in svg
        assert ">A</text>" in svg
        assert ">B</text>" in svg

    def test_renders_edges_targeting_an_empty_subgraph(self):
        svg = render_mermaid(
            "graph TD\n"
            "  subgraph S [Empty Group]\n"
            "  end\n"
            "  A --> S\n"
            "  S --> B"
        )
        assert "<svg" in svg
        assert ">Empty Group</text>" in svg
        assert ">A</text>" in svg
        assert ">B</text>" in svg

    def test_renders_a_single_node_subgraph(self):
        svg = render_mermaid(
            "graph TD\n"
            "  subgraph Single\n"
            "    A[Only Node]\n"
            "  end\n"
            "  B --> A"
        )
        assert ">Single</text>" in svg
        assert ">Only Node</text>" in svg
        assert ">B</text>" in svg

    def test_renders_3_level_nested_subgraphs(self):
        svg = render_mermaid(
            "graph TD\n"
            "  subgraph Level1 [Outer]\n"
            "    subgraph Level2 [Middle]\n"
            "      subgraph Level3 [Inner]\n"
            "        A[Deep Node] --> B[Also Deep]\n"
            "      end\n"
            "    end\n"
            "  end\n"
            "  C[Outside] --> A"
        )

        assert ">Outer</text>" in svg
        assert ">Middle</text>" in svg
        assert ">Inner</text>" in svg
        assert ">Deep Node</text>" in svg
        assert ">Also Deep</text>" in svg
        assert ">Outside</text>" in svg

    def test_renders_3_level_nested_composite_states(self):
        svg = render_mermaid(
            "stateDiagram-v2\n"
            "  [*] --> Active\n"
            "  state Active {\n"
            "    state Processing {\n"
            "      state Validating {\n"
            "        check --> verify\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "  Active --> [*]"
        )

        assert "<svg" in svg
        assert ">Active</text>" in svg
        assert ">Processing</text>" in svg
        assert ">Validating</text>" in svg
        assert ">check</text>" in svg
        assert ">verify</text>" in svg


# ============================================================================
# All new shapes in one diagram (end-to-end stress test)
# ============================================================================


class TestAllShapesCombined:
    def test_renders_a_diagram_with_all_12_flowchart_shapes(self):
        svg = render_mermaid(
            "graph LR\n"
            "  A[Rectangle] --> B(Rounded)\n"
            "  B --> C{Diamond}\n"
            "  C --> D([Stadium])\n"
            "  D --> E((Circle))\n"
            "  E --> F[[Subroutine]]\n"
            "  F --> G(((DoubleCircle)))\n"
            "  G --> H{{Hexagon}}\n"
            "  H --> I[(Cylinder)]\n"
            "  I --> J>Flag]\n"
            "  J --> K[/Trapezoid\\]\n"
            "  K --> L[\\TrapAlt/]"
        )

        for label in [
            "Rectangle", "Rounded", "Diamond", "Stadium", "Circle",
            "Subroutine", "DoubleCircle", "Hexagon", "Cylinder",
            "Flag", "Trapezoid", "TrapAlt",
        ]:
            assert f">{label}</text>" in svg

        assert "<svg" in svg
        assert "</svg>" in svg
