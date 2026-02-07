"""Tests for the sequence diagram parser.

Covers: participants, actors, messages (solid/dashed, filled/open arrows),
activation/deactivation, blocks (loop/alt/opt/par), notes, auto-created actors.
"""
from __future__ import annotations

import pytest

from pretty_mermaid.sequence.parser import parse_sequence_diagram


def parse(text: str):
    """Helper to parse -- preprocesses text the same way __init__.py does."""
    lines = [
        l.strip()
        for l in text.split("\n")
        if l.strip() and not l.strip().startswith("%%")
    ]
    return parse_sequence_diagram(lines)


# ============================================================================
# Actor / Participant declarations
# ============================================================================


class TestActors:
    def test_parses_participant_declarations(self):
        d = parse(
            "sequenceDiagram\n"
            "  participant A as Alice\n"
            "  participant B as Bob\n"
            "  A->>B: Hello"
        )
        assert len(d.actors) == 2
        assert d.actors[0].id == "A"
        assert d.actors[0].label == "Alice"
        assert d.actors[0].type == "participant"

    def test_parses_actor_declarations_stick_figures(self):
        d = parse(
            "sequenceDiagram\n"
            "  actor U as User\n"
            "  participant S as System\n"
            "  U->>S: Click"
        )
        assert d.actors[0].type == "actor"
        assert d.actors[1].type == "participant"

    def test_auto_creates_participants_from_messages(self):
        d = parse(
            "sequenceDiagram\n"
            "  Alice->>Bob: Hello"
        )
        assert len(d.actors) == 2
        assert d.actors[0].id == "Alice"
        assert d.actors[0].label == "Alice"
        assert d.actors[0].type == "participant"

    def test_does_not_duplicate_declared_actors_when_also_used_in_messages(self):
        d = parse(
            "sequenceDiagram\n"
            "  participant A as Alice\n"
            "  A->>B: Hello\n"
            "  B->>A: Hi"
        )
        assert len(d.actors) == 2
        assert d.actors[0].label == "Alice"
        assert d.actors[1].id == "B"

    def test_participant_without_alias_uses_id_as_label(self):
        d = parse(
            "sequenceDiagram\n"
            "  participant Server\n"
            "  Server->>Server: Ping"
        )
        assert d.actors[0].label == "Server"


# ============================================================================
# Messages
# ============================================================================


class TestMessages:
    def test_parses_solid_arrow_message(self):
        d = parse(
            "sequenceDiagram\n"
            "  A->>B: Hello"
        )
        assert len(d.messages) == 1
        assert d.messages[0].from_ == "A"
        assert d.messages[0].to == "B"
        assert d.messages[0].label == "Hello"
        assert d.messages[0].line_style == "solid"
        assert d.messages[0].arrow_head == "filled"

    def test_parses_dashed_arrow_message(self):
        d = parse(
            "sequenceDiagram\n"
            "  A-->>B: Response"
        )
        assert d.messages[0].line_style == "dashed"
        assert d.messages[0].arrow_head == "filled"

    def test_parses_open_arrow_message(self):
        d = parse(
            "sequenceDiagram\n"
            "  A-)B: Async"
        )
        assert d.messages[0].arrow_head == "open"
        assert d.messages[0].line_style == "solid"

    def test_parses_multiple_messages_in_order(self):
        d = parse(
            "sequenceDiagram\n"
            "  A->>B: First\n"
            "  B->>C: Second\n"
            "  C->>A: Third"
        )
        assert len(d.messages) == 3
        assert d.messages[0].label == "First"
        assert d.messages[1].label == "Second"
        assert d.messages[2].label == "Third"

    def test_parses_activation_marker(self):
        d = parse(
            "sequenceDiagram\n"
            "  A->>+B: Activate"
        )
        assert d.messages[0].activate is True

    def test_parses_deactivation_marker(self):
        d = parse(
            "sequenceDiagram\n"
            "  B-->>-A: Deactivate"
        )
        assert d.messages[0].deactivate is True


# ============================================================================
# Blocks (loop, alt, opt, par)
# ============================================================================


class TestBlocks:
    def test_parses_loop_block(self):
        d = parse(
            "sequenceDiagram\n"
            "  A->>B: Start\n"
            "  loop Every 5s\n"
            "    A->>B: Ping\n"
            "  end\n"
            "  A->>B: Done"
        )
        assert len(d.blocks) == 1
        assert d.blocks[0].type == "loop"
        assert d.blocks[0].label == "Every 5s"
        assert d.blocks[0].start_index == 1

    def test_parses_alt_else_block(self):
        d = parse(
            "sequenceDiagram\n"
            "  A->>B: Request\n"
            "  alt Success\n"
            "    B->>A: 200 OK\n"
            "  else Failure\n"
            "    B->>A: 500 Error\n"
            "  end"
        )
        assert len(d.blocks) == 1
        assert d.blocks[0].type == "alt"
        assert d.blocks[0].label == "Success"
        assert len(d.blocks[0].dividers) == 1
        assert d.blocks[0].dividers[0].label == "Failure"

    def test_parses_opt_block(self):
        d = parse(
            "sequenceDiagram\n"
            "  opt Extra logging\n"
            "    A->>Logger: Log\n"
            "  end"
        )
        assert d.blocks[0].type == "opt"

    def test_parses_par_block_with_and_dividers(self):
        d = parse(
            "sequenceDiagram\n"
            "  par Task A\n"
            "    A->>B: Do A\n"
            "  and Task B\n"
            "    A->>C: Do B\n"
            "  end"
        )
        assert d.blocks[0].type == "par"
        assert len(d.blocks[0].dividers) == 1
        assert d.blocks[0].dividers[0].label == "Task B"


# ============================================================================
# Notes
# ============================================================================


class TestNotes:
    def test_parses_note_left_of(self):
        d = parse(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  Note left of A: Important note"
        )
        assert len(d.notes) == 1
        assert d.notes[0].position == "left"
        assert d.notes[0].actor_ids == ["A"]
        assert d.notes[0].text == "Important note"

    def test_parses_note_right_of(self):
        d = parse(
            "sequenceDiagram\n"
            "  Note right of B: Side note\n"
            "  A->>B: Hello"
        )
        assert d.notes[0].position == "right"

    def test_parses_note_over_spanning_multiple_actors(self):
        d = parse(
            "sequenceDiagram\n"
            "  Note over A,B: Shared note\n"
            "  A->>B: Hello"
        )
        assert d.notes[0].position == "over"
        assert d.notes[0].actor_ids == ["A", "B"]


# ============================================================================
# Full diagram
# ============================================================================


class TestFullDiagram:
    def test_parses_a_complete_authentication_flow(self):
        d = parse(
            "sequenceDiagram\n"
            "  participant C as Client\n"
            "  participant S as Server\n"
            "  participant DB as Database\n"
            "  C->>S: POST /login\n"
            "  S->>DB: SELECT user\n"
            "  alt User found\n"
            "    DB-->>S: User record\n"
            "    S-->>C: 200 OK + token\n"
            "  else Not found\n"
            "    DB-->>S: null\n"
            "    S-->>C: 401 Unauthorized\n"
            "  end"
        )

        assert len(d.actors) == 3
        assert len(d.messages) == 6
        assert len(d.blocks) == 1
        assert d.blocks[0].type == "alt"
        assert len(d.blocks[0].dividers) == 1
