"""Tests for dagre-adapter utilities -- focused on clip_endpoints_to_nodes().

Verifies that edge endpoints are correctly clipped to node boundaries
after orthogonal snapping changes the approach direction.
"""
from __future__ import annotations

import pytest

from pretty_mermaid.dagre_adapter import (
    clip_endpoints_to_nodes,
    snap_to_orthogonal,
    NodeRect,
)
from pretty_mermaid.types import Point


# A node centered at (200, 250) with width=120, height=68 (like a class box)
course_node = NodeRect(cx=200, cy=250, hw=60, hh=34)

# A node centered at (100, 50) with width=120, height=60
teacher_node = NodeRect(cx=100, cy=50, hw=60, hh=30)

# A node centered at (300, 50) with same size
student_node = NodeRect(cx=300, cy=50, hw=60, hh=30)


# ============================================================================
# clip_endpoints_to_nodes -- basic behavior
# ============================================================================


class TestClipEndpointsToNodes:
    def test_returns_2_point_edges_unchanged(self):
        points = [Point(x=100, y=80), Point(x=100, y=216)]
        result = clip_endpoints_to_nodes(points, teacher_node, course_node)
        assert result == points

    def test_returns_1_point_or_empty_edges_unchanged(self):
        assert clip_endpoints_to_nodes([], None, None) == []
        assert clip_endpoints_to_nodes([Point(x=0, y=0)], None, None) == [Point(x=0, y=0)]

    def test_does_not_mutate_the_input_array(self):
        points = [
            Point(x=100, y=80),
            Point(x=100, y=216),
            Point(x=200, y=216),
        ]
        original = [Point(x=p.x, y=p.y) for p in points]
        clip_endpoints_to_nodes(points, teacher_node, course_node)
        assert points == original

    # ========================================================================
    # Target endpoint -- horizontal last segment
    # ========================================================================

    class TestTargetHorizontalLastSegment:
        def test_clips_to_left_side_at_vertical_center_when_approaching_from_left(self):
            points = [
                Point(x=100, y=80),
                Point(x=100, y=216),
                Point(x=200, y=216),
            ]
            result = clip_endpoints_to_nodes(points, None, course_node)

            assert result[2].x == 140
            assert result[2].y == 250
            assert result[1].y == 250
            assert result[1].x == 100

        def test_clips_to_right_side_at_vertical_center_when_approaching_from_right(self):
            points = [
                Point(x=300, y=80),
                Point(x=300, y=216),
                Point(x=200, y=216),
            ]
            result = clip_endpoints_to_nodes(points, None, course_node)

            assert result[2].x == 260
            assert result[2].y == 250
            assert result[1].y == 250

    # ========================================================================
    # Target endpoint -- vertical last segment
    # ========================================================================

    class TestTargetVerticalLastSegment:
        def test_clips_to_top_at_horizontal_center_when_approaching_from_above(self):
            points = [
                Point(x=200, y=80),
                Point(x=200, y=150),
                Point(x=200, y=250),
            ]
            result = clip_endpoints_to_nodes(points, None, course_node)

            assert result[2].x == 200
            assert result[2].y == 216
            assert result[1].x == 200

        def test_clips_to_bottom_at_horizontal_center_when_approaching_from_below(self):
            points = [
                Point(x=200, y=400),
                Point(x=200, y=350),
                Point(x=200, y=250),
            ]
            result = clip_endpoints_to_nodes(points, None, course_node)

            assert result[2].x == 200
            assert result[2].y == 284

    # ========================================================================
    # Source endpoint -- horizontal first segment
    # ========================================================================

    class TestSourceHorizontalFirstSegment:
        def test_clips_to_right_side_at_vertical_center_when_exiting_rightward(self):
            points = [
                Point(x=100, y=80),
                Point(x=200, y=80),
                Point(x=200, y=216),
            ]
            result = clip_endpoints_to_nodes(points, teacher_node, None)

            assert result[0].x == 160
            assert result[0].y == 50
            assert result[1].y == 50

        def test_clips_to_left_side_at_vertical_center_when_exiting_leftward(self):
            points = [
                Point(x=100, y=80),
                Point(x=50, y=80),
                Point(x=50, y=216),
            ]
            result = clip_endpoints_to_nodes(points, teacher_node, None)

            assert result[0].x == 40
            assert result[0].y == 50

    # ========================================================================
    # Source endpoint -- vertical first segment
    # ========================================================================

    class TestSourceVerticalFirstSegment:
        def test_clips_to_bottom_at_horizontal_center_when_exiting_downward(self):
            points = [
                Point(x=115, y=80),
                Point(x=115, y=150),
                Point(x=200, y=150),
            ]
            result = clip_endpoints_to_nodes(points, teacher_node, None)

            assert result[0].x == 100
            assert result[0].y == 80
            assert result[1].x == 100

        def test_clips_to_top_at_horizontal_center_when_exiting_upward(self):
            points = [
                Point(x=100, y=50),
                Point(x=100, y=10),
                Point(x=200, y=10),
            ]
            result = clip_endpoints_to_nodes(points, teacher_node, None)

            assert result[0].x == 100
            assert result[0].y == 20

    # ========================================================================
    # Both endpoints adjusted
    # ========================================================================

    class TestBothEndpointsAdjusted:
        def test_fixes_both_source_and_target_in_a_multi_segment_path(self):
            points = [
                Point(x=115, y=80),
                Point(x=115, y=150),
                Point(x=150, y=150),
                Point(x=150, y=216),
                Point(x=200, y=216),
            ]
            result = clip_endpoints_to_nodes(points, teacher_node, course_node)

            # Source: vertical exit downward -> bottom at horizontal center
            assert result[0].x == 100
            assert result[0].y == 80
            assert result[1].x == 100

            # Target: horizontal approach from left -> left side at vertical center
            assert result[4].x == 140
            assert result[4].y == 250
            assert result[3].y == 250

    # ========================================================================
    # null node skipping
    # ========================================================================

    class TestNullNodeHandling:
        def test_skips_source_clipping_when_source_node_is_none(self):
            points = [
                Point(x=115, y=80),
                Point(x=115, y=216),
                Point(x=200, y=216),
            ]
            result = clip_endpoints_to_nodes(points, None, course_node)

            assert result[0] == Point(x=115, y=80)
            assert result[2].x == 140

        def test_skips_target_clipping_when_target_node_is_none(self):
            points = [
                Point(x=115, y=80),
                Point(x=115, y=216),
                Point(x=200, y=216),
            ]
            result = clip_endpoints_to_nodes(points, teacher_node, None)

            assert result[2] == Point(x=200, y=216)
            assert result[0].x == 100

        def test_returns_copy_unchanged_when_both_nodes_are_none(self):
            points = [
                Point(x=100, y=80),
                Point(x=100, y=150),
                Point(x=200, y=150),
            ]
            result = clip_endpoints_to_nodes(points, None, None)
            assert result == points

    # ========================================================================
    # Orthogonality preservation
    # ========================================================================

    class TestOrthogonalityPreservation:
        def test_maintains_orthogonal_segments_after_clipping(self):
            points = [
                Point(x=115, y=80),
                Point(x=115, y=150),
                Point(x=150, y=150),
                Point(x=150, y=216),
                Point(x=200, y=216),
            ]
            result = clip_endpoints_to_nodes(points, teacher_node, course_node)

            for i in range(len(result) - 1):
                a = result[i]
                b = result[i + 1]
                same_x = abs(a.x - b.x) < 1
                same_y = abs(a.y - b.y) < 1
                assert same_x or same_y


# ============================================================================
# Integration: snap_to_orthogonal + clip_endpoints_to_nodes pipeline
# ============================================================================


class TestSnapAndClipPipeline:
    def test_produces_correct_path_for_tb_layout_with_offset_nodes(self):
        raw_points = [
            Point(x=115, y=80),
            Point(x=150, y=150),
            Point(x=183, y=216),
        ]

        ortho = snap_to_orthogonal(raw_points, True)
        result = clip_endpoints_to_nodes(ortho, teacher_node, course_node)

        assert result[0].x == teacher_node.cx
        assert result[0].y == teacher_node.cy + teacher_node.hh

        last_pt = result[-1]
        assert last_pt.y == course_node.cy
        assert (
            last_pt.x == course_node.cx - course_node.hw
            or last_pt.x == course_node.cx + course_node.hw
        )

    def test_produces_correct_path_for_lr_layout(self):
        left_node = NodeRect(cx=100, cy=100, hw=50, hh=30)
        right_node = NodeRect(cx=300, cy=150, hw=50, hh=30)

        raw_points = [
            Point(x=150, y=115),
            Point(x=225, y=130),
            Point(x=250, y=145),
        ]

        ortho = snap_to_orthogonal(raw_points, False)
        result = clip_endpoints_to_nodes(ortho, left_node, right_node)

        assert result[0].x == left_node.cx + left_node.hw
        assert result[0].y == left_node.cy

        last_pt = result[-1]
        assert (
            last_pt.x == right_node.cx - right_node.hw
            or last_pt.x == right_node.cx + right_node.hw
            or last_pt.y == right_node.cy - right_node.hh
            or last_pt.y == right_node.cy + right_node.hh
        )
