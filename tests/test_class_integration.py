"""Integration tests for class diagrams -- end-to-end parse -> layout -> render."""
from __future__ import annotations

import re

import pytest

from pretty_mermaid import render_mermaid
from pretty_mermaid.types import RenderOptions


class TestClassDiagrams:
    def test_renders_a_basic_class_diagram_to_valid_svg(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  class Animal {\n"
            "    +String name\n"
            "    +eat() void\n"
            "  }"
        )
        assert "<svg" in svg
        assert "</svg>" in svg
        assert "Animal" in svg
        assert "name" in svg
        assert "eat" in svg

    def test_renders_class_with_annotation(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  class Flyable {\n"
            "    <<interface>>\n"
            "    +fly() void\n"
            "  }"
        )
        assert "interface" in svg
        assert "Flyable" in svg
        assert "fly" in svg

    def test_renders_inheritance_relationship_with_triangle_marker(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  Animal <|-- Dog"
        )
        assert "Animal" in svg
        assert "Dog" in svg
        assert "cls-inherit" in svg

    def test_renders_composition_with_filled_diamond(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  Car *-- Engine"
        )
        assert "cls-composition" in svg

    def test_renders_aggregation_with_hollow_diamond(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  University o-- Department"
        )
        assert "cls-aggregation" in svg

    def test_renders_dependency_with_dashed_line(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  Service ..> Repository"
        )
        assert "stroke-dasharray" in svg
        assert "cls-arrow" in svg

    def test_renders_realization_with_dashed_line_and_triangle(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  Bird ..|> Flyable"
        )
        assert "stroke-dasharray" in svg
        assert "cls-inherit" in svg

    def test_renders_relationship_labels(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  Customer --> Order : places"
        )
        assert "places" in svg

    def test_renders_class_compartments_with_divider_lines(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  class Animal {\n"
            "    +String name\n"
            "    +eat() void\n"
            "  }"
        )
        lines = re.findall(r"<line ", svg)
        assert len(lines) >= 2

    def test_renders_with_dark_colors(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  class A {\n"
            "    +x int\n"
            "  }",
            RenderOptions(bg="#18181B", fg="#FAFAFA"),
        )
        assert "--bg:#18181B" in svg

    def test_renders_a_complete_class_hierarchy(self):
        svg = render_mermaid(
            "classDiagram\n"
            "  class Animal {\n"
            "    <<abstract>>\n"
            "    +String name\n"
            "    +eat() void\n"
            "  }\n"
            "  class Dog {\n"
            "    +String breed\n"
            "    +bark() void\n"
            "  }\n"
            "  class Cat {\n"
            "    +bool isIndoor\n"
            "    +meow() void\n"
            "  }\n"
            "  Animal <|-- Dog\n"
            "  Animal <|-- Cat"
        )
        assert "Animal" in svg
        assert "Dog" in svg
        assert "Cat" in svg
        assert "abstract" in svg
