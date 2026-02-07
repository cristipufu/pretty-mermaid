from __future__ import annotations

import re

from .types import SequenceDiagram, Actor, Message, Block, BlockDivider, Note, BlockType

# ============================================================================
# Sequence diagram parser
#
# Parses Mermaid sequenceDiagram syntax into a SequenceDiagram structure.
#
# Supported syntax:
#   participant A as Alice
#   actor B as Bob
#   A->>B: Solid arrow
#   A-->>B: Dashed arrow
#   A-)B: Open arrow
#   A--)B: Dashed open arrow
#   A->>+B: Activate target
#   A-->>-B: Deactivate source
#   loop Label ... end
#   alt Label ... else Label ... end
#   opt Label ... end
#   par Label ... and Label ... end
#   Note left of A: Text
#   Note right of A: Text
#   Note over A,B: Text
# ============================================================================

# Compiled regex patterns
_ACTOR_RE = re.compile(r"^(participant|actor)\s+(\S+?)(?:\s+as\s+(.+))?$")
_NOTE_RE = re.compile(r"^Note\s+(left of|right of|over)\s+([^:]+):\s*(.+)$", re.IGNORECASE)
_BLOCK_RE = re.compile(r"^(loop|alt|opt|par|critical|break|rect)\s*(.*)$")
_DIVIDER_RE = re.compile(r"^(else|and)\s*(.*)$")
_MSG_RE = re.compile(r"^(\S+?)\s*(--?>?>|--?[)x]|--?>>|--?>)\s*([+-]?)(\S+?)\s*:\s*(.+)$")
_SIMPLE_MSG_RE = re.compile(
    r"^(\S+?)\s*(->>|-->>|-\)|--\)|-x|--x|->|-->)\s*([+-]?)(\S+?)\s*:\s*(.+)$"
)


def parse_sequence_diagram(lines: list[str]) -> SequenceDiagram:
    """Parse a Mermaid sequence diagram.

    Expects the first line to be "sequenceDiagram".
    """
    diagram = SequenceDiagram()

    # Track actor IDs to auto-create actors referenced in messages
    actor_ids: set[str] = set()
    # Track block nesting with a stack
    block_stack: list[dict] = []

    for i in range(1, len(lines)):
        line = lines[i]

        # --- Participant / Actor declaration ---
        # "participant A as Alice" or "participant Alice"
        # "actor B as Bob" or "actor Bob"
        actor_match = _ACTOR_RE.match(line)
        if actor_match:
            actor_type = actor_match.group(1)  # 'participant' or 'actor'
            id_ = actor_match.group(2)
            label_group = actor_match.group(3)
            label = label_group.strip() if label_group else id_
            if id_ not in actor_ids:
                actor_ids.add(id_)
                diagram.actors.append(Actor(id=id_, label=label, type=actor_type))  # type: ignore[arg-type]
            continue

        # --- Note ---
        # "Note left of A: text" / "Note right of A: text" / "Note over A,B: text"
        note_match = _NOTE_RE.match(line)
        if note_match:
            pos_str = note_match.group(1).lower()
            actors_str = note_match.group(2).strip()
            text = note_match.group(3).strip()
            note_actor_ids = [s.strip() for s in actors_str.split(",")]

            # Ensure actors exist
            for aid in note_actor_ids:
                _ensure_actor(diagram, actor_ids, aid)

            if pos_str == "left of":
                position = "left"
            elif pos_str == "right of":
                position = "right"
            else:
                position = "over"

            diagram.notes.append(
                Note(
                    actor_ids=note_actor_ids,
                    text=text,
                    position=position,  # type: ignore[arg-type]
                    after_index=len(diagram.messages) - 1,
                )
            )
            continue

        # --- Block start: loop, alt, opt, par, critical, break, rect ---
        block_match = _BLOCK_RE.match(line)
        if block_match:
            block_type = block_match.group(1)
            label = (block_match.group(2) or "").strip()
            block_stack.append({
                "type": block_type,
                "label": label,
                "start_index": len(diagram.messages),
                "dividers": [],
            })
            continue

        # --- Block divider: else, and ---
        divider_match = _DIVIDER_RE.match(line)
        if divider_match and len(block_stack) > 0:
            label = (divider_match.group(2) or "").strip()
            block_stack[-1]["dividers"].append(
                BlockDivider(index=len(diagram.messages), label=label)
            )
            continue

        # --- Block end ---
        if line == "end" and len(block_stack) > 0:
            completed = block_stack.pop()
            diagram.blocks.append(
                Block(
                    type=completed["type"],
                    label=completed["label"],
                    start_index=completed["start_index"],
                    end_index=max(len(diagram.messages) - 1, completed["start_index"]),
                    dividers=completed["dividers"],
                )
            )
            continue

        # --- Message ---
        # Patterns: A->>B, A-->>B, A-)B, A--)B, with optional +/- activation
        # Format: FROM ARROW TO: LABEL
        msg_match = _MSG_RE.match(line)
        if msg_match:
            _parse_message(diagram, actor_ids, msg_match)
            continue

        # --- Simplified message format: A->>B: Label (fallback with more relaxed regex) ---
        simple_msg_match = _SIMPLE_MSG_RE.match(line)
        if simple_msg_match:
            _parse_message(diagram, actor_ids, simple_msg_match)
            continue

        # --- activate / deactivate explicit commands ---
        # These are handled implicitly via +/- on messages but can also appear standalone
        # For now, we skip explicit activate/deactivate lines (they affect rendering only)

    return diagram


def _parse_message(
    diagram: SequenceDiagram,
    actor_ids: set[str],
    match: re.Match[str],
) -> None:
    """Parse a message match and append it to the diagram."""
    from_ = match.group(1)
    arrow = match.group(2)
    activation_mark = match.group(3)
    to = match.group(4)
    label = match.group(5).strip()

    # Ensure both actors exist
    _ensure_actor(diagram, actor_ids, from_)
    _ensure_actor(diagram, actor_ids, to)

    # Determine line style and arrow head from the arrow operator
    line_style = "dashed" if arrow.startswith("--") else "solid"
    # ">>" = filled arrow, ")" or ">" alone = open arrow, "x" = cross (treat as filled)
    arrow_head = "filled" if (">>" in arrow or "x" in arrow) else "open"

    msg = Message(
        from_=from_,
        to=to,
        label=label,
        line_style=line_style,  # type: ignore[arg-type]
        arrow_head=arrow_head,  # type: ignore[arg-type]
    )

    # Activation/deactivation via +/- prefix on target
    if activation_mark == "+":
        msg.activate = True
    if activation_mark == "-":
        msg.deactivate = True

    diagram.messages.append(msg)


def _ensure_actor(
    diagram: SequenceDiagram, actor_ids: set[str], id_: str
) -> None:
    """Ensure an actor exists, creating a default participant if not."""
    if id_ not in actor_ids:
        actor_ids.add(id_)
        diagram.actors.append(Actor(id=id_, label=id_, type="participant"))
