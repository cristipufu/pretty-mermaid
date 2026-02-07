"""Layout tests for sequence diagrams -- verify that block headers and dividers
get extra vertical space so they don't overlap with messages.

These tests call parse_sequence_diagram + layout_sequence_diagram directly
to inspect Y coordinates, rather than checking SVG output.
"""
from __future__ import annotations

import pytest

from pretty_mermaid.sequence.parser import parse_sequence_diagram
from pretty_mermaid.sequence.layout import layout_sequence_diagram


def layout(source: str):
    """Helper: parse and layout a sequence diagram from source lines."""
    lines = [
        l.strip()
        for l in source.split("\n")
        if l.strip() and not l.strip().startswith("%%")
    ]
    return layout_sequence_diagram(parse_sequence_diagram(lines))


class TestBlockSpacing:
    def test_messages_outside_blocks_are_spaced_at_base_row_height(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: First\n"
            "  B->>A: Second\n"
            "  A->>B: Third"
        )

        assert len(result.messages) == 3
        gap1 = result.messages[1].y - result.messages[0].y
        gap2 = result.messages[2].y - result.messages[1].y
        assert gap1 == gap2
        assert gap1 == 40

    def test_first_message_in_a_loop_block_gets_extra_header_space(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Before loop\n"
            "  loop Every 5s\n"
            "    A->>B: Inside loop\n"
            "  end"
        )

        assert len(result.messages) == 2
        gap = result.messages[1].y - result.messages[0].y
        assert gap == 40 + 28

    def test_first_message_in_an_alt_block_gets_extra_header_space(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Login\n"
            "  alt Success\n"
            "    B->>A: 200\n"
            "  end"
        )

        assert len(result.messages) == 2
        gap = result.messages[1].y - result.messages[0].y
        assert gap == 40 + 28

    def test_messages_after_else_dividers_get_extra_divider_space(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Login\n"
            "  alt Valid\n"
            "    B->>A: 200 OK\n"
            "  else Invalid\n"
            "    B->>A: 401\n"
            "  end"
        )

        assert len(result.messages) == 3
        gap01 = result.messages[1].y - result.messages[0].y
        assert gap01 == 40 + 28

        gap12 = result.messages[2].y - result.messages[1].y
        assert gap12 == 40 + 24

    def test_multiple_else_dividers_each_get_extra_space(self):
        result = layout(
            "sequenceDiagram\n"
            "  C->>S: Login\n"
            "  alt Valid credentials\n"
            "    S-->>C: 200 OK\n"
            "  else Invalid\n"
            "    S-->>C: 401 Unauthorized\n"
            "  else Account locked\n"
            "    S-->>C: 403 Forbidden\n"
            "  end"
        )

        assert len(result.messages) == 4

        gap01 = result.messages[1].y - result.messages[0].y
        assert gap01 == 40 + 28

        gap12 = result.messages[2].y - result.messages[1].y
        assert gap12 == 40 + 24

        gap23 = result.messages[3].y - result.messages[2].y
        assert gap23 == 40 + 24

    def test_par_block_with_and_dividers_gets_correct_spacing(self):
        result = layout(
            "sequenceDiagram\n"
            "  G->>A: Validate\n"
            "  par Fetch user\n"
            "    G->>U: Get user\n"
            "  and Fetch orders\n"
            "    G->>O: Get orders\n"
            "  end"
        )

        assert len(result.messages) == 3

        gap01 = result.messages[1].y - result.messages[0].y
        assert gap01 == 40 + 28

        gap12 = result.messages[2].y - result.messages[1].y
        assert gap12 == 40 + 24

    def test_opt_block_header_gets_extra_space(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Request\n"
            "  opt Cache available\n"
            "    B-->>A: Cached response\n"
            "  end"
        )

        assert len(result.messages) == 2
        gap = result.messages[1].y - result.messages[0].y
        assert gap == 40 + 28

    def test_critical_block_header_gets_extra_space(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>DB: BEGIN\n"
            "  critical Transaction\n"
            "    A->>DB: UPDATE\n"
            "  end"
        )

        assert len(result.messages) == 2
        gap = result.messages[1].y - result.messages[0].y
        assert gap == 40 + 28

    def test_messages_after_a_block_return_to_normal_spacing(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Before\n"
            "  loop Retry\n"
            "    A->>B: Attempt\n"
            "  end\n"
            "  A->>B: After"
        )

        assert len(result.messages) == 3
        gap12 = result.messages[2].y - result.messages[1].y
        assert gap12 == 40


class TestBlockPositioning:
    def test_block_top_is_above_the_first_message_with_room_for_header(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Before\n"
            "  loop Retry\n"
            "    A->>B: Inside\n"
            "  end"
        )

        block = result.blocks[0]
        first_msg = result.messages[1]
        assert block.y < first_msg.y
        assert first_msg.y - block.y == 40

    def test_divider_y_is_between_the_messages_it_separates(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Login\n"
            "  alt Success\n"
            "    B->>A: 200\n"
            "  else Failure\n"
            "    B->>A: 500\n"
            "  end"
        )

        block = result.blocks[0]
        assert len(block.dividers) == 1
        div_y = block.dividers[0].y
        msg1_y = result.messages[1].y
        msg2_y = result.messages[2].y

        assert div_y > msg1_y
        assert div_y < msg2_y

    def test_multiple_dividers_are_each_between_their_respective_messages(self):
        result = layout(
            "sequenceDiagram\n"
            "  C->>S: Login\n"
            "  alt Valid\n"
            "    S-->>C: 200\n"
            "  else Invalid\n"
            "    S-->>C: 401\n"
            "  else Locked\n"
            "    S-->>C: 403\n"
            "  end"
        )

        block = result.blocks[0]
        assert len(block.dividers) == 2

        assert block.dividers[0].y > result.messages[1].y
        assert block.dividers[0].y < result.messages[2].y

        assert block.dividers[1].y > result.messages[2].y
        assert block.dividers[1].y < result.messages[3].y

    def test_block_height_encompasses_all_its_messages(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Before\n"
            "  alt Yes\n"
            "    B->>A: Response 1\n"
            "  else No\n"
            "    B->>A: Response 2\n"
            "  end"
        )

        block = result.blocks[0]
        first_msg_y = result.messages[1].y
        last_msg_y = result.messages[2].y

        assert block.y < first_msg_y
        assert block.y + block.height > last_msg_y


class TestDiagramDimensions:
    def test_diagram_height_increases_with_block_extra_space(self):
        plain = layout(
            "sequenceDiagram\n"
            "  A->>B: One\n"
            "  B->>A: Two\n"
            "  A->>B: Three"
        )

        with_block = layout(
            "sequenceDiagram\n"
            "  A->>B: One\n"
            "  loop Repeat\n"
            "    B->>A: Two\n"
            "  end\n"
            "  A->>B: Three"
        )

        assert with_block.height > plain.height
        assert with_block.height - plain.height == 28

    def test_diagram_with_multiple_dividers_is_taller_than_one_with_none(self):
        no_dividers = layout(
            "sequenceDiagram\n"
            "  A->>B: M1\n"
            "  B->>A: M2\n"
            "  A->>B: M3\n"
            "  B->>A: M4"
        )

        with_dividers = layout(
            "sequenceDiagram\n"
            "  A->>B: M1\n"
            "  alt Case1\n"
            "    B->>A: M2\n"
            "  else Case2\n"
            "    A->>B: M3\n"
            "  else Case3\n"
            "    B->>A: M4\n"
            "  end"
        )

        assert with_dividers.height - no_dividers.height == 28 + 24 + 24


# ============================================================================
# Clearance tests
# ============================================================================


class TestRenderClearance:
    def test_block_header_tab_bottom_is_above_the_first_message_label(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Before\n"
            "  loop Repeat\n"
            "    A->>B: Inside\n"
            "  end"
        )

        block = result.blocks[0]
        first_msg = result.messages[1]
        tab_bottom = block.y + 18
        msg_label = first_msg.y - 6

        assert tab_bottom < msg_label
        assert msg_label - tab_bottom >= 10

    def test_block_header_tab_does_not_overlap_the_previous_message_arrow(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Previous\n"
            "  alt Valid\n"
            "    B->>A: Response\n"
            "  end"
        )

        prev_msg = result.messages[0]
        block = result.blocks[0]

        assert prev_msg.y < block.y
        assert block.y - prev_msg.y >= 20

    def test_divider_label_does_not_overlap_the_message_label_below_it(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Login\n"
            "  alt Success\n"
            "    B->>A: 200\n"
            "  else Failure\n"
            "    B->>A: 500\n"
            "  end"
        )

        block = result.blocks[0]
        divider = block.dividers[0]
        msg2 = result.messages[2]

        div_label_bottom = divider.y + 14
        msg_label = msg2.y - 6

        assert div_label_bottom < msg_label

    def test_divider_line_does_not_overlap_the_previous_message_arrow(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Login\n"
            "  alt Success\n"
            "    B->>A: 200 OK\n"
            "  else Failure\n"
            "    B->>A: 500 Error\n"
            "  end"
        )

        block = result.blocks[0]
        divider = block.dividers[0]
        prev_msg = result.messages[1]

        assert prev_msg.y < divider.y
        assert divider.y - prev_msg.y >= 10

    def test_alt_block_with_3_else_no_overlap_at_any_boundary(self):
        result = layout(
            "sequenceDiagram\n"
            "  C->>S: Login\n"
            "  alt Valid\n"
            "    S-->>C: 200\n"
            "  else Invalid\n"
            "    S-->>C: 401\n"
            "  else Locked\n"
            "    S-->>C: 403\n"
            "  end"
        )

        block = result.blocks[0]

        tab_bottom = block.y + 18
        first_msg_label = result.messages[1].y - 6
        assert tab_bottom < first_msg_label

        for d in range(len(block.dividers)):
            divider = block.dividers[d]
            msg_after = result.messages[d + 2]
            div_label_bottom = divider.y + 14
            msg_label_top = msg_after.y - 6
            assert div_label_bottom < msg_label_top

        assert block.dividers[0].y > result.messages[1].y
        assert block.dividers[1].y > result.messages[2].y

    def test_long_divider_labels_get_extra_offset(self):
        result = layout(
            "sequenceDiagram\n"
            "  participant C as Client\n"
            "  participant S as Server\n"
            "  C->>S: Login\n"
            "  alt Valid credentials\n"
            "    S-->>C: 200 OK\n"
            "  else Account locked\n"
            "    S-->>C: 403 Forbidden\n"
            "  end"
        )

        block = result.blocks[0]
        assert len(block.dividers) == 1

        divider = block.dividers[0]
        msg_after = result.messages[2]

        div_label_baseline = divider.y + 14
        msg_label_baseline = msg_after.y - 6
        baseline_clearance = msg_label_baseline - div_label_baseline

        assert baseline_clearance >= 14

    def test_short_divider_labels_keep_default_offset(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Login\n"
            "  alt Yes\n"
            "    B->>A: 200\n"
            "  else No\n"
            "    B->>A: 500\n"
            "  end"
        )

        block = result.blocks[0]
        divider = block.dividers[0]
        msg_after = result.messages[2]

        baseline_clearance = (msg_after.y - 6) - (divider.y + 14)
        assert baseline_clearance == 8


# ============================================================================
# Bounding-box tests -- notes positioning
# ============================================================================


class TestNoteBoundingBox:
    def test_note_right_of_last_actor_is_within_diagram_width(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  Note right of B: Right-side note\n"
            "  B-->>A: Hi"
        )

        for note in result.notes:
            assert note.x >= 0
            assert note.x + note.width <= result.width

    def test_note_left_of_first_actor_is_within_diagram_width(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  Note left of A: Left-side note\n"
            "  B-->>A: Hi"
        )

        for note in result.notes:
            assert note.x >= 0
            assert note.x + note.width <= result.width

    def test_both_left_and_right_notes_are_within_diagram_width(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  Note left of A: Left note\n"
            "  Note right of B: Right note\n"
            "  B-->>A: Hi"
        )

        assert len(result.notes) == 2
        for note in result.notes:
            assert note.x >= 0
            assert note.x + note.width <= result.width

    def test_note_over_actor_stays_centered_and_within_bounds(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  Note over A: Centered note\n"
            "  B-->>A: Hi"
        )

        for note in result.notes:
            assert note.x >= 0
            assert note.x + note.width <= result.width

    def test_shift_preserves_relative_positions_of_all_elements(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  Note left of A: This shifts everything\n"
            "  B-->>A: Reply"
        )

        actor_x = {a.id: a.x for a in result.actors}

        for msg in result.messages:
            assert msg.x1 == actor_x[msg.from_]
            assert msg.x2 == actor_x[msg.to]

        for ll in result.lifelines:
            assert ll.x == actor_x[ll.actor_id]

    def test_diagram_without_notes_has_no_unnecessary_shift(self):
        result = layout(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  B-->>A: Hi"
        )

        first_actor_x = result.actors[0].x
        first_actor_left = first_actor_x - result.actors[0].width / 2

        assert first_actor_left == 30

    def test_diagram_width_expands_for_right_side_notes_beyond_actors(self):
        without_note = layout(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  B-->>A: Hi"
        )

        with_note = layout(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  Note right of B: Extra wide note text here\n"
            "  B-->>A: Hi"
        )

        assert with_note.width > without_note.width

    def test_left_side_note_shifts_actors_right_expanding_diagram_width(self):
        without_note = layout(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  B-->>A: Hi"
        )

        with_note = layout(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  Note left of A: Left note\n"
            "  B-->>A: Hi"
        )

        assert with_note.actors[0].x > without_note.actors[0].x

        left_note = with_note.notes[0]
        assert left_note.x >= 0
