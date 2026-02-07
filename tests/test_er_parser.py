"""Tests for the ER diagram parser.

Covers: entity definitions, attribute parsing (types, names, keys, comments),
relationships with all cardinality types, identifying/non-identifying lines.
"""
from __future__ import annotations

import pytest

from pretty_mermaid.er.parser import parse_er_diagram


def parse(text: str):
    """Helper to parse -- preprocesses text the same way __init__.py does."""
    lines = [
        l.strip()
        for l in text.split("\n")
        if l.strip() and not l.strip().startswith("%%")
    ]
    return parse_er_diagram(lines)


# ============================================================================
# Entity definitions
# ============================================================================


class TestEntityDefinitions:
    def test_parses_an_entity_with_attributes(self):
        d = parse(
            "erDiagram\n"
            "  CUSTOMER {\n"
            "    string name\n"
            "    int age\n"
            "    string email\n"
            "  }"
        )
        assert len(d.entities) == 1
        assert d.entities[0].id == "CUSTOMER"
        assert len(d.entities[0].attributes) == 3
        assert d.entities[0].attributes[0].type == "string"
        assert d.entities[0].attributes[0].name == "name"

    def test_parses_attributes_with_pk_key(self):
        d = parse(
            "erDiagram\n"
            "  USER {\n"
            "    int id PK\n"
            "    string name\n"
            "  }"
        )
        assert "PK" in d.entities[0].attributes[0].keys

    def test_parses_attributes_with_fk_key(self):
        d = parse(
            "erDiagram\n"
            "  ORDER {\n"
            "    int id PK\n"
            "    int customer_id FK\n"
            "  }"
        )
        assert "FK" in d.entities[0].attributes[1].keys

    def test_parses_attributes_with_uk_key(self):
        d = parse(
            "erDiagram\n"
            "  USER {\n"
            "    string email UK\n"
            "  }"
        )
        assert "UK" in d.entities[0].attributes[0].keys

    def test_parses_attributes_with_comment(self):
        d = parse(
            "erDiagram\n"
            '  USER {\n'
            '    string email UK "user email address"\n'
            '  }'
        )
        assert d.entities[0].attributes[0].comment == "user email address"

    def test_parses_multiple_entities(self):
        d = parse(
            "erDiagram\n"
            "  CUSTOMER {\n"
            "    int id PK\n"
            "    string name\n"
            "  }\n"
            "  ORDER {\n"
            "    int id PK\n"
            "    date created\n"
            "  }"
        )
        assert len(d.entities) == 2

    def test_auto_creates_entities_from_relationships(self):
        d = parse(
            "erDiagram\n"
            "  CUSTOMER ||--o{ ORDER : places"
        )
        assert len(d.entities) == 2
        assert any(e.id == "CUSTOMER" for e in d.entities)
        assert any(e.id == "ORDER" for e in d.entities)


# ============================================================================
# Relationships
# ============================================================================


class TestRelationships:
    def test_parses_exactly_one_to_zero_or_many(self):
        d = parse(
            "erDiagram\n"
            "  CUSTOMER ||--o{ ORDER : places"
        )
        assert len(d.relationships) == 1
        assert d.relationships[0].entity1 == "CUSTOMER"
        assert d.relationships[0].entity2 == "ORDER"
        assert d.relationships[0].cardinality1 == "one"
        assert d.relationships[0].cardinality2 == "zero-many"
        assert d.relationships[0].label == "places"
        assert d.relationships[0].identifying is True

    def test_parses_zero_or_one_to_one_or_more(self):
        d = parse(
            "erDiagram\n"
            "  A |o--|{ B : connects"
        )
        assert d.relationships[0].cardinality1 == "zero-one"
        assert d.relationships[0].cardinality2 == "many"

    def test_parses_exactly_one_to_exactly_one(self):
        d = parse(
            "erDiagram\n"
            "  PERSON ||--|| PASSPORT : has"
        )
        assert d.relationships[0].cardinality1 == "one"
        assert d.relationships[0].cardinality2 == "one"

    def test_parses_non_identifying_relationship_dotted(self):
        d = parse(
            "erDiagram\n"
            "  USER ||..o{ LOG : generates"
        )
        assert d.relationships[0].identifying is False

    def test_parses_one_or_more_to_zero_or_many(self):
        d = parse(
            "erDiagram\n"
            "  PRODUCT }|--o{ TAG : has"
        )
        assert d.relationships[0].cardinality1 == "many"
        assert d.relationships[0].cardinality2 == "zero-many"

    def test_handles_multiple_relationships(self):
        d = parse(
            "erDiagram\n"
            "  CUSTOMER ||--o{ ORDER : places\n"
            "  ORDER ||--|{ LINE_ITEM : contains\n"
            "  PRODUCT ||--o{ LINE_ITEM : appears_in"
        )
        assert len(d.relationships) == 3


# ============================================================================
# Full diagram
# ============================================================================


class TestFullDiagram:
    def test_parses_a_complete_e_commerce_schema(self):
        d = parse(
            "erDiagram\n"
            "  CUSTOMER {\n"
            "    int id PK\n"
            "    string name\n"
            "    string email UK\n"
            "  }\n"
            "  ORDER {\n"
            "    int id PK\n"
            "    date created\n"
            "    int customer_id FK\n"
            "  }\n"
            "  LINE_ITEM {\n"
            "    int id PK\n"
            "    int quantity\n"
            "    int order_id FK\n"
            "    int product_id FK\n"
            "  }\n"
            "  PRODUCT {\n"
            "    int id PK\n"
            "    string name\n"
            "    float price\n"
            "  }\n"
            "  CUSTOMER ||--o{ ORDER : places\n"
            "  ORDER ||--|{ LINE_ITEM : contains\n"
            "  PRODUCT ||--o{ LINE_ITEM : includes"
        )

        assert len(d.entities) == 4
        assert len(d.relationships) == 3

        customer = next(e for e in d.entities if e.id == "CUSTOMER")
        assert len(customer.attributes) == 3
        assert "PK" in customer.attributes[0].keys
        assert "UK" in customer.attributes[2].keys

        line_item = next(e for e in d.entities if e.id == "LINE_ITEM")
        assert len([a for a in line_item.attributes if "FK" in a.keys]) == 2
