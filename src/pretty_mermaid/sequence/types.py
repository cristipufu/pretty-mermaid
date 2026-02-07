from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ============================================================================
# Sequence diagram types
#
# Models the parsed and positioned representations of a Mermaid sequence diagram.
# Sequence diagrams show actor interactions over time (vertical timeline).
# ============================================================================

# ============================================================================
# Parsed sequence diagram -- logical structure from mermaid text
# ============================================================================

ActorType = Literal["participant", "actor"]
LineStyle = Literal["solid", "dashed"]
ArrowHead = Literal["filled", "open"]
BlockType = Literal["loop", "alt", "opt", "par", "critical", "break", "rect"]
NotePosition = Literal["left", "right", "over"]


@dataclass(slots=True)
class Actor:
    id: str
    label: str
    # 'participant' renders as a box, 'actor' renders as a stick figure
    type: ActorType


@dataclass(slots=True)
class Message:
    from_: str
    to: str
    label: str
    # Arrow style: solid line or dashed line
    line_style: LineStyle
    # Arrow head: filled (closed) or open
    arrow_head: ArrowHead
    # Activate the target lifeline (+)
    activate: bool | None = None
    # Deactivate the source lifeline (-)
    deactivate: bool | None = None


@dataclass(slots=True)
class BlockDivider:
    index: int
    label: str


@dataclass(slots=True)
class Block:
    # Block type keyword
    type: BlockType
    # Label for the block header
    label: str
    # Index of the first message inside this block
    start_index: int
    # Index of the last message inside this block (inclusive)
    end_index: int
    # For alt/par blocks: indices where "else"/"and" dividers appear (message indices)
    dividers: list[BlockDivider] = field(default_factory=list)


@dataclass(slots=True)
class Note:
    # Which actor(s) the note is attached to
    actor_ids: list[str]
    # Note text content
    text: str
    # Position relative to the actor(s)
    position: NotePosition
    # Message index after which this note appears
    after_index: int


@dataclass(slots=True)
class SequenceDiagram:
    """Parsed sequence diagram -- logical structure from mermaid text."""
    # Ordered list of actors/participants
    actors: list[Actor] = field(default_factory=list)
    # Messages between actors in chronological order
    messages: list[Message] = field(default_factory=list)
    # Structural blocks (loop, alt, opt, par, critical)
    blocks: list[Block] = field(default_factory=list)
    # Notes attached to actors
    notes: list[Note] = field(default_factory=list)


# ============================================================================
# Positioned sequence diagram -- ready for SVG rendering
# ============================================================================


@dataclass(slots=True)
class PositionedActor:
    id: str
    label: str
    type: ActorType
    # Center x of the actor box
    x: float
    # Top y of the actor box
    y: float
    width: float
    height: float


@dataclass(slots=True)
class Lifeline:
    """Vertical dashed line from actor to bottom of diagram."""
    actor_id: str
    x: float
    top_y: float
    bottom_y: float


@dataclass(slots=True)
class PositionedMessage:
    from_: str
    to: str
    label: str
    line_style: LineStyle
    arrow_head: ArrowHead
    # Start point (from actor's lifeline)
    x1: float
    # End point (to actor's lifeline)
    x2: float
    # Vertical position
    y: float
    # Whether this is a self-message (same actor)
    is_self: bool


@dataclass(slots=True)
class Activation:
    """Narrow rectangle on a lifeline showing active processing."""
    actor_id: str
    x: float
    top_y: float
    bottom_y: float
    width: float


@dataclass(slots=True)
class PositionedBlockDivider:
    y: float
    label: str


@dataclass(slots=True)
class PositionedBlock:
    type: BlockType
    label: str
    x: float
    y: float
    width: float
    height: float
    # Divider lines within the block (for alt/par)
    dividers: list[PositionedBlockDivider] = field(default_factory=list)


@dataclass(slots=True)
class PositionedNote:
    text: str
    x: float
    y: float
    width: float
    height: float


@dataclass(slots=True)
class PositionedSequenceDiagram:
    width: float
    height: float
    actors: list[PositionedActor] = field(default_factory=list)
    lifelines: list[Lifeline] = field(default_factory=list)
    messages: list[PositionedMessage] = field(default_factory=list)
    activations: list[Activation] = field(default_factory=list)
    blocks: list[PositionedBlock] = field(default_factory=list)
    notes: list[PositionedNote] = field(default_factory=list)
