"""Comprehensive tests for class diagram arrow directions.

Ensures all relationship types have correctly oriented arrows:
- Inheritance/Realization: hollow triangles point toward parent/interface
- Association/Dependency: filled arrows point from source to target
- Composition/Aggregation: diamonds are omnidirectional
"""
from __future__ import annotations

import pytest

from pretty_mermaid import render_mermaid_ascii


class TestInheritance:
    """Inheritance (<|--)"""

    def test_parent_above_child_triangle_points_up_toward_parent(self):
        diagram = "classDiagram\n  Animal <|-- Dog"
        result = render_mermaid_ascii(diagram)

        assert "\u25b3" in result  # upward triangle
        assert "\u25bd" not in result  # no downward triangle

        lines = result.split("\n")
        animal_line = next(i for i, l in enumerate(lines) if "Animal" in l)
        dog_line = next(i for i, l in enumerate(lines) if "Dog" in l)
        assert animal_line < dog_line

    def test_multiple_inheritance_creates_separate_arrows(self):
        diagram = (
            "classDiagram\n"
            "  Animal <|-- Dog\n"
            "  Animal <|-- Cat\n"
            "  Dog <|-- Puppy"
        )
        result = render_mermaid_ascii(diagram)

        lines = result.split("\n")
        animal_line = next(i for i, l in enumerate(lines) if "Animal" in l)
        dog_line = next(i for i, l in enumerate(lines) if "Dog" in l)
        cat_line = next(i for i, l in enumerate(lines) if "Cat" in l)
        puppy_line = next(i for i, l in enumerate(lines) if "Puppy" in l)

        assert animal_line < dog_line
        assert animal_line < cat_line
        assert dog_line < puppy_line

    def test_multi_level_inheritance_all_triangles_point_up(self):
        diagram = (
            "classDiagram\n"
            "  Animal <|-- Mammal\n"
            "  Mammal <|-- Dog"
        )
        result = render_mermaid_ascii(diagram)

        lines = result.split("\n")
        animal_line = next(i for i, l in enumerate(lines) if "Animal" in l)
        mammal_line = next(i for i, l in enumerate(lines) if "Mammal" in l)
        dog_line = next(i for i, l in enumerate(lines) if "Dog" in l)

        assert animal_line < mammal_line
        assert mammal_line < dog_line

        assert len(result.split("\u25b3")) - 1 == 2  # 2 upward triangles

    def test_multiple_inheritance_from_same_parent(self):
        diagram = (
            "classDiagram\n"
            "  Animal <|-- Dog\n"
            "  Animal <|-- Cat"
        )
        result = render_mermaid_ascii(diagram)

        lines = result.split("\n")
        animal_line = next(i for i, l in enumerate(lines) if "Animal" in l)
        dog_line = next(i for i, l in enumerate(lines) if "Dog" in l)
        cat_line = next(i for i, l in enumerate(lines) if "Cat" in l)

        assert animal_line < dog_line
        assert animal_line < cat_line
        assert "\u25b3" in result

    def test_ascii_mode_uses_caret_for_upward_triangle(self):
        diagram = "classDiagram\n  Animal <|-- Dog"
        result = render_mermaid_ascii(diagram, {"useAscii": True})

        assert "^" in result
        assert "v" not in result


class TestAssociation:
    """Association (-->)"""

    def test_source_above_target_arrow_points_down(self):
        diagram = "classDiagram\n  Person --> Address"
        result = render_mermaid_ascii(diagram)

        assert "\u25bc" in result  # downward arrow
        assert "\u25b2" not in result  # no upward arrow

        lines = result.split("\n")
        person_line = next(i for i, l in enumerate(lines) if "Person" in l)
        address_line = next(i for i, l in enumerate(lines) if "Address" in l)
        assert person_line < address_line

    def test_multiple_associations_from_same_source(self):
        diagram = (
            "classDiagram\n"
            "  Person --> Address\n"
            "  Person --> Phone"
        )
        result = render_mermaid_ascii(diagram)

        lines = result.split("\n")
        person_line = next(i for i, l in enumerate(lines) if "Person" in l)
        address_line = next(i for i, l in enumerate(lines) if "Address" in l)
        phone_line = next(i for i, l in enumerate(lines) if "Phone" in l)

        assert person_line < address_line
        assert person_line < phone_line

    def test_chain_of_associations(self):
        diagram = (
            "classDiagram\n"
            "  A --> B\n"
            "  B --> C"
        )
        result = render_mermaid_ascii(diagram)

        lines = result.split("\n")
        a_line = next(i for i, l in enumerate(lines) if "\u2502 A \u2502" in l)
        b_line = next(i for i, l in enumerate(lines) if "\u2502 B \u2502" in l)
        c_line = next(i for i, l in enumerate(lines) if "\u2502 C \u2502" in l)

        assert a_line < b_line
        assert b_line < c_line

        assert len(result.split("\u25bc")) - 1 == 2

    def test_ascii_mode_uses_v_for_downward_arrow(self):
        diagram = "classDiagram\n  Person --> Address"
        result = render_mermaid_ascii(diagram, {"useAscii": True})

        assert "v" in result
        assert "^" not in result


class TestDependency:
    """Dependency (..>)"""

    def test_source_above_target_arrow_points_down(self):
        diagram = "classDiagram\n  Client ..> Server"
        result = render_mermaid_ascii(diagram)

        assert "\u25bc" in result
        assert "\u25b2" not in result

        lines = result.split("\n")
        client_line = next(i for i, l in enumerate(lines) if "Client" in l)
        server_line = next(i for i, l in enumerate(lines) if "Server" in l)
        assert client_line < server_line

    def test_multiple_dependencies(self):
        diagram = (
            "classDiagram\n"
            "  Client ..> Server\n"
            "  Client ..> Database"
        )
        result = render_mermaid_ascii(diagram)

        lines = result.split("\n")
        client_line = next(i for i, l in enumerate(lines) if "Client" in l)
        server_line = next(i for i, l in enumerate(lines) if "Server" in l)
        db_line = next(i for i, l in enumerate(lines) if "Database" in l)

        assert client_line < server_line
        assert client_line < db_line

    def test_ascii_mode_uses_v_for_downward_arrow(self):
        diagram = "classDiagram\n  Client ..> Server"
        result = render_mermaid_ascii(diagram, {"useAscii": True})

        assert "v" in result


class TestRealization:
    """Realization (..|>)"""

    def test_interface_above_implementation_triangle_points_up(self):
        diagram = "classDiagram\n  Circle ..|> Shape"
        result = render_mermaid_ascii(diagram)

        lines = result.split("\n")
        shape_line = next(i for i, l in enumerate(lines) if "Shape" in l)
        circle_line = next(i for i, l in enumerate(lines) if "Circle" in l)
        assert shape_line < circle_line
        assert "\u25b3" in result

    def test_realization_with_reversed_syntax(self):
        diagram = "classDiagram\n  Shape <|.. Circle"
        result = render_mermaid_ascii(diagram)

        lines = result.split("\n")
        shape_line = next(i for i, l in enumerate(lines) if "Shape" in l)
        circle_line = next(i for i, l in enumerate(lines) if "Circle" in l)
        assert shape_line < circle_line
        assert "\u25b3" in result

    def test_multiple_implementations(self):
        diagram = (
            "classDiagram\n"
            "  Circle ..|> Shape\n"
            "  Square ..|> Shape"
        )
        result = render_mermaid_ascii(diagram)

        lines = result.split("\n")
        shape_line = next(i for i, l in enumerate(lines) if "Shape" in l)
        circle_line = next(i for i, l in enumerate(lines) if "Circle" in l)
        square_line = next(i for i, l in enumerate(lines) if "Square" in l)

        assert shape_line < circle_line
        assert shape_line < square_line
        assert "\u25b3" in result


class TestCompositionAndAggregation:
    """Composition (*--) and Aggregation (o--)"""

    def test_composition_diamond_is_omnidirectional(self):
        diagram = "classDiagram\n  Car *-- Engine"
        result = render_mermaid_ascii(diagram)
        assert "\u25c6" in result

    def test_aggregation_hollow_diamond_is_omnidirectional(self):
        diagram = "classDiagram\n  Team o-- Player"
        result = render_mermaid_ascii(diagram)
        assert "\u25c7" in result


class TestMixedRelationshipScenarios:
    def test_all_6_relationship_types_together(self):
        diagram = (
            "classDiagram\n"
            "  A <|-- B : inheritance\n"
            "  C *-- D : composition\n"
            "  E o-- F : aggregation\n"
            "  G --> H : association\n"
            "  I ..> J : dependency\n"
            "  K ..|> L : realization"
        )
        result = render_mermaid_ascii(diagram)

        assert len(result.split("\u25b3")) - 1 == 2  # inheritance + realization
        assert len(result.split("\u25bc")) - 1 == 2  # association + dependency
        assert "\u25c6" in result  # composition
        assert "\u25c7" in result  # aggregation

    def test_inheritance_with_association_different_arrow_directions(self):
        diagram = (
            "classDiagram\n"
            "  Animal <|-- Dog\n"
            "  Dog --> Food"
        )
        result = render_mermaid_ascii(diagram)

        assert "\u25b3" in result
        assert "\u25bc" in result

    def test_circular_reference_creates_valid_layout(self):
        diagram = (
            "classDiagram\n"
            "  A --> B\n"
            "  B --> C\n"
            "  C ..> A"
        )
        result = render_mermaid_ascii(diagram)

        has_up_arrow = "\u25b2" in result
        has_down_arrow = "\u25bc" in result
        assert has_up_arrow or has_down_arrow
        assert "\u2502 A \u2502" in result
        assert "\u2502 B \u2502" in result
        assert "\u2502 C \u2502" in result


class TestAsciiAndUnicodeConsistency:
    def test_same_diagram_produces_consistent_layouts_in_both_modes(self):
        diagram = (
            "classDiagram\n"
            "  Animal <|-- Dog\n"
            "  Person --> Address"
        )

        unicode_result = render_mermaid_ascii(diagram)
        ascii_result = render_mermaid_ascii(diagram, {"useAscii": True})

        unicode_lines = unicode_result.split("\n")
        ascii_lines = ascii_result.split("\n")

        u_animal = next(i for i, l in enumerate(unicode_lines) if "Animal" in l)
        u_dog = next(i for i, l in enumerate(unicode_lines) if "Dog" in l)
        a_person = next(i for i, l in enumerate(ascii_lines) if "Person" in l)
        a_address = next(i for i, l in enumerate(ascii_lines) if "Address" in l)

        assert u_animal < u_dog
        assert a_person < a_address

        assert "\u25b3" in unicode_result
        assert "\u25bc" in unicode_result
        assert "^" in ascii_result
        assert "v" in ascii_result


class TestEdgeCases:
    def test_single_inheritance_relationship(self):
        diagram = "classDiagram\n  A <|-- B"
        result = render_mermaid_ascii(diagram)

        assert "\u25b3" in result
        lines = result.split("\n")
        a_line = next(i for i, l in enumerate(lines) if "\u2502 A \u2502" in l)
        b_line = next(i for i, l in enumerate(lines) if "\u2502 B \u2502" in l)
        assert a_line < b_line

    def test_classes_with_members_maintain_arrow_directions(self):
        diagram = (
            "classDiagram\n"
            "  class Animal {\n"
            "    +String name\n"
            "    +eat() void\n"
            "  }\n"
            "  class Dog {\n"
            "    +bark() void\n"
            "  }\n"
            "  Animal <|-- Dog"
        )
        result = render_mermaid_ascii(diagram)

        assert "\u25b3" in result
        lines = result.split("\n")
        animal_line = next(i for i, l in enumerate(lines) if "Animal" in l)
        dog_line = next(i for i, l in enumerate(lines) if "Dog" in l)
        assert animal_line < dog_line
