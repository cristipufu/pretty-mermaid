# pretty-mermaid

Render [Mermaid](https://mermaid.js.org/) diagrams to SVG and ASCII/Unicode art. Pure Python, no browser or external tools required.

Supports flowcharts, state diagrams, sequence diagrams, class diagrams, and ER diagrams.

Python port of [beautiful-mermaid](https://github.com/nicholasgasior/beautiful-mermaid).

## Install

```bash
pip install pretty-mermaid
```

## Usage

### SVG output

```python
from pretty_mermaid import render_mermaid

svg = render_mermaid("""
graph TD
  A[Start] --> B{Decision}
  B -->|Yes| C[OK]
  B -->|No| D[Fail]
""")

# svg is a complete SVG string with inline styles
with open("diagram.svg", "w") as f:
    f.write(svg)
```

Options:

```python
from pretty_mermaid import render_mermaid
from pretty_mermaid.types import RenderOptions
from pretty_mermaid.theme import THEMES

# Custom theme
svg = render_mermaid("graph LR\n  A --> B", RenderOptions(
    colors=THEMES["github-dark"],
    font="JetBrains Mono",
    padding=60,
))
```

### ASCII/Unicode output

```python
from pretty_mermaid import render_mermaid_ascii

print(render_mermaid_ascii("""
graph TD
  A[Start] --> B{Decision}
  B -->|Yes| C[OK]
  B -->|No| D[Fail]
"""))
```

```
┌──────────┐
│          │
│  Start   │
│          │
└─────┬────┘
      │
      │
      │
      │
      ▼
┌──────────┐
│          │
│ Decision ├───No────┐
│          │         │
└─────┬────┘         │
      │              │
      │              │
     Yes             │
      │              │
      ▼              ▼
┌──────────┐     ┌──────┐
│          │     │      │
│    OK    │     │ Fail │
│          │     │      │
└──────────┘     └──────┘
```

### Flowchart (LR)

```python
print(render_mermaid_ascii("graph LR\n  A[Input] --> B[Process] --> C[Output]"))
```

```
┌───────┐     ┌─────────┐     ┌────────┐
│       │     │         │     │        │
│ Input ├────►│ Process ├────►│ Output │
│       │     │         │     │        │
└───────┘     └─────────┘     └────────┘
```

### Sequence diagram

```python
print(render_mermaid_ascii("""
sequenceDiagram
  Alice->>Bob: Hello
  Bob-->>Alice: Hi back
"""))
```

```
 ┌───────┐     ┌─────┐
 │ Alice │     │ Bob │
 └───┬───┘     └──┬──┘
     │            │
     │   Hello    │
     │────────────▶
     │            │
     │  Hi back   │
     ◀╌╌╌╌╌╌╌╌╌╌╌╌│
     │            │
 ┌───┴───┐     ┌──┴──┐
 │ Alice │     │ Bob │
 └───────┘     └─────┘
```

### Class diagram

```python
print(render_mermaid_ascii("""
classDiagram
  class Animal {
    +String name
    +makeSound()
  }
  class Dog {
    +fetch()
  }
  Animal <|-- Dog
"""))
```

```
┌───────────────┐
│ Animal        │
├───────────────┤
│ +name: String │
├───────────────┤
│ +makeSound    │
└───────────────┘
        △
     ┌──┘
     │
┌────────┐
│ Dog    │
├────────┤
│        │
├────────┤
│ +fetch │
└────────┘
```

### ER diagram

```python
print(render_mermaid_ascii("""
erDiagram
  CUSTOMER ||--o{ ORDER : places
  ORDER ||--|{ LINE_ITEM : contains
"""))
```

```
┌──────────┐places┌───────┐
│ CUSTOMER │║───o╟│ ORDER │
└──────────┘      └───────┘
                      ║
      ───────────────── contains
      │               │
      ╟               │
┌───────────┐
│ LINE_ITEM │
└───────────┘
```

### ASCII mode (no Unicode)

```python
print(render_mermaid_ascii("graph LR\n  A --> B", {"useAscii": True}))
```

## Themes

15 built-in themes for SVG output:

```python
from pretty_mermaid.theme import THEMES

print(list(THEMES.keys()))
# ['default', 'github-light', 'github-dark', 'dracula', 'nord', ...]
```

Use `from_shiki_theme()` to derive colors from any [Shiki](https://shiki.style/) theme.

## Requirements

- Python 3.11+
- [grandalf](https://github.com/bdcht/grandalf) (pure Python graph layout, installed automatically)

## License

MIT
