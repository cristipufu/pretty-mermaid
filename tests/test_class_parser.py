"""Tests for the class diagram parser.

Covers: class blocks, attributes, methods, visibility, annotations,
relationships (all 6 types), cardinality, labels, inline attributes.
"""
from __future__ import annotations

import pytest

from pretty_mermaid.class_diagram.parser import parse_class_diagram


def parse(text: str):
    """Helper to parse -- preprocesses text the same way __init__.py does."""
    lines = [
        l.strip()
        for l in text.split("\n")
        if l.strip() and not l.strip().startswith("%%")
    ]
    return parse_class_diagram(lines)


# ============================================================================
# Class definitions
# ============================================================================


class TestClassDefinitions:
    def test_parses_a_class_block_with_attributes_and_methods(self):
        d = parse(
            "classDiagram\n"
            "  class Animal {\n"
            "    +String name\n"
            "    +int age\n"
            "    +eat() void\n"
            "    +sleep()\n"
            "  }"
        )
        assert len(d.classes) == 1
        assert d.classes[0].id == "Animal"
        assert len(d.classes[0].attributes) == 2
        assert len(d.classes[0].methods) == 2

    def test_parses_attribute_visibility(self):
        d = parse(
            "classDiagram\n"
            "  class MyClass {\n"
            "    +String publicField\n"
            "    -int privateField\n"
            "    #double protectedField\n"
            "    ~bool packageField\n"
            "  }"
        )
        assert d.classes[0].attributes[0].visibility == "+"
        assert d.classes[0].attributes[1].visibility == "-"
        assert d.classes[0].attributes[2].visibility == "#"
        assert d.classes[0].attributes[3].visibility == "~"

    def test_parses_method_with_return_type(self):
        d = parse(
            "classDiagram\n"
            "  class Calc {\n"
            "    +add(a, b) int\n"
            "  }"
        )
        assert d.classes[0].methods[0].name == "add"
        assert d.classes[0].methods[0].type == "int"

    def test_parses_annotation_interface(self):
        d = parse(
            "classDiagram\n"
            "  class Flyable {\n"
            "    <<interface>>\n"
            "    +fly() void\n"
            "  }"
        )
        assert d.classes[0].annotation == "interface"
        assert len(d.classes[0].methods) == 1

    def test_parses_inline_annotation_syntax(self):
        d = parse(
            "classDiagram\n"
            "  class Shape { <<abstract>> }"
        )
        assert d.classes[0].annotation == "abstract"

    def test_parses_standalone_class_declaration(self):
        d = parse(
            "classDiagram\n"
            "  class EmptyClass"
        )
        assert len(d.classes) == 1
        assert d.classes[0].id == "EmptyClass"

    def test_auto_creates_classes_from_relationships(self):
        d = parse(
            "classDiagram\n"
            "  Animal <|-- Dog"
        )
        assert len(d.classes) == 2
        assert any(c.id == "Animal" for c in d.classes)
        assert any(c.id == "Dog" for c in d.classes)


# ============================================================================
# Inline attributes
# ============================================================================


class TestInlineAttributes:
    def test_parses_inline_attribute(self):
        d = parse(
            "classDiagram\n"
            "  class Animal\n"
            "  Animal : +String name\n"
            "  Animal : +int age"
        )
        cls = next(c for c in d.classes if c.id == "Animal")
        assert len(cls.attributes) == 2
        assert cls.attributes[0].name == "name"


# ============================================================================
# Relationships
# ============================================================================


class TestRelationships:
    def test_parses_inheritance(self):
        d = parse(
            "classDiagram\n"
            "  Animal <|-- Dog"
        )
        assert len(d.relationships) == 1
        assert d.relationships[0].type == "inheritance"
        assert d.relationships[0].from_ == "Animal"
        assert d.relationships[0].to == "Dog"
        assert d.relationships[0].marker_at == "from"

    def test_parses_composition(self):
        d = parse(
            "classDiagram\n"
            "  Car *-- Engine"
        )
        assert d.relationships[0].type == "composition"
        assert d.relationships[0].marker_at == "from"

    def test_parses_aggregation(self):
        d = parse(
            "classDiagram\n"
            "  University o-- Department"
        )
        assert d.relationships[0].type == "aggregation"
        assert d.relationships[0].marker_at == "from"

    def test_parses_association(self):
        d = parse(
            "classDiagram\n"
            "  Customer --> Order"
        )
        assert d.relationships[0].type == "association"
        assert d.relationships[0].marker_at == "to"

    def test_parses_dependency(self):
        d = parse(
            "classDiagram\n"
            "  Service ..> Repository"
        )
        assert d.relationships[0].type == "dependency"
        assert d.relationships[0].marker_at == "to"

    def test_parses_realization(self):
        d = parse(
            "classDiagram\n"
            "  Bird ..|> Flyable"
        )
        assert d.relationships[0].type == "realization"
        assert d.relationships[0].marker_at == "to"

    # --- Reversed arrow variants ---

    def test_parses_reversed_realization(self):
        d = parse(
            "classDiagram\n"
            "  Flyable <|.. Bird"
        )
        assert d.relationships[0].type == "realization"
        assert d.relationships[0].from_ == "Flyable"
        assert d.relationships[0].to == "Bird"
        assert d.relationships[0].marker_at == "from"

    def test_parses_reversed_composition(self):
        d = parse(
            "classDiagram\n"
            "  Engine --* Car"
        )
        assert d.relationships[0].type == "composition"
        assert d.relationships[0].from_ == "Engine"
        assert d.relationships[0].to == "Car"
        assert d.relationships[0].marker_at == "to"

    def test_parses_reversed_aggregation(self):
        d = parse(
            "classDiagram\n"
            "  Department --o University"
        )
        assert d.relationships[0].type == "aggregation"
        assert d.relationships[0].from_ == "Department"
        assert d.relationships[0].to == "University"
        assert d.relationships[0].marker_at == "to"

    def test_parses_relationship_with_label(self):
        d = parse(
            "classDiagram\n"
            "  Customer --> Order : places"
        )
        assert d.relationships[0].label == "places"

    def test_parses_relationship_with_cardinality(self):
        d = parse(
            'classDiagram\n'
            '  Customer "1" --> "*" Order : places'
        )
        assert d.relationships[0].from_cardinality == "1"
        assert d.relationships[0].to_cardinality == "*"

    def test_handles_multiple_relationships(self):
        d = parse(
            "classDiagram\n"
            "  Animal <|-- Dog\n"
            "  Animal <|-- Cat\n"
            "  Dog *-- Leg"
        )
        assert len(d.relationships) == 3


# ============================================================================
# Full diagram
# ============================================================================


class TestFullDiagram:
    def test_parses_a_complete_class_hierarchy(self):
        d = parse(
            "classDiagram\n"
            "  class Animal {\n"
            "    <<abstract>>\n"
            "    +String name\n"
            "    +eat() void\n"
            "    +sleep() void\n"
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

        assert len(d.classes) == 3
        assert len(d.relationships) == 2
        animal = next(c for c in d.classes if c.id == "Animal")
        assert animal.annotation == "abstract"
        assert len(animal.attributes) == 1
        assert len(animal.methods) == 2
