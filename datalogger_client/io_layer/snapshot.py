from dataclasses import dataclass
from typing import NamedTuple


class ChannelEntry(NamedTuple):
    value: float
    label: str
    unit: str


@dataclass(frozen=True)
class Snapshot:
    """What one Poll emits: an entry per Channel plus the raw Timestamp (seconds of day)."""

    entries: tuple[ChannelEntry, ...]
    timestamp: int
