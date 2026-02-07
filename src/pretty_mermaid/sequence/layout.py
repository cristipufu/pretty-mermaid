from __future__ import annotations

from .types import (
    SequenceDiagram,
    PositionedSequenceDiagram,
    PositionedActor,
    Lifeline,
    PositionedMessage,
    Activation,
    PositionedBlock,
    PositionedBlockDivider,
    PositionedNote,
)
from ..types import RenderOptions
from ..styles import estimate_text_width, FONT_SIZES, FONT_WEIGHTS

# ============================================================================
# Sequence diagram layout engine
#
# Custom timeline-based layout (no dagre -- sequence diagrams aren't graphs).
#
# Layout strategy:
#   1. Space actors horizontally based on label widths + min gap
#   2. Stack messages vertically in chronological order
#   3. Track activation boxes via a stack
#   4. Position blocks (loop/alt/opt) as background rectangles
#   5. Position notes next to their target actors
# ============================================================================

# Layout constants specific to sequence diagrams
SEQ = {
    # Padding around the entire diagram
    "padding": 30,
    # Minimum gap between actor centers
    "actor_gap": 140,
    # Actor box height
    "actor_height": 40,
    # Horizontal padding inside actor boxes
    "actor_pad_x": 16,
    # Vertical space between actor boxes and first message
    "header_gap": 20,
    # Vertical space per message row
    "message_row_height": 40,
    # Extra vertical space for self-messages (they loop back)
    "self_message_height": 30,
    # Activation box width (narrow rectangle on lifeline)
    "activation_width": 10,
    # Block padding (loop/alt borders)
    "block_pad_x": 10,
    "block_pad_top": 40,
    "block_pad_bottom": 8,
    # Extra vertical space before the first message in a block (room for the header label)
    "block_header_extra": 28,
    # Extra vertical space before a message at a divider boundary (room for else/and label)
    "divider_extra": 24,
    # Note dimensions
    "note_width": 120,
    "note_padding": 8,
    "note_gap": 10,
}


def layout_sequence_diagram(
    diagram: SequenceDiagram,
    _options: RenderOptions | None = None,
) -> PositionedSequenceDiagram:
    """Lay out a parsed sequence diagram.

    Returns a fully positioned diagram ready for SVG rendering.
    """
    if len(diagram.actors) == 0:
        return PositionedSequenceDiagram(width=0, height=0)

    # 1. Calculate actor widths and assign horizontal positions (center X)
    actor_widths: list[float] = []
    for a in diagram.actors:
        text_w = estimate_text_width(
            a.label, FONT_SIZES["node_label"], FONT_WEIGHTS["node_label"]
        )
        actor_widths.append(max(text_w + SEQ["actor_pad_x"] * 2, 80))

    # Build actor center X positions with minimum gap
    actor_center_x: list[float] = []
    current_x = SEQ["padding"] + actor_widths[0] / 2
    for i in range(len(diagram.actors)):
        if i > 0:
            min_gap = max(
                SEQ["actor_gap"],
                (actor_widths[i - 1] + actor_widths[i]) / 2 + 40,
            )
            current_x += min_gap
        actor_center_x.append(current_x)

    # Build actor ID -> index lookup
    actor_index: dict[str, int] = {}
    for i, a in enumerate(diagram.actors):
        actor_index[a.id] = i

    # 2. Position actors at the top
    actor_y = SEQ["padding"]
    actors: list[PositionedActor] = [
        PositionedActor(
            id=a.id,
            label=a.label,
            type=a.type,
            x=actor_center_x[i],
            y=actor_y,
            width=actor_widths[i],
            height=SEQ["actor_height"],
        )
        for i, a in enumerate(diagram.actors)
    ]

    # 3. Stack messages vertically
    message_y = actor_y + SEQ["actor_height"] + SEQ["header_gap"]
    messages: list[PositionedMessage] = []

    # Pre-scan blocks to determine which message indices need extra vertical
    # space for block headers (e.g. "alt [Valid credentials]") or divider
    # labels (e.g. "[else Invalid]"). Without this, messages inside blocks
    # overlap with the header/divider text that sits above them.
    extra_space_before: dict[int, float] = {}
    for block in diagram.blocks:
        # First message in the block needs room for the block header label
        prev = extra_space_before.get(block.start_index, 0)
        extra_space_before[block.start_index] = max(prev, SEQ["block_header_extra"])

        # Each divider (else/and) needs room for the divider label
        for div in block.dividers:
            prev_div = extra_space_before.get(div.index, 0)
            extra_space_before[div.index] = max(prev_div, SEQ["divider_extra"])

    # Track activation stack per actor: array of start-Y positions
    activation_stacks: dict[str, list[float]] = {}
    activations: list[Activation] = []

    for msg_idx, msg in enumerate(diagram.messages):
        from_idx = actor_index.get(msg.from_, 0)
        to_idx = actor_index.get(msg.to, 0)
        is_self = msg.from_ == msg.to

        # Add extra vertical space if this message sits below a block header or divider
        extra = extra_space_before.get(msg_idx, 0)
        if extra > 0:
            message_y += extra

        x1 = actor_center_x[from_idx]
        x2 = actor_center_x[to_idx]

        messages.append(
            PositionedMessage(
                from_=msg.from_,
                to=msg.to,
                label=msg.label,
                line_style=msg.line_style,
                arrow_head=msg.arrow_head,
                x1=x1,
                x2=x2,
                y=message_y,
                is_self=is_self,
            )
        )

        # Handle activation
        if msg.activate:
            if msg.to not in activation_stacks:
                activation_stacks[msg.to] = []
            activation_stacks[msg.to].append(message_y)

        if msg.deactivate:
            stack = activation_stacks.get(msg.from_)
            if stack and len(stack) > 0:
                start_y = stack.pop()
                idx = actor_index.get(msg.from_, 0)
                activations.append(
                    Activation(
                        actor_id=msg.from_,
                        x=actor_center_x[idx] - SEQ["activation_width"] / 2,
                        top_y=start_y,
                        bottom_y=message_y,
                        width=SEQ["activation_width"],
                    )
                )

        message_y += (
            SEQ["self_message_height"] + SEQ["message_row_height"]
            if is_self
            else SEQ["message_row_height"]
        )

    # Close any unclosed activations
    for actor_id, stack in activation_stacks.items():
        for start_y in stack:
            idx = actor_index.get(actor_id, 0)
            activations.append(
                Activation(
                    actor_id=actor_id,
                    x=actor_center_x[idx] - SEQ["activation_width"] / 2,
                    top_y=start_y,
                    bottom_y=message_y - SEQ["message_row_height"] / 2,
                    width=SEQ["activation_width"],
                )
            )

    # 4. Position blocks (loop/alt/opt)
    blocks: list[PositionedBlock] = []
    for block in diagram.blocks:
        # Block spans from the Y of start_index to end_index messages
        start_msg = messages[block.start_index] if block.start_index < len(messages) else None
        end_msg = messages[block.end_index] if block.end_index < len(messages) else None
        block_top = (start_msg.y if start_msg else message_y) - SEQ["block_pad_top"]
        block_bottom = (end_msg.y if end_msg else message_y) + SEQ["block_pad_bottom"] + 12

        # Block width spans all actors involved in its messages
        involved_actors: set[int] = set()
        for mi in range(block.start_index, block.end_index + 1):
            if mi < len(diagram.messages):
                m = diagram.messages[mi]
                involved_actors.add(actor_index.get(m.from_, 0))
                involved_actors.add(actor_index.get(m.to, 0))
        # Fallback: span all actors if none involved
        if len(involved_actors) == 0:
            for ai in range(len(diagram.actors)):
                involved_actors.add(ai)
        min_idx = min(involved_actors)
        max_idx = max(involved_actors)
        block_left = actor_center_x[min_idx] - actor_widths[min_idx] / 2 - SEQ["block_pad_x"]
        block_right = actor_center_x[max_idx] + actor_widths[max_idx] / 2 + SEQ["block_pad_x"]

        # Position dividers -- offset from message Y so the divider label text
        # (rendered at divider.y + 14 in the renderer) clears the message label
        # (rendered at msg.y - 6).
        #
        # Default offset 28 gives ~8px baseline clearance, which is sufficient
        # when the divider label (left-aligned at block edge) and message label
        # (centered between actors) don't share horizontal space. When they DO
        # overlap horizontally (e.g. long divider labels like "[Account locked]"
        # next to centered message labels like "403 Forbidden"), we increase the
        # offset to 36 so text bounding boxes have ~5px visual clearance.
        positioned_dividers: list[PositionedBlockDivider] = []
        for d in block.dividers:
            d_msg = messages[d.index] if d.index < len(messages) else None
            msg_y = d_msg.y if d_msg else message_y
            offset = 28.0

            # Dynamic overlap detection: increase offset when the divider label
            # and message label occupy the same horizontal region, which would
            # cause vertical text overlap at the default 8px baseline gap.
            if d.label and d_msg and d_msg.label:
                div_label_text = f"[{d.label}]"
                div_label_w = estimate_text_width(
                    div_label_text, FONT_SIZES["edge_label"], FONT_WEIGHTS["edge_label"]
                )
                div_label_left = block_left + 8
                div_label_right = div_label_left + div_label_w

                msg_label_w = estimate_text_width(
                    d_msg.label, FONT_SIZES["edge_label"], FONT_WEIGHTS["edge_label"]
                )
                # Self-messages render labels at x1 + 36 (left-aligned); normal
                # messages center the label between the two actor lifelines.
                if d_msg.is_self:
                    msg_label_left = d_msg.x1 + 36
                else:
                    msg_label_left = (d_msg.x1 + d_msg.x2) / 2 - msg_label_w / 2
                msg_label_right = msg_label_left + msg_label_w

                if div_label_right > msg_label_left and div_label_left < msg_label_right:
                    offset = 36.0

            positioned_dividers.append(
                PositionedBlockDivider(y=msg_y - offset, label=d.label)
            )

        blocks.append(
            PositionedBlock(
                type=block.type,
                label=block.label,
                x=block_left,
                y=block_top,
                width=block_right - block_left,
                height=block_bottom - block_top,
                dividers=positioned_dividers,
            )
        )

    # 5. Position notes
    notes: list[PositionedNote] = []
    for note in diagram.notes:
        note_w = max(
            SEQ["note_width"],
            estimate_text_width(
                note.text, FONT_SIZES["edge_label"], FONT_WEIGHTS["edge_label"]
            )
            + SEQ["note_padding"] * 2,
        )
        note_h = FONT_SIZES["edge_label"] + SEQ["note_padding"] * 2

        # Position based on the message after which it appears
        ref_msg = messages[note.after_index] if 0 <= note.after_index < len(messages) else None
        note_y = (ref_msg.y if ref_msg else actor_y + SEQ["actor_height"]) + 4

        # X based on actor position and note type
        first_actor_idx = actor_index.get(note.actor_ids[0] if note.actor_ids else "", 0)
        if note.position == "left":
            note_x = (
                actor_center_x[first_actor_idx]
                - actor_widths[first_actor_idx] / 2
                - note_w
                - SEQ["note_gap"]
            )
        elif note.position == "right":
            note_x = (
                actor_center_x[first_actor_idx]
                + actor_widths[first_actor_idx] / 2
                + SEQ["note_gap"]
            )
        else:
            # over -- center between first and last actor
            if len(note.actor_ids) > 1:
                last_actor_idx = actor_index.get(
                    note.actor_ids[-1] if note.actor_ids else "", first_actor_idx
                )
                note_x = (
                    (actor_center_x[first_actor_idx] + actor_center_x[last_actor_idx]) / 2
                    - note_w / 2
                )
            else:
                note_x = actor_center_x[first_actor_idx] - note_w / 2

        notes.append(
            PositionedNote(text=note.text, x=note_x, y=note_y, width=note_w, height=note_h)
        )

    # 6. Bounding-box post-processing
    #
    # Notes positioned "left of" the first actor or "right of" the last actor
    # can extend beyond the actor-based viewport. Compute the true bounding box
    # across all positioned elements, then shift everything right if anything
    # extends left of the desired padding margin and expand the width to fit.
    diagram_bottom = message_y + SEQ["padding"]

    # Find global X extents across actors, blocks, and notes
    global_min_x: float = SEQ["padding"]  # actors already start at SEQ.padding
    global_max_x: float = 0
    for a in actors:
        global_min_x = min(global_min_x, a.x - a.width / 2)
        global_max_x = max(global_max_x, a.x + a.width / 2)
    for b in blocks:
        global_min_x = min(global_min_x, b.x)
        global_max_x = max(global_max_x, b.x + b.width)
    for n in notes:
        global_min_x = min(global_min_x, n.x)
        global_max_x = max(global_max_x, n.x + n.width)

    # If elements extend left of the desired padding, shift everything right
    shift_x = SEQ["padding"] - global_min_x if global_min_x < SEQ["padding"] else 0
    if shift_x > 0:
        for a in actors:
            a.x += shift_x
        for m in messages:
            m.x1 += shift_x
            m.x2 += shift_x
        for act in activations:
            act.x += shift_x
        for b in blocks:
            b.x += shift_x
        for n in notes:
            n.x += shift_x
        # Also shift actor center X array (used for lifelines below)
        for i in range(len(actor_center_x)):
            actor_center_x[i] += shift_x

    # 7. Calculate final lifelines (after shift so X positions are correct)
    lifelines: list[Lifeline] = [
        Lifeline(
            actor_id=a.id,
            x=actor_center_x[i],
            top_y=actor_y + SEQ["actor_height"],
            bottom_y=diagram_bottom - SEQ["padding"],
        )
        for i, a in enumerate(diagram.actors)
    ]

    # 8. Calculate diagram dimensions from the bounding box
    diagram_width = global_max_x + shift_x + SEQ["padding"]
    diagram_height = diagram_bottom

    return PositionedSequenceDiagram(
        width=max(diagram_width, 200),
        height=max(diagram_height, 100),
        actors=actors,
        lifelines=lifelines,
        messages=messages,
        activations=activations,
        blocks=blocks,
        notes=notes,
    )
