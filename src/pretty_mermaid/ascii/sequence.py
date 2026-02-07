from __future__ import annotations

import math

from ..sequence.parser import parse_sequence_diagram
from ..sequence.types import SequenceDiagram
from .types import AsciiConfig, Canvas
from .canvas import mk_canvas, canvas_to_string, increase_size

# ============================================================================
# ASCII renderer -- sequence diagrams
#
# Renders sequenceDiagram text to ASCII/Unicode art using a column-based layout.
# Each actor occupies a column with a vertical lifeline; messages are horizontal
# arrows between lifelines.  Blocks (loop/alt/opt/par) wrap around message groups.
#
# Layout is fundamentally different from flowcharts -- no grid or A* pathfinding.
# Instead: actors -> columns, messages -> rows, all positioned linearly.
# ============================================================================


def render_sequence_ascii(lines: list[str], config: AsciiConfig) -> str:
    """Render a Mermaid sequence diagram to ASCII/Unicode text.

    Pipeline: parse -> layout (columns + rows) -> draw onto canvas -> string.
    """
    diagram = parse_sequence_diagram(lines)

    if len(diagram.actors) == 0:
        return ""

    use_ascii = config.use_ascii

    # Box-drawing characters
    H = "-" if use_ascii else "\u2500"   # ─
    V = "|" if use_ascii else "\u2502"   # │
    TL = "+" if use_ascii else "\u250c"  # ┌
    TR = "+" if use_ascii else "\u2510"  # ┐
    BL = "+" if use_ascii else "\u2514"  # └
    BR = "+" if use_ascii else "\u2518"  # ┘
    JT = "+" if use_ascii else "\u252c"  # ┬  top junction on lifeline
    JB = "+" if use_ascii else "\u2534"  # ┴  bottom junction on lifeline
    JL = "+" if use_ascii else "\u251c"  # ├  left junction
    JR = "+" if use_ascii else "\u2524"  # ┤  right junction

    # ---- LAYOUT: compute lifeline X positions ----

    actor_idx: dict[str, int] = {}
    for i, a in enumerate(diagram.actors):
        actor_idx[a.id] = i

    box_pad = 1
    actor_box_widths = [len(a.label) + 2 * box_pad + 2 for a in diagram.actors]
    half_box = [math.ceil(w / 2) for w in actor_box_widths]
    actor_box_h = 3  # top border + label row + bottom border

    # Compute minimum gap between adjacent lifelines based on message labels.
    # For messages spanning multiple actors, distribute required width across gaps.
    adj_max_width: list[int] = [0] * max(len(diagram.actors) - 1, 0)

    for msg in diagram.messages:
        fi = actor_idx[msg.from_]
        ti = actor_idx[msg.to]
        if fi == ti:
            continue  # self-messages don't affect spacing
        lo = min(fi, ti)
        hi = max(fi, ti)
        # Required gap per span = (label + arrow decorations) / number of gaps
        needed = len(msg.label) + 4
        num_gaps = hi - lo
        per_gap = math.ceil(needed / num_gaps)
        for g in range(lo, hi):
            adj_max_width[g] = max(adj_max_width[g], per_gap)

    # Compute lifeline x-positions (greedy left-to-right)
    ll_x: list[int] = [half_box[0]]
    for i in range(1, len(diagram.actors)):
        gap = max(
            half_box[i - 1] + half_box[i] + 2,
            adj_max_width[i - 1] + 2,
            10,
        )
        ll_x.append(ll_x[i - 1] + gap)

    # ---- LAYOUT: compute vertical positions for messages ----

    msg_arrow_y: list[int] = [0] * len(diagram.messages)
    msg_label_y: list[int] = [0] * len(diagram.messages)
    block_start_y: dict[int, int] = {}
    block_end_y: dict[int, int] = {}
    div_y_map: dict[str, int] = {}  # "blockIdx:divIdx" -> y
    note_positions: list[dict] = []  # {x, y, width, height, lines}

    cur_y = actor_box_h  # start right below header boxes

    for m in range(len(diagram.messages)):
        # Block openings at this message
        for b in range(len(diagram.blocks)):
            if diagram.blocks[b].start_index == m:
                cur_y += 2  # 1 blank + 1 header row
                block_start_y[b] = cur_y - 1

        # Dividers at this message index
        for b in range(len(diagram.blocks)):
            for d in range(len(diagram.blocks[b].dividers)):
                if diagram.blocks[b].dividers[d].index == m:
                    cur_y += 1
                    div_y_map[f"{b}:{d}"] = cur_y
                    cur_y += 1

        cur_y += 1  # blank row before message

        msg = diagram.messages[m]
        is_self = msg.from_ == msg.to

        if is_self:
            # Self-message occupies 3 rows: top-arm, label-col, bottom-arm
            msg_label_y[m] = cur_y + 1
            msg_arrow_y[m] = cur_y
            cur_y += 3
        else:
            # Normal message: label row then arrow row
            msg_label_y[m] = cur_y
            msg_arrow_y[m] = cur_y + 1
            cur_y += 2

        # Notes after this message
        for n in range(len(diagram.notes)):
            if diagram.notes[n].after_index == m:
                cur_y += 1
                note = diagram.notes[n]
                n_lines = note.text.split("\\n")
                n_width = max(len(l) for l in n_lines) + 4
                n_height = len(n_lines) + 2

                # Determine x position based on note.position
                a_idx = actor_idx.get(note.actor_ids[0], 0)
                if note.position == "left":
                    nx = ll_x[a_idx] - n_width - 1
                elif note.position == "right":
                    nx = ll_x[a_idx] + 2
                else:
                    # 'over' -- center over actor(s)
                    if len(note.actor_ids) >= 2:
                        a_idx2 = actor_idx.get(note.actor_ids[1], a_idx)
                        nx = (ll_x[a_idx] + ll_x[a_idx2]) // 2 - n_width // 2
                    else:
                        nx = ll_x[a_idx] - n_width // 2
                nx = max(0, nx)

                note_positions.append({
                    "x": nx,
                    "y": cur_y,
                    "width": n_width,
                    "height": n_height,
                    "lines": n_lines,
                })
                cur_y += n_height

        # Block closings after this message
        for b in range(len(diagram.blocks)):
            if diagram.blocks[b].end_index == m:
                cur_y += 1
                block_end_y[b] = cur_y
                cur_y += 1

    cur_y += 1  # gap before footer
    footer_y = cur_y
    total_h = footer_y + actor_box_h

    # Total canvas width
    last_ll = ll_x[-1] if ll_x else 0
    last_half = half_box[-1] if half_box else 0
    total_w = last_ll + last_half + 2

    # Ensure canvas is wide enough for self-message labels and notes
    for m in range(len(diagram.messages)):
        msg = diagram.messages[m]
        if msg.from_ == msg.to:
            fi = actor_idx[msg.from_]
            self_right = ll_x[fi] + 6 + 2 + len(msg.label)
            total_w = max(total_w, self_right + 1)
    for np in note_positions:
        total_w = max(total_w, np["x"] + np["width"] + 1)

    canvas = mk_canvas(total_w, total_h - 1)

    # ---- DRAW: helper to place a bordered actor box ----

    def draw_actor_box(cx: int, top_y: int, label: str) -> None:
        w = len(label) + 2 * box_pad + 2
        left = cx - w // 2
        # Top border
        canvas[left][top_y] = TL
        for x in range(1, w - 1):
            canvas[left + x][top_y] = H
        canvas[left + w - 1][top_y] = TR
        # Sides + label
        canvas[left][top_y + 1] = V
        canvas[left + w - 1][top_y + 1] = V
        ls = left + 1 + box_pad
        for i, ch in enumerate(label):
            canvas[ls + i][top_y + 1] = ch
        # Bottom border
        canvas[left][top_y + 2] = BL
        for x in range(1, w - 1):
            canvas[left + x][top_y + 2] = H
        canvas[left + w - 1][top_y + 2] = BR

    # ---- DRAW: lifelines ----

    for i in range(len(diagram.actors)):
        x = ll_x[i]
        for y in range(actor_box_h, footer_y + 1):
            canvas[x][y] = V

    # ---- DRAW: actor header + footer boxes (drawn over lifelines) ----

    for i in range(len(diagram.actors)):
        actor = diagram.actors[i]
        draw_actor_box(ll_x[i], 0, actor.label)
        draw_actor_box(ll_x[i], footer_y, actor.label)

        # Lifeline junctions on box borders (Unicode only)
        if not use_ascii:
            canvas[ll_x[i]][actor_box_h - 1] = JT  # bottom of header -> ┬
            canvas[ll_x[i]][footer_y] = JB          # top of footer -> ┴

    # ---- DRAW: messages ----

    for m in range(len(diagram.messages)):
        msg = diagram.messages[m]
        fi = actor_idx[msg.from_]
        ti = actor_idx[msg.to]
        from_x = ll_x[fi]
        to_x = ll_x[ti]
        is_self = fi == ti
        is_dashed = msg.line_style == "dashed"
        is_filled = msg.arrow_head == "filled"

        # Arrow line character (solid vs dashed)
        line_char = ("." if use_ascii else "\u254c") if is_dashed else H  # ╌

        if is_self:
            # Self-message: 3-row loop to the right of the lifeline
            #   ├──┐           (row 0 = msg_arrow_y)
            #   │  │ Label     (row 1)
            #   │◄─┘           (row 2)
            y0 = msg_arrow_y[m]
            loop_w = max(4, 4)

            # Row 0: start junction + horizontal + top-right corner
            canvas[from_x][y0] = JL
            for x in range(from_x + 1, from_x + loop_w):
                canvas[x][y0] = line_char
            canvas[from_x + loop_w][y0] = "+" if use_ascii else "\u2510"  # ┐

            # Row 1: vertical on right side + label
            canvas[from_x + loop_w][y0 + 1] = V
            label_x = from_x + loop_w + 2
            for i, ch in enumerate(msg.label):
                if label_x + i < total_w:
                    canvas[label_x + i][y0 + 1] = ch

            # Row 2: arrow-back + horizontal + bottom-right corner
            arrow_char = ("<" if use_ascii else "\u25c0") if is_filled else ("<" if use_ascii else "\u25c1")
            canvas[from_x][y0 + 2] = arrow_char
            for x in range(from_x + 1, from_x + loop_w):
                canvas[x][y0 + 2] = line_char
            canvas[from_x + loop_w][y0 + 2] = "+" if use_ascii else "\u2518"  # ┘
        else:
            # Normal message: label on row above, arrow on row below
            label_y = msg_label_y[m]
            arrow_y = msg_arrow_y[m]
            left_to_right = from_x < to_x

            # Draw label centered between the two lifelines
            mid_x = (from_x + to_x) // 2
            label_start = mid_x - len(msg.label) // 2
            for i, ch in enumerate(msg.label):
                lx = label_start + i
                if 0 <= lx < total_w:
                    canvas[lx][label_y] = ch

            # Draw arrow line
            if left_to_right:
                for x in range(from_x + 1, to_x):
                    canvas[x][arrow_y] = line_char
                # Arrowhead at destination
                ah = (">" if use_ascii else "\u25b6") if is_filled else (">" if use_ascii else "\u25b7")
                canvas[to_x][arrow_y] = ah
            else:
                for x in range(to_x + 1, from_x):
                    canvas[x][arrow_y] = line_char
                ah = ("<" if use_ascii else "\u25c0") if is_filled else ("<" if use_ascii else "\u25c1")
                canvas[to_x][arrow_y] = ah

    # ---- DRAW: blocks (loop, alt, opt, par, etc.) ----

    def is_dashed_h() -> str:
        return "-" if use_ascii else "\u254c"  # ╌

    for b in range(len(diagram.blocks)):
        block = diagram.blocks[b]
        top_y = block_start_y.get(b)
        bot_y = block_end_y.get(b)
        if top_y is None or bot_y is None:
            continue

        # Find the leftmost/rightmost lifelines involved in this block's messages
        min_lx = total_w
        max_lx = 0
        for m_idx in range(block.start_index, block.end_index + 1):
            if m_idx >= len(diagram.messages):
                break
            msg = diagram.messages[m_idx]
            f = actor_idx.get(msg.from_, 0)
            t = actor_idx.get(msg.to, 0)
            min_lx = min(min_lx, ll_x[min(f, t)])
            max_lx = max(max_lx, ll_x[max(f, t)])

        b_left = max(0, min_lx - 4)
        b_right = min(total_w - 1, max_lx + 4)

        # Top border with block type label
        canvas[b_left][top_y] = TL
        for x in range(b_left + 1, b_right):
            canvas[x][top_y] = H
        canvas[b_right][top_y] = TR
        # Write block header label over the top border
        hdr_label = f"{block.type} [{block.label}]" if block.label else block.type
        for i, ch in enumerate(hdr_label):
            if b_left + 1 + i < b_right:
                canvas[b_left + 1 + i][top_y] = ch

        # Bottom border
        canvas[b_left][bot_y] = BL
        for x in range(b_left + 1, b_right):
            canvas[x][bot_y] = H
        canvas[b_right][bot_y] = BR

        # Side borders
        for y in range(top_y + 1, bot_y):
            canvas[b_left][y] = V
            canvas[b_right][y] = V

        # Dividers
        for d in range(len(block.dividers)):
            d_y = div_y_map.get(f"{b}:{d}")
            if d_y is None:
                continue
            dash_char = is_dashed_h()
            canvas[b_left][d_y] = JL
            for x in range(b_left + 1, b_right):
                canvas[x][d_y] = dash_char
            canvas[b_right][d_y] = JR
            # Divider label
            d_label = block.dividers[d].label
            if d_label:
                d_str = f"[{d_label}]"
                for i, ch in enumerate(d_str):
                    if b_left + 1 + i < b_right:
                        canvas[b_left + 1 + i][d_y] = ch

    # ---- DRAW: notes ----

    for np in note_positions:
        # Ensure canvas is big enough
        increase_size(canvas, np["x"] + np["width"], np["y"] + np["height"])
        # Top border
        canvas[np["x"]][np["y"]] = TL
        for x in range(1, np["width"] - 1):
            canvas[np["x"] + x][np["y"]] = H
        canvas[np["x"] + np["width"] - 1][np["y"]] = TR
        # Content rows
        for l_idx, line_text in enumerate(np["lines"]):
            ly = np["y"] + 1 + l_idx
            canvas[np["x"]][ly] = V
            canvas[np["x"] + np["width"] - 1][ly] = V
            for i, ch in enumerate(line_text):
                canvas[np["x"] + 2 + i][ly] = ch
        # Bottom border
        by = np["y"] + np["height"] - 1
        canvas[np["x"]][by] = BL
        for x in range(1, np["width"] - 1):
            canvas[np["x"] + x][by] = H
        canvas[np["x"] + np["width"] - 1][by] = BR

    return canvas_to_string(canvas)
