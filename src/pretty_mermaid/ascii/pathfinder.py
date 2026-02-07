from __future__ import annotations

# ============================================================================
# ASCII renderer -- A* pathfinding for edge routing
#
# Ported from AlexanderGrooff/mermaid-ascii cmd/arrow.go.
# Uses A* search with a corner-penalizing heuristic to find clean
# paths between nodes on the grid. Prefers straight lines over zigzags.
# ============================================================================

from dataclasses import dataclass
from typing import Optional

from .types import GridCoord, AsciiNode, grid_key, grid_coord_equals

# Canvas type alias (column-major: canvas[x][y])
Canvas = list[list[str]]


# ============================================================================
# Priority queue (min-heap) for A* open set
# ============================================================================


@dataclass
class PQItem:
    coord: GridCoord
    priority: float


class MinHeap:
    """Simple min-heap priority queue.

    For the grid sizes we handle (~100s of cells), this is more than fast enough.
    """

    def __init__(self) -> None:
        self._items: list[PQItem] = []

    def __len__(self) -> int:
        return len(self._items)

    @property
    def length(self) -> int:
        return len(self._items)

    def push(self, item: PQItem) -> None:
        self._items.append(item)
        self._bubble_up(len(self._items) - 1)

    def pop(self) -> Optional[PQItem]:
        if len(self._items) == 0:
            return None
        top = self._items[0]
        last = self._items.pop()
        if len(self._items) > 0:
            self._items[0] = last
            self._sink_down(0)
        return top

    def _bubble_up(self, i: int) -> None:
        while i > 0:
            parent = (i - 1) >> 1
            if self._items[i].priority < self._items[parent].priority:
                self._items[i], self._items[parent] = self._items[parent], self._items[i]
                i = parent
            else:
                break

    def _sink_down(self, i: int) -> None:
        n = len(self._items)
        while True:
            smallest = i
            left = 2 * i + 1
            right = 2 * i + 2
            if left < n and self._items[left].priority < self._items[smallest].priority:
                smallest = left
            if right < n and self._items[right].priority < self._items[smallest].priority:
                smallest = right
            if smallest != i:
                self._items[i], self._items[smallest] = self._items[smallest], self._items[i]
                i = smallest
            else:
                break


# ============================================================================
# A* heuristic
# ============================================================================


def heuristic(a: GridCoord, b: GridCoord) -> int:
    """Manhattan distance with a +1 penalty when both dx and dy are non-zero.

    This encourages the pathfinder to prefer straight lines and minimize corners.
    """
    abs_x = abs(a.x - b.x)
    abs_y = abs(a.y - b.y)
    if abs_x == 0 or abs_y == 0:
        return abs_x + abs_y
    return abs_x + abs_y + 1


# ============================================================================
# A* pathfinding
# ============================================================================

# 4-directional movement (no diagonals in grid pathfinding).
MOVE_DIRS: list[GridCoord] = [
    GridCoord(x=1, y=0),
    GridCoord(x=-1, y=0),
    GridCoord(x=0, y=1),
    GridCoord(x=0, y=-1),
]


def _is_free_in_grid(grid: dict[str, AsciiNode], c: GridCoord) -> bool:
    """Check if a grid cell is unoccupied and has non-negative coordinates."""
    if c.x < 0 or c.y < 0:
        return False
    return grid_key(c) not in grid


def get_path(
    grid: dict[str, AsciiNode],
    from_coord: GridCoord,
    to_coord: GridCoord,
) -> Optional[list[GridCoord]]:
    """Find a path from *from_coord* to *to_coord* on the grid using A*.

    Returns the path as a list of GridCoords, or ``None`` if no path exists.
    """
    pq = MinHeap()
    pq.push(PQItem(coord=from_coord, priority=0))

    cost_so_far: dict[str, int] = {}
    cost_so_far[grid_key(from_coord)] = 0

    came_from: dict[str, Optional[GridCoord]] = {}
    came_from[grid_key(from_coord)] = None

    while pq.length > 0:
        current = pq.pop()
        assert current is not None
        current_coord = current.coord

        if grid_coord_equals(current_coord, to_coord):
            # Reconstruct path by walking backwards through came_from
            path: list[GridCoord] = []
            c: Optional[GridCoord] = current_coord
            while c is not None:
                path.insert(0, c)
                c = came_from.get(grid_key(c))
            return path

        current_cost = cost_so_far[grid_key(current_coord)]

        for move_dir in MOVE_DIRS:
            next_coord = GridCoord(
                x=current_coord.x + move_dir.x,
                y=current_coord.y + move_dir.y,
            )

            # Allow moving to the destination even if it's occupied (it's a node boundary)
            if not _is_free_in_grid(grid, next_coord) and not grid_coord_equals(next_coord, to_coord):
                continue

            new_cost = current_cost + 1
            next_key = grid_key(next_coord)
            existing_cost = cost_so_far.get(next_key)

            if existing_cost is None or new_cost < existing_cost:
                cost_so_far[next_key] = new_cost
                priority = new_cost + heuristic(next_coord, to_coord)
                pq.push(PQItem(coord=next_coord, priority=priority))
                came_from[next_key] = current_coord

    return None  # No path found


# ============================================================================
# Path simplification
# ============================================================================


def merge_path(path: list[GridCoord]) -> list[GridCoord]:
    """Simplify a path by removing intermediate waypoints on straight segments.

    E.g., ``[(0,0), (1,0), (2,0), (2,1)]`` becomes ``[(0,0), (2,0), (2,1)]``.
    This reduces the number of line-drawing operations.
    """
    if len(path) <= 2:
        return path

    to_remove: set[int] = set()
    step0 = path[0]
    step1 = path[1]

    for idx in range(2, len(path)):
        step2 = path[idx]
        prev_dx = step1.x - step0.x
        prev_dy = step1.y - step0.y
        dx = step2.x - step1.x
        dy = step2.y - step1.y

        # Same direction -- the middle point is redundant
        if prev_dx == dx and prev_dy == dy:
            to_remove.add(idx - 1)  # Remove the middle point (step1's position)

        step0 = step1
        step1 = step2

    return [p for i, p in enumerate(path) if i not in to_remove]
