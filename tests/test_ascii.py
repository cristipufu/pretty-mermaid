"""Golden-file tests for the ASCII/Unicode renderer.

Ported from AlexanderGrooff/mermaid-ascii cmd/graph_test.go.
Each .txt file contains mermaid input above a ``---`` separator
and the expected ASCII/Unicode output below it.

Test data: golden files in testdata/ascii and testdata/unicode directories.
"""
from __future__ import annotations

import os
import re

import pytest

from pretty_mermaid import render_mermaid_ascii

# ============================================================================
# Test case parser -- matches Go's testutil.ReadTestCase format
# ============================================================================


def _parse_test_case(content: str) -> dict:
    """Parse a golden test file into its components.

    Format:
      [paddingX=N]     (optional)
      [paddingY=N]     (optional)
      <mermaid code>
      ---
      <expected output>
    """
    tc = {"mermaid": "", "expected": "", "padding_x": 5, "padding_y": 5}
    lines = content.split("\n")
    padding_regex = re.compile(r"^(?:padding([xy]))\s*=\s*(\d+)\s*$", re.IGNORECASE)

    in_mermaid = True
    mermaid_started = False
    mermaid_lines: list[str] = []
    expected_lines: list[str] = []

    for line in lines:
        if line == "---":
            in_mermaid = False
            continue

        if in_mermaid:
            trimmed = line.strip()

            if not mermaid_started:
                if trimmed == "":
                    continue
                match = padding_regex.match(trimmed)
                if match:
                    value = int(match.group(2))
                    if match.group(1).lower() == "x":
                        tc["padding_x"] = value
                    else:
                        tc["padding_y"] = value
                    continue

            mermaid_started = True
            mermaid_lines.append(line)
        else:
            expected_lines.append(line)

    tc["mermaid"] = "\n".join(mermaid_lines) + "\n"

    expected = "\n".join(expected_lines)
    if expected.endswith("\n"):
        expected = expected[:-1]
    tc["expected"] = expected

    return tc


# ============================================================================
# Whitespace normalization -- matches Go's testutil.NormalizeWhitespace
# ============================================================================


def _normalize_whitespace(s: str) -> str:
    """Normalize whitespace for comparison:
    - Trim trailing spaces from each line
    - Remove leading/trailing blank lines
    """
    normalized = [line.rstrip() for line in s.split("\n")]

    while normalized and normalized[0] == "":
        normalized.pop(0)
    while normalized and normalized[-1] == "":
        normalized.pop()

    return "\n".join(normalized)


def _visualize_whitespace(s: str) -> str:
    """Replace spaces with middle dots for clearer diff output."""
    return s.replace(" ", "\u00b7")


# ============================================================================
# Test runner -- dynamically loads all golden files from testdata directories
# ============================================================================


def _collect_golden_tests(directory: str, use_ascii: bool) -> list:
    """Collect test cases from golden files in a directory."""
    if not os.path.isdir(directory):
        return []
    files = sorted(f for f in os.listdir(directory) if f.endswith(".txt"))
    tests = []
    for filename in files:
        test_name = filename.replace(".txt", "")
        filepath = os.path.join(directory, filename)
        tests.append((test_name, filepath, use_ascii))
    return tests


_testdata_dir = os.path.join(os.path.dirname(__file__), "testdata")
_ascii_tests = _collect_golden_tests(os.path.join(_testdata_dir, "ascii"), True)
_unicode_tests = _collect_golden_tests(os.path.join(_testdata_dir, "unicode"), False)


@pytest.mark.parametrize(
    "test_name,filepath,use_ascii",
    _ascii_tests,
    ids=[t[0] for t in _ascii_tests],
)
def test_ascii_rendering(test_name: str, filepath: str, use_ascii: bool):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    tc = _parse_test_case(content)

    actual = render_mermaid_ascii(tc["mermaid"], {
        "useAscii": use_ascii,
        "paddingX": tc["padding_x"],
        "paddingY": tc["padding_y"],
    })

    normalized_expected = _normalize_whitespace(tc["expected"])
    normalized_actual = _normalize_whitespace(actual)

    if normalized_expected != normalized_actual:
        expected_vis = _visualize_whitespace(normalized_expected)
        actual_vis = _visualize_whitespace(normalized_actual)
        assert actual_vis == expected_vis


@pytest.mark.parametrize(
    "test_name,filepath,use_ascii",
    _unicode_tests,
    ids=[t[0] for t in _unicode_tests],
)
def test_unicode_rendering(test_name: str, filepath: str, use_ascii: bool):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    tc = _parse_test_case(content)

    actual = render_mermaid_ascii(tc["mermaid"], {
        "useAscii": use_ascii,
        "paddingX": tc["padding_x"],
        "paddingY": tc["padding_y"],
    })

    normalized_expected = _normalize_whitespace(tc["expected"])
    normalized_actual = _normalize_whitespace(actual)

    if normalized_expected != normalized_actual:
        expected_vis = _visualize_whitespace(normalized_expected)
        actual_vis = _visualize_whitespace(normalized_actual)
        assert actual_vis == expected_vis


# ============================================================================
# Config behavior tests -- ported from Go's TestGraphUseAsciiConfig
# ============================================================================


class TestConfigBehavior:
    _mermaid_input = "graph LR\nA --> B"

    def test_ascii_and_unicode_outputs_should_differ(self):
        ascii_output = render_mermaid_ascii(self._mermaid_input, {"useAscii": True})
        unicode_output = render_mermaid_ascii(self._mermaid_input, {"useAscii": False})
        assert ascii_output != unicode_output

    def test_ascii_output_should_not_contain_unicode_box_drawing_characters(self):
        output = render_mermaid_ascii(self._mermaid_input, {"useAscii": True})
        assert "\u250c" not in output  # top-left corner
        assert "\u2500" not in output  # horizontal line
        assert "\u2502" not in output  # vertical line

    def test_unicode_output_should_contain_unicode_box_drawing_characters(self):
        output = render_mermaid_ascii(self._mermaid_input, {"useAscii": False})
        has_unicode = (
            "\u250c" in output  # top-left corner
            or "\u2500" in output  # horizontal line
            or "\u2502" in output  # vertical line
        )
        assert has_unicode
