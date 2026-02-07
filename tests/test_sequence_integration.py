"""Integration tests for sequence diagrams -- end-to-end parse -> layout -> render."""
from __future__ import annotations

import re

import pytest

from pretty_mermaid import render_mermaid
from pretty_mermaid.types import RenderOptions


class TestSequenceDiagrams:
    def test_renders_a_basic_sequence_diagram_to_valid_svg(self):
        svg = render_mermaid(
            "sequenceDiagram\n"
            "  Alice->>Bob: Hello\n"
            "  Bob-->>Alice: Hi there"
        )
        assert "<svg" in svg
        assert "</svg>" in svg
        assert "Alice" in svg
        assert "Bob" in svg
        assert "Hello" in svg

    def test_renders_participant_declarations(self):
        svg = render_mermaid(
            "sequenceDiagram\n"
            "  participant A as Alice\n"
            "  participant B as Bob\n"
            "  A->>B: Message"
        )
        assert "Alice" in svg
        assert "Bob" in svg
        assert "Message" in svg

    def test_renders_actor_circle_person_icons(self):
        svg = render_mermaid(
            "sequenceDiagram\n"
            "  actor U as User\n"
            "  participant S as System\n"
            "  U->>S: Click"
        )
        assert '<g transform="translate(' in svg
        assert "scale(" in svg
        assert "User" in svg
        assert "System" in svg

    def test_renders_dashed_return_arrows(self):
        svg = render_mermaid(
            "sequenceDiagram\n"
            "  A->>B: Request\n"
            "  B-->>A: Response"
        )
        assert "stroke-dasharray" in svg
        assert "Request" in svg
        assert "Response" in svg

    def test_renders_loop_blocks(self):
        svg = render_mermaid(
            "sequenceDiagram\n"
            "  A->>B: Start\n"
            "  loop Every 5s\n"
            "    A->>B: Ping\n"
            "  end"
        )
        assert "loop" in svg
        assert "Every 5s" in svg

    def test_renders_alt_else_blocks(self):
        svg = render_mermaid(
            "sequenceDiagram\n"
            "  A->>B: Request\n"
            "  alt Success\n"
            "    B->>A: 200\n"
            "  else Error\n"
            "    B->>A: 500\n"
            "  end"
        )
        assert "alt" in svg
        assert "Success" in svg
        assert "Error" in svg

    def test_renders_notes(self):
        svg = render_mermaid(
            "sequenceDiagram\n"
            "  A->>B: Hello\n"
            "  Note right of B: Think about response\n"
            "  B-->>A: Hi"
        )
        assert "Think about response" in svg

    def test_renders_with_dark_colors(self):
        svg = render_mermaid(
            "sequenceDiagram\n"
            "  A->>B: Hello",
            RenderOptions(bg="#18181B", fg="#FAFAFA"),
        )
        assert "--bg:#18181B" in svg

    def test_renders_lifeline_dashed_lines(self):
        svg = render_mermaid(
            "sequenceDiagram\n"
            "  A->>B: Hello"
        )
        dashed_lines = re.findall(r'stroke-dasharray="6 4"', svg)
        assert len(dashed_lines) >= 2

    def test_renders_a_complex_authentication_flow(self):
        svg = render_mermaid(
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
        assert "<svg" in svg
        assert "Client" in svg
        assert "Server" in svg
        assert "Database" in svg
        assert "POST /login" in svg
