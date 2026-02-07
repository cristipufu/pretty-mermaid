from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

# ============================================================================
# Types
# ============================================================================


@dataclass(slots=True)
class DiagramColors:
    """Diagram color configuration.

    Required: bg + fg give you a clean mono diagram.
    Optional: line, accent, muted, surface, border bring in richer color.
    """

    bg: str
    fg: str
    line: str | None = None
    accent: str | None = None
    muted: str | None = None
    surface: str | None = None
    border: str | None = None


# ============================================================================
# Defaults
# ============================================================================

DEFAULTS = {"bg": "#FFFFFF", "fg": "#27272A"}

# ============================================================================
# color-mix() weights for derived CSS variables
# ============================================================================

MIX = {
    "text": 100,
    "text_sec": 60,
    "text_muted": 40,
    "text_faint": 25,
    "line": 30,
    "arrow": 50,
    "node_fill": 3,
    "node_stroke": 20,
    "group_header": 5,
    "inner_stroke": 12,
    "key_badge": 10,
}

# ============================================================================
# Well-known theme palettes
# ============================================================================

THEMES: dict[str, DiagramColors] = {
    "zinc-dark": DiagramColors(bg="#18181B", fg="#FAFAFA"),
    "tokyo-night": DiagramColors(
        bg="#1a1b26", fg="#a9b1d6",
        line="#3d59a1", accent="#7aa2f7", muted="#565f89",
    ),
    "tokyo-night-storm": DiagramColors(
        bg="#24283b", fg="#a9b1d6",
        line="#3d59a1", accent="#7aa2f7", muted="#565f89",
    ),
    "tokyo-night-light": DiagramColors(
        bg="#d5d6db", fg="#343b58",
        line="#34548a", accent="#34548a", muted="#9699a3",
    ),
    "catppuccin-mocha": DiagramColors(
        bg="#1e1e2e", fg="#cdd6f4",
        line="#585b70", accent="#cba6f7", muted="#6c7086",
    ),
    "catppuccin-latte": DiagramColors(
        bg="#eff1f5", fg="#4c4f69",
        line="#9ca0b0", accent="#8839ef", muted="#9ca0b0",
    ),
    "nord": DiagramColors(
        bg="#2e3440", fg="#d8dee9",
        line="#4c566a", accent="#88c0d0", muted="#616e88",
    ),
    "nord-light": DiagramColors(
        bg="#eceff4", fg="#2e3440",
        line="#aab1c0", accent="#5e81ac", muted="#7b88a1",
    ),
    "dracula": DiagramColors(
        bg="#282a36", fg="#f8f8f2",
        line="#6272a4", accent="#bd93f9", muted="#6272a4",
    ),
    "github-light": DiagramColors(
        bg="#ffffff", fg="#1f2328",
        line="#d1d9e0", accent="#0969da", muted="#59636e",
    ),
    "github-dark": DiagramColors(
        bg="#0d1117", fg="#e6edf3",
        line="#3d444d", accent="#4493f8", muted="#9198a1",
    ),
    "solarized-light": DiagramColors(
        bg="#fdf6e3", fg="#657b83",
        line="#93a1a1", accent="#268bd2", muted="#93a1a1",
    ),
    "solarized-dark": DiagramColors(
        bg="#002b36", fg="#839496",
        line="#586e75", accent="#268bd2", muted="#586e75",
    ),
    "one-dark": DiagramColors(
        bg="#282c34", fg="#abb2bf",
        line="#4b5263", accent="#c678dd", muted="#5c6370",
    ),
}

ThemeName = str

# ============================================================================
# Shiki theme extraction
# ============================================================================


def from_shiki_theme(theme: dict[str, Any]) -> DiagramColors:
    """Extract diagram colors from a Shiki theme object."""
    c: dict[str, str] = theme.get("colors", {})
    dark = theme.get("type") == "dark"
    token_colors: list[dict[str, Any]] = theme.get("tokenColors", [])

    def token_color(scope: str) -> str | None:
        for t in token_colors:
            s = t.get("scope")
            if isinstance(s, list):
                if scope in s:
                    return t.get("settings", {}).get("foreground")
            elif s == scope:
                return t.get("settings", {}).get("foreground")
        return None

    return DiagramColors(
        bg=c.get("editor.background", "#1e1e1e" if dark else "#ffffff"),
        fg=c.get("editor.foreground", "#d4d4d4" if dark else "#333333"),
        line=c.get("editorLineNumber.foreground"),
        accent=c.get("focusBorder") or token_color("keyword"),
        muted=token_color("comment") or c.get("editorLineNumber.foreground"),
        surface=c.get("editor.selectionBackground"),
        border=c.get("editorWidget.border"),
    )


# ============================================================================
# SVG style block
# ============================================================================


def build_style_block(font: str, has_mono_font: bool) -> str:
    """Build the CSS variable derivation rules for the SVG <style> block."""
    font_imports = [
        f"@import url('https://fonts.googleapis.com/css2?family={quote(font)}:wght@400;500;600;700&amp;display=swap');",
    ]
    if has_mono_font:
        font_imports.append(
            "@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&amp;display=swap');"
        )

    derived_vars = f"""
    /* Derived from --bg and --fg (overridable via --line, --accent, etc.) */
    --_text:          var(--fg);
    --_text-sec:      var(--muted, color-mix(in srgb, var(--fg) {MIX["text_sec"]}%, var(--bg)));
    --_text-muted:    var(--muted, color-mix(in srgb, var(--fg) {MIX["text_muted"]}%, var(--bg)));
    --_text-faint:    color-mix(in srgb, var(--fg) {MIX["text_faint"]}%, var(--bg));
    --_line:          var(--line, color-mix(in srgb, var(--fg) {MIX["line"]}%, var(--bg)));
    --_arrow:         var(--accent, color-mix(in srgb, var(--fg) {MIX["arrow"]}%, var(--bg)));
    --_node-fill:     var(--surface, color-mix(in srgb, var(--fg) {MIX["node_fill"]}%, var(--bg)));
    --_node-stroke:   var(--border, color-mix(in srgb, var(--fg) {MIX["node_stroke"]}%, var(--bg)));
    --_group-fill:    var(--bg);
    --_group-hdr:     color-mix(in srgb, var(--fg) {MIX["group_header"]}%, var(--bg));
    --_inner-stroke:  color-mix(in srgb, var(--fg) {MIX["inner_stroke"]}%, var(--bg));
    --_key-badge:     color-mix(in srgb, var(--fg) {MIX["key_badge"]}%, var(--bg));"""

    lines = [
        "<style>",
        f"  {chr(10).join('  ' + imp if i > 0 else imp for i, imp in enumerate(font_imports))}",
        f"  text {{ font-family: '{font}', system-ui, sans-serif; }}",
    ]
    if has_mono_font:
        lines.append(
            "  .mono { font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', ui-monospace, monospace; }"
        )
    lines.extend([
        f"  svg {{{derived_vars}",
        "  }",
        "</style>",
    ])
    return "\n".join(lines)


def svg_open_tag(
    width: float,
    height: float,
    colors: DiagramColors,
    transparent: bool = False,
) -> str:
    """Build the SVG opening tag with CSS variables set as inline styles."""
    vars_parts = [
        f"--bg:{colors.bg}",
        f"--fg:{colors.fg}",
    ]
    if colors.line:
        vars_parts.append(f"--line:{colors.line}")
    if colors.accent:
        vars_parts.append(f"--accent:{colors.accent}")
    if colors.muted:
        vars_parts.append(f"--muted:{colors.muted}")
    if colors.surface:
        vars_parts.append(f"--surface:{colors.surface}")
    if colors.border:
        vars_parts.append(f"--border:{colors.border}")

    vars_str = ";".join(vars_parts)
    bg_style = "" if transparent else ";background:var(--bg)"

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" style="{vars_str}{bg_style}">'
    )
