from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ============================================================================
# ER diagram types
#
# Models the parsed and positioned representations of a Mermaid ER diagram.
# ER diagrams show database entities, their attributes, and relationships.
# ============================================================================

# Cardinality notation (crow's foot):
#   'one'       ||  exactly one
#   'zero-one'  |o  zero or one
#   'many'      }|  one or more
#   'zero-many' o{  zero or more
Cardinality = Literal["one", "zero-one", "many", "zero-many"]


@dataclass(slots=True)
class ErAttribute:
    """A single attribute (column) of an ER entity."""

    # Data type (string, int, varchar, etc.)
    type: str
    # Attribute name
    name: str
    # Key constraints: PK, FK, UK
    keys: list[Literal["PK", "FK", "UK"]] = field(default_factory=list)
    # Optional comment
    comment: str | None = None


@dataclass(slots=True)
class ErEntity:
    """An entity definition in an ER diagram."""

    id: str
    # Display name (same as id unless aliased)
    label: str
    # Entity attributes (columns)
    attributes: list[ErAttribute] = field(default_factory=list)


@dataclass(slots=True)
class ErRelationship:
    """A relationship between two entities."""

    entity1: str
    entity2: str
    # Cardinality at entity1's end
    cardinality1: Cardinality
    # Cardinality at entity2's end
    cardinality2: Cardinality
    # Relationship verb/label (e.g., "places", "contains")
    label: str
    # Whether the relationship is identifying (solid line) or non-identifying (dashed)
    identifying: bool


@dataclass(slots=True)
class ErDiagram:
    """Parsed ER diagram -- logical structure from mermaid text."""

    # All entity definitions
    entities: list[ErEntity] = field(default_factory=list)
    # Relationships between entities
    relationships: list[ErRelationship] = field(default_factory=list)


# ============================================================================
# Positioned ER diagram -- ready for SVG rendering
# ============================================================================


@dataclass(slots=True)
class PositionedErEntity:
    """A positioned entity box ready for rendering."""

    id: str
    label: str
    attributes: list[ErAttribute]
    x: float
    y: float
    width: float
    height: float
    # Height of the header row
    header_height: float
    # Height per attribute row
    row_height: float


@dataclass(slots=True)
class PositionedErRelationship:
    """A positioned relationship with path points."""

    entity1: str
    entity2: str
    cardinality1: Cardinality
    cardinality2: Cardinality
    label: str
    identifying: bool
    # Path points from entity1 to entity2
    points: list[tuple[float, float]] = field(default_factory=list)


@dataclass(slots=True)
class PositionedErDiagram:
    """Fully positioned ER diagram ready for SVG rendering."""

    width: float
    height: float
    entities: list[PositionedErEntity] = field(default_factory=list)
    relationships: list[PositionedErRelationship] = field(default_factory=list)
