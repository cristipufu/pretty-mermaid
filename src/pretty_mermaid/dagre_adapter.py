from __future__ import annotations

import math
from dataclasses import dataclass

from .types import Point

# ============================================================================
# Dagre layout adapter — shared utilities for layout integration
# ============================================================================


def center_to_top_left(cx: float, cy: float, width: float, height: float) -> Point:
    """Convert center-based coordinates to top-left origin."""
    return Point(x=cx - width / 2, y=cy - height / 2)


def clip_to_diamond_boundary(
    point: Point, cx: float, cy: float, hw: float, hh: float
) -> Point:
    """Project a point from rectangular boundary onto the diamond boundary."""
    dx = point.x - cx
    dy = point.y - cy
    if abs(dx) < 0.5 and abs(dy) < 0.5:
        return point
    scale = 1 / (abs(dx) / hw + abs(dy) / hh)
    return Point(x=cx + scale * dx, y=cy + scale * dy)


def clip_to_circle_boundary(
    point: Point, cx: float, cy: float, r: float
) -> Point:
    """Project a point from rectangular boundary onto the circle boundary."""
    dx = point.x - cx
    dy = point.y - cy
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 0.5:
        return point
    scale = r / dist
    return Point(x=cx + scale * dx, y=cy + scale * dy)


def snap_to_orthogonal(points: list[Point], vertical_first: bool = True) -> list[Point]:
    """Post-process edge points into strictly orthogonal (90-degree) segments."""
    if len(points) < 2:
        return points

    result: list[Point] = [points[0]]

    for i in range(1, len(points)):
        prev = result[-1]
        curr = points[i]

        dx = abs(curr.x - prev.x)
        dy = abs(curr.y - prev.y)

        if dx < 1 or dy < 1:
            result.append(curr)
            continue

        if vertical_first:
            result.append(Point(x=prev.x, y=curr.y))
        else:
            result.append(Point(x=curr.x, y=prev.y))
        result.append(curr)

    return _remove_collinear(result)


def _remove_collinear(pts: list[Point]) -> list[Point]:
    """Remove middle points from three-in-a-row collinear sequences."""
    if len(pts) < 3:
        return pts
    out: list[Point] = [pts[0]]
    for i in range(1, len(pts) - 1):
        a = out[-1]
        b = pts[i]
        c = pts[i + 1]
        same_x = abs(a.x - b.x) < 1 and abs(b.x - c.x) < 1
        same_y = abs(a.y - b.y) < 1 and abs(b.y - c.y) < 1
        if same_x or same_y:
            continue
        out.append(b)
    out.append(pts[-1])
    return out


@dataclass(slots=True)
class NodeRect:
    """Node rectangle for endpoint clipping — uses center-based coordinates."""

    cx: float
    cy: float
    hw: float
    hh: float


def clip_endpoints_to_nodes(
    points: list[Point],
    source_node: NodeRect | None,
    target_node: NodeRect | None,
) -> list[Point]:
    """Clip edge endpoints to the correct side of rectangular node boundaries."""
    if len(points) < 2:
        return points
    result = [Point(x=p.x, y=p.y) for p in points]

    # --- Fix target endpoint ---
    if target_node:
        last = len(result) - 1

        if len(points) == 2:
            first_pt = result[0]
            curr = result[last]
            dx = abs(curr.x - first_pt.x)
            dy = abs(curr.y - first_pt.y)

            if dy >= dx:
                approach_from_top = curr.y > first_pt.y
                side_y = (
                    target_node.cy - target_node.hh
                    if approach_from_top
                    else target_node.cy + target_node.hh
                )
                result[last] = Point(x=curr.x, y=side_y)
            else:
                approach_from_left = curr.x > first_pt.x
                side_x = (
                    target_node.cx - target_node.hw
                    if approach_from_left
                    else target_node.cx + target_node.hw
                )
                result[last] = Point(x=side_x, y=curr.y)
        else:
            prev = result[last - 1]
            curr = result[last]
            dx = abs(curr.x - prev.x)
            dy = abs(curr.y - prev.y)

            is_strictly_horizontal = dy < 1 and dx >= 1
            is_strictly_vertical = dx < 1 and dy >= 1
            is_primarily_horizontal = (
                not is_strictly_horizontal
                and not is_strictly_vertical
                and dy < dx
            )
            is_primarily_vertical = (
                not is_strictly_horizontal
                and not is_strictly_vertical
                and dx < dy
            )

            if is_strictly_horizontal:
                approach_from_left = curr.x > prev.x
                side_x = (
                    target_node.cx - target_node.hw
                    if approach_from_left
                    else target_node.cx + target_node.hw
                )
                result[last] = Point(x=side_x, y=target_node.cy)
                result[last - 1] = Point(x=prev.x, y=target_node.cy)
            elif is_strictly_vertical:
                approach_from_top = curr.y > prev.y
                side_y = (
                    target_node.cy - target_node.hh
                    if approach_from_top
                    else target_node.cy + target_node.hh
                )
                result[last] = Point(x=target_node.cx, y=side_y)
                result[last - 1] = Point(x=prev.x, y=target_node.cx)
                # Fix: use original prev values
                result[last - 1] = Point(x=target_node.cx, y=prev.y)
            elif is_primarily_horizontal:
                approach_from_left = curr.x > prev.x
                side_x = (
                    target_node.cx - target_node.hw
                    if approach_from_left
                    else target_node.cx + target_node.hw
                )
                within_vertical = (
                    prev.y >= target_node.cy - target_node.hh
                    and prev.y <= target_node.cy + target_node.hh
                )
                if within_vertical:
                    result[last] = Point(x=side_x, y=prev.y)
                else:
                    result[last] = Point(x=side_x, y=target_node.cy)
                    result[last - 1] = Point(x=prev.x, y=target_node.cy)
            elif is_primarily_vertical:
                approach_from_top = curr.y > prev.y
                side_y = (
                    target_node.cy - target_node.hh
                    if approach_from_top
                    else target_node.cy + target_node.hh
                )
                within_horizontal = (
                    prev.x >= target_node.cx - target_node.hw
                    and prev.x <= target_node.cx + target_node.hw
                )
                if within_horizontal:
                    result[last] = Point(x=prev.x, y=side_y)
                else:
                    result[last] = Point(x=target_node.cx, y=side_y)
                    result[last - 1] = Point(x=target_node.cx, y=prev.y)

    # --- Fix source endpoint ---
    if source_node and len(points) >= 3:
        first_pt = result[0]
        next_pt = result[1]
        dx = abs(next_pt.x - first_pt.x)
        dy = abs(next_pt.y - first_pt.y)

        is_strictly_horizontal = dy < 1 and dx >= 1
        is_strictly_vertical = dx < 1 and dy >= 1
        is_primarily_horizontal = (
            not is_strictly_horizontal and not is_strictly_vertical and dy < dx
        )
        is_primarily_vertical = (
            not is_strictly_horizontal and not is_strictly_vertical and dx < dy
        )

        if is_strictly_horizontal:
            exit_to_right = next_pt.x > first_pt.x
            side_x = (
                source_node.cx + source_node.hw
                if exit_to_right
                else source_node.cx - source_node.hw
            )
            result[0] = Point(x=side_x, y=source_node.cy)
            result[1] = Point(x=result[1].x, y=source_node.cy)
        elif is_strictly_vertical:
            exit_downward = next_pt.y > first_pt.y
            side_y = (
                source_node.cy + source_node.hh
                if exit_downward
                else source_node.cy - source_node.hh
            )
            result[0] = Point(x=source_node.cx, y=side_y)
            result[1] = Point(x=source_node.cx, y=result[1].y)
        elif is_primarily_horizontal:
            exit_to_right = next_pt.x > first_pt.x
            side_x = (
                source_node.cx + source_node.hw
                if exit_to_right
                else source_node.cx - source_node.hw
            )
            within_vertical = (
                next_pt.y >= source_node.cy - source_node.hh
                and next_pt.y <= source_node.cy + source_node.hh
            )
            if within_vertical:
                result[0] = Point(x=side_x, y=next_pt.y)
            else:
                result[0] = Point(x=side_x, y=source_node.cy)
                result[1] = Point(x=result[1].x, y=source_node.cy)
        elif is_primarily_vertical:
            exit_downward = next_pt.y > first_pt.y
            side_y = (
                source_node.cy + source_node.hh
                if exit_downward
                else source_node.cy - source_node.hh
            )
            within_horizontal = (
                next_pt.x >= source_node.cx - source_node.hw
                and next_pt.x <= source_node.cx + source_node.hw
            )
            if within_horizontal:
                result[0] = Point(x=next_pt.x, y=side_y)
            else:
                result[0] = Point(x=source_node.cx, y=side_y)
                result[1] = Point(x=source_node.cx, y=result[1].y)

    return result
