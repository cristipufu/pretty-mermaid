from __future__ import annotations

import re
from typing import Literal

from .types import ErDiagram, ErEntity, ErAttribute, ErRelationship, Cardinality

# ============================================================================
# ER diagram parser
#
# Parses Mermaid erDiagram syntax into an ErDiagram structure.
#
# Supported syntax:
#   CUSTOMER ||--o{ ORDER : places
#   CUSTOMER {
#     string name PK
#     int age
#     string email UK "user email"
#   }
#
# Cardinality notation:
#   ||  exactly one
#   o|  zero or one (also |o)
#   }|  one or more (also |{)
#   o{  zero or more (also {o)
#
# Line style:
#   --  identifying (solid line)
#   ..  non-identifying (dashed line)
# ============================================================================


def parse_er_diagram(lines: list[str]) -> ErDiagram:
    """Parse a Mermaid ER diagram.

    Expects the first line to be "erDiagram".
    """
    diagram = ErDiagram()

    # Track entities by ID for deduplication
    entity_map: dict[str, ErEntity] = {}
    # Track entity body parsing
    current_entity: ErEntity | None = None

    for i in range(1, len(lines)):
        line = lines[i]

        # --- Inside entity body ---
        if current_entity is not None:
            if line == "}":
                current_entity = None
                continue

            # Attribute line: type name [PK|FK|UK] ["comment"]
            attr = _parse_attribute(line)
            if attr is not None:
                current_entity.attributes.append(attr)
            continue

        # --- Entity block start: `ENTITY_NAME {` ---
        entity_block_match = re.match(r"^(\S+)\s*\{$", line)
        if entity_block_match:
            entity_id = entity_block_match.group(1)
            entity = _ensure_entity(entity_map, entity_id)
            current_entity = entity
            continue

        # --- Relationship: `ENTITY1 cardinality1--cardinality2 ENTITY2 : label` ---
        rel = _parse_relationship_line(line)
        if rel is not None:
            # Ensure both entities exist
            _ensure_entity(entity_map, rel.entity1)
            _ensure_entity(entity_map, rel.entity2)
            diagram.relationships.append(rel)
            continue

    diagram.entities = list(entity_map.values())
    return diagram


def _ensure_entity(entity_map: dict[str, ErEntity], entity_id: str) -> ErEntity:
    """Ensure an entity exists in the map."""
    entity = entity_map.get(entity_id)
    if entity is None:
        entity = ErEntity(id=entity_id, label=entity_id)
        entity_map[entity_id] = entity
    return entity


def _parse_attribute(line: str) -> ErAttribute | None:
    """Parse an attribute line inside an entity block.

    Format: type name [PK|FK|UK [...]] ["comment"]
    """
    match = re.match(r"^(\S+)\s+(\S+)(?:\s+(.+))?$", line)
    if not match:
        return None

    attr_type = match.group(1)
    attr_name = match.group(2)
    rest = (match.group(3) or "").strip()

    # Extract key constraints (PK, FK, UK) and optional comment
    keys: list[Literal["PK", "FK", "UK"]] = []
    comment: str | None = None

    # Extract quoted comment first
    comment_match = re.search(r'"([^"]*)"', rest)
    if comment_match:
        comment = comment_match.group(1)

    # Extract key constraints
    rest_without_comment = re.sub(r'"[^"]*"', "", rest).strip()
    for part in rest_without_comment.split():
        upper = part.upper()
        if upper in ("PK", "FK", "UK"):
            keys.append(upper)  # type: ignore[arg-type]

    return ErAttribute(type=attr_type, name=attr_name, keys=keys, comment=comment)


def _parse_relationship_line(line: str) -> ErRelationship | None:
    """Parse a relationship line.

    Cardinality symbols on each side of the line style:
      Left side (entity1):  ||  |o  o|  }|  |{  o{  {o
      Line:                 --  (identifying) or  ..  (non-identifying)
      Right side (entity2): ||  o|  |o  |{  }|  {o  o{

    Full pattern example: CUSTOMER ||--o{ ORDER : places
    """
    # Match: ENTITY1 <cardinality_and_line> ENTITY2 : label
    match = re.match(r"^(\S+)\s+([|o}{]+(?:--|\.\.)[\|o}{]+)\s+(\S+)\s*:\s*(.+)$", line)
    if not match:
        return None

    entity1 = match.group(1)
    cardinality_str = match.group(2)
    entity2 = match.group(3)
    label = match.group(4).strip()

    # Split the cardinality string into left side, line style, right side
    line_match = re.match(r"^([|o}{]+)(--|\.\.?)([|o}{]+)$", cardinality_str)
    if not line_match:
        return None

    left_str = line_match.group(1)
    line_style = line_match.group(2)
    right_str = line_match.group(3)

    cardinality1 = _parse_cardinality(left_str)
    cardinality2 = _parse_cardinality(right_str)
    identifying = line_style == "--"

    if cardinality1 is None or cardinality2 is None:
        return None

    return ErRelationship(
        entity1=entity1,
        entity2=entity2,
        cardinality1=cardinality1,
        cardinality2=cardinality2,
        label=label,
        identifying=identifying,
    )


def _parse_cardinality(s: str) -> Cardinality | None:
    """Parse a cardinality notation string into a Cardinality type."""
    # Normalize: sort the characters to handle both orders (e.g., |o and o|)
    sorted_s = "".join(sorted(s))

    # Exact one: || -> sorted "||"
    if sorted_s == "||":
        return "one"
    # Zero or one: o| or |o -> sorted "o|" (o=111 < |=124 in char codes)
    # In Python, ord('|') = 124, ord('o') = 111, so sorted is "|o"... wait,
    # actually sorted() sorts by char code: 'o' (111) < '|' (124), so "o|" sorts to "o|"
    # But in the TS version sorted "o|" matched. Let's check:
    # 'o' = 111, '|' = 124 -> sorted('o|') = 'o|', sorted('|o') = 'o|'
    if sorted_s == "o|":
        return "zero-one"
    # One or more: }| or |{ -> sorted "|}" or "{|"
    # '{' = 123, '|' = 124, '}' = 125
    # sorted('}|') = '|}', sorted('|{') = '{|'
    if sorted_s == "|}" or sorted_s == "{|":
        return "many"
    # Zero or more: o{ or {o -> sorted "{o" or "o{"
    # '{' = 123, 'o' = 111 -> sorted('o{') = '{o'... wait:
    # ord('o')=111, ord('{')=123 -> sorted is 'o{' ... no, 111 < 123 so sorted('o{') = 'o{'
    # Actually sorted sorts ascending: 'o' (111) < '{' (123), so sorted = 'o{'
    # sorted('{o') = 'o{' as well
    if sorted_s == "o{" or sorted_s == "{o":
        return "zero-many"

    return None
