from __future__ import annotations

import re

from .types import (
    ClassDiagram,
    ClassNode,
    ClassRelationship,
    ClassMember,
    ClassNamespace,
    RelationshipType,
    MarkerAt,
    Visibility,
)

# ============================================================================
# Class diagram parser
#
# Parses Mermaid classDiagram syntax into a ClassDiagram structure.
#
# Supported syntax:
#   class Animal { +String name; +eat() void }
#   class Shape { <<abstract>> }
#   Animal <|-- Dog           (inheritance)
#   Car *-- Engine            (composition)
#   Car o-- Wheel             (aggregation)
#   A --> B                   (association)
#   A ..> B                   (dependency)
#   A ..|> B                  (realization)
#   A "1" --> "*" B : label   (with cardinality + label)
#   Animal : +String name     (inline attribute)
#   namespace MyNamespace { class A { } }
# ============================================================================


def parse_class_diagram(lines: list[str]) -> ClassDiagram:
    """Parse a Mermaid class diagram.

    Expects the first line to be "classDiagram".
    """
    diagram = ClassDiagram()

    # Track classes by ID for deduplication
    class_map: dict[str, ClassNode] = {}
    # Track namespace nesting
    current_namespace: ClassNamespace | None = None
    # Track class body parsing
    current_class: ClassNode | None = None
    brace_depth = 0

    for i in range(1, len(lines)):
        line = lines[i]

        # --- Inside a class body block ---
        if current_class is not None and brace_depth > 0:
            if line == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    current_class = None
                continue

            # Check for annotation like <<interface>>
            annot_match = re.match(r"^<<(\w+)>>$", line)
            if annot_match:
                current_class.annotation = annot_match.group(1)
                continue

            # Parse member: visibility, name, type, optional parens for method
            member = _parse_member(line)
            if member is not None:
                member_obj, is_method = member
                if is_method:
                    current_class.methods.append(member_obj)
                else:
                    current_class.attributes.append(member_obj)
            continue

        # --- Namespace block start ---
        ns_match = re.match(r"^namespace\s+(\S+)\s*\{$", line)
        if ns_match:
            current_namespace = ClassNamespace(name=ns_match.group(1))
            continue

        # --- Namespace end ---
        if line == "}" and current_namespace is not None:
            diagram.namespaces.append(current_namespace)
            current_namespace = None
            continue

        # --- Class block start: `class ClassName {` or `class ClassName~Generic~ {` ---
        class_block_match = re.match(r"^class\s+(\S+?)(?:\s*~(\w+)~)?\s*\{$", line)
        if class_block_match:
            cls_id = class_block_match.group(1)
            generic = class_block_match.group(2)
            cls = _ensure_class(class_map, cls_id)
            if generic:
                cls.label = f"{cls_id}<{generic}>"
            current_class = cls
            brace_depth = 1
            if current_namespace is not None:
                current_namespace.class_ids.append(cls_id)
            continue

        # --- Standalone class declaration (no body): `class ClassName` ---
        class_only_match = re.match(r"^class\s+(\S+?)(?:\s*~(\w+)~)?\s*$", line)
        if class_only_match:
            cls_id = class_only_match.group(1)
            generic = class_only_match.group(2)
            cls = _ensure_class(class_map, cls_id)
            if generic:
                cls.label = f"{cls_id}<{generic}>"
            if current_namespace is not None:
                current_namespace.class_ids.append(cls_id)
            continue

        # --- Inline annotation: `class ClassName { <<interface>> }` (single line) ---
        inline_annot_match = re.match(r"^class\s+(\S+?)\s*\{\s*<<(\w+)>>\s*\}$", line)
        if inline_annot_match:
            cls = _ensure_class(class_map, inline_annot_match.group(1))
            cls.annotation = inline_annot_match.group(2)
            continue

        # --- Inline attribute: `ClassName : +String name` ---
        inline_attr_match = re.match(r"^(\S+?)\s*:\s*(.+)$", line)
        if inline_attr_match:
            # Make sure this isn't a relationship line (those have arrows)
            rest = inline_attr_match.group(2)
            if not re.search(r"<\|--|--|\*--|o--|-->|\.\.>|\.\.\|>", rest):
                cls = _ensure_class(class_map, inline_attr_match.group(1))
                member = _parse_member(rest)
                if member is not None:
                    member_obj, is_method = member
                    if is_method:
                        cls.methods.append(member_obj)
                    else:
                        cls.attributes.append(member_obj)
                continue

        # --- Relationship ---
        # Pattern: [FROM] ["card"] ARROW ["card"] [TO] [: label]
        # Arrows: <|--, *--, o--, -->, ..|>, ..>
        # Can also be reversed: --o, --*, --|>
        rel = _parse_relationship(line)
        if rel is not None:
            # Ensure both classes exist
            _ensure_class(class_map, rel.from_)
            _ensure_class(class_map, rel.to)
            diagram.relationships.append(rel)
            continue

    diagram.classes = list(class_map.values())
    return diagram


def _ensure_class(class_map: dict[str, ClassNode], cls_id: str) -> ClassNode:
    """Ensure a class exists in the map, creating a default if needed."""
    cls = class_map.get(cls_id)
    if cls is None:
        cls = ClassNode(id=cls_id, label=cls_id)
        class_map[cls_id] = cls
    return cls


def _parse_member(line: str) -> tuple[ClassMember, bool] | None:
    """Parse a class member line (attribute or method).

    Returns a tuple of (ClassMember, is_method) or None if parsing fails.
    """
    trimmed = line.strip().rstrip(";")
    if not trimmed:
        return None

    # Extract visibility prefix
    visibility: Visibility = ""
    rest = trimmed
    if rest and rest[0] in "+-#~":
        visibility = rest[0]  # type: ignore[assignment]
        rest = rest[1:].strip()

    # Check if it's a method (has parentheses)
    method_match = re.match(r"^(.+?)\(([^)]*)\)(?:\s*(.+))?$", rest)
    if method_match:
        name = method_match.group(1).strip()
        type_ = method_match.group(3)
        type_ = type_.strip() if type_ else None
        # Check for static ($) or abstract (*) markers
        is_static = name.endswith("$") or "$" in rest
        is_abstract = name.endswith("*") or "*" in rest
        return (
            ClassMember(
                visibility=visibility,
                name=re.sub(r"[$*]$", "", name),
                type=type_ or None,
                is_static=is_static,
                is_abstract=is_abstract,
            ),
            True,
        )

    # It's an attribute: [Type] name or name Type
    # Common patterns: "String name", "+int age", "name"
    parts = rest.split()
    if len(parts) >= 2:
        # "Type name" pattern
        type_ = parts[0]
        name = " ".join(parts[1:])
    else:
        name = parts[0] if parts else rest
        type_ = None

    is_static = name.endswith("$")
    is_abstract = name.endswith("*")

    return (
        ClassMember(
            visibility=visibility,
            name=re.sub(r"[$*]$", "", name),
            type=type_ or None,
            is_static=is_static,
            is_abstract=is_abstract,
        ),
        False,
    )


def _parse_relationship(line: str) -> ClassRelationship | None:
    """Parse a relationship line into a ClassRelationship."""
    # Relationship regex -- handles all arrow types with optional cardinality and labels
    # Pattern: FROM ["card"] ARROW ["card"] TO [: label]
    match = re.match(
        r'^(\S+?)\s+(?:"([^"]*?)"\s+)?(<\|--'
        r"|<\|\.\.|\*--|o--|-->|--\*|--o|--|>\s*|\.\.>|\.\.\|>|--)"
        r'\s+(?:"([^"]*?)"\s+)?(\S+?)(?:\s*:\s*(.+))?$',
        line,
    )
    if not match:
        return None

    from_ = match.group(1)
    from_cardinality = match.group(2) or None
    arrow = match.group(3).strip()
    to_cardinality = match.group(4) or None
    to = match.group(5)
    label = match.group(6)
    label = label.strip() if label else None

    parsed = _parse_arrow(arrow)
    if parsed is None:
        return None

    rel_type, marker_at = parsed
    return ClassRelationship(
        from_=from_,
        to=to,
        type=rel_type,
        marker_at=marker_at,
        label=label,
        from_cardinality=from_cardinality,
        to_cardinality=to_cardinality,
    )


def _parse_arrow(arrow: str) -> tuple[RelationshipType, MarkerAt] | None:
    """Map arrow syntax to relationship type and marker placement side.

    Prefix markers (`<|--`, `*--`, `o--`) place the UML shape at the 'from' end.
    Suffix markers (`..|>`, `-->`, `..>`, `--*`, `--o`) place it at the 'to' end.
    """
    mapping: dict[str, tuple[RelationshipType, MarkerAt]] = {
        "<|--": ("inheritance", "from"),
        "<|..": ("realization", "from"),
        "*--": ("composition", "from"),
        "--*": ("composition", "to"),
        "o--": ("aggregation", "from"),
        "--o": ("aggregation", "to"),
        "-->": ("association", "to"),
        "..>": ("dependency", "to"),
        "..|>": ("realization", "to"),
        "--": ("association", "to"),
    }
    return mapping.get(arrow)
