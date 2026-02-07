from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ============================================================================
# Class diagram types
#
# Models the parsed and positioned representations of a Mermaid class diagram.
# Class diagrams show UML class relationships, inheritance, composition, etc.
# ============================================================================

# Parsed class diagram -- logical structure from mermaid text

Visibility = Literal["+", "-", "#", "~", ""]

RelationshipType = Literal[
    "inheritance",   # A <|-- B   (solid line, hollow triangle)
    "composition",   # A *-- B    (solid line, filled diamond)
    "aggregation",   # A o-- B    (solid line, hollow diamond)
    "association",   # A --> B    (solid line, open arrow)
    "dependency",    # A ..> B    (dashed line, open arrow)
    "realization",   # A ..|> B   (dashed line, hollow triangle)
]

MarkerAt = Literal["from", "to"]


@dataclass(slots=True)
class ClassMember:
    """A single class member (attribute or method)."""

    # Visibility: + public, - private, # protected, ~ package
    visibility: Visibility
    # Member name
    name: str
    # Type annotation (e.g., "String", "int", "void")
    type: str | None = None
    # Whether the member is static (underlined in UML)
    is_static: bool = False
    # Whether the member is abstract (italic in UML)
    is_abstract: bool = False


@dataclass(slots=True)
class ClassNode:
    """A class definition in the diagram."""

    id: str
    label: str
    # Annotation like <<interface>>, <<abstract>>, <<service>>, <<enumeration>>
    annotation: str | None = None
    # Class attributes (fields/properties)
    attributes: list[ClassMember] = field(default_factory=list)
    # Class methods (functions)
    methods: list[ClassMember] = field(default_factory=list)


@dataclass(slots=True)
class ClassRelationship:
    """A relationship between two classes."""

    from_: str
    to: str
    type: RelationshipType
    # Which end of the relationship line has the UML marker (triangle, diamond, arrow).
    # Determined by the arrow syntax direction:
    #   - Prefix markers like `<|--`, `*--`, `o--` -> 'from' (marker on left/from side)
    #   - Suffix markers like `..|>`, `-->`, `..>`, `--*`, `--o` -> 'to' (marker on right/to side)
    marker_at: MarkerAt
    # Label on the relationship line
    label: str | None = None
    # Cardinality at the "from" end (e.g., "1", "*", "0..1")
    from_cardinality: str | None = None
    # Cardinality at the "to" end
    to_cardinality: str | None = None


@dataclass(slots=True)
class ClassNamespace:
    """A namespace grouping of classes."""

    name: str
    class_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ClassDiagram:
    """Parsed class diagram -- logical structure from mermaid text."""

    # All class definitions
    classes: list[ClassNode] = field(default_factory=list)
    # Relationships between classes
    relationships: list[ClassRelationship] = field(default_factory=list)
    # Optional namespace groupings
    namespaces: list[ClassNamespace] = field(default_factory=list)


# ============================================================================
# Positioned class diagram -- ready for SVG rendering
# ============================================================================


@dataclass(slots=True)
class PositionedClassNode:
    """A class node with computed position and dimensions."""

    id: str
    label: str
    annotation: str | None
    attributes: list[ClassMember]
    methods: list[ClassMember]
    x: float
    y: float
    width: float
    height: float
    # Height of the header section (name + annotation)
    header_height: float
    # Height of the attributes section
    attr_height: float
    # Height of the methods section
    method_height: float


@dataclass(slots=True)
class PositionedClassRelationship:
    """A relationship with computed path points."""

    from_: str
    to: str
    type: RelationshipType
    # Which end of the line has the UML marker -- propagated from ClassRelationship
    marker_at: MarkerAt
    label: str | None
    from_cardinality: str | None
    to_cardinality: str | None
    # Path points from source to target
    points: list[dict[str, float]]
    # Layout-computed label center position (avoids overlaps between nearby edges)
    label_position: dict[str, float] | None = None


@dataclass(slots=True)
class PositionedClassDiagram:
    """Fully positioned class diagram ready for SVG rendering."""

    width: float
    height: float
    classes: list[PositionedClassNode] = field(default_factory=list)
    relationships: list[PositionedClassRelationship] = field(default_factory=list)
