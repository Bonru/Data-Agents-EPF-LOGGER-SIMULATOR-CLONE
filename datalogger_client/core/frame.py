from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional

from .registry import CHANNELS, TIMESTAMP


@dataclass(frozen=True)
class Frame:
    """One full sample of every Channel at one instant. Immutable.

    `readings` maps a Channel's canonical name to its value; a Channel with no
    Reading is simply absent. `timestamp` is seconds of day, or None if it could
    not be read. Two Frames are equal when their readings and timestamp are; the
    time the Client received the Frame (`received_at`, epoch seconds) is not compared.
    """

    readings: Mapping[str, float]
    timestamp: Optional[int]
    received_at: float = field(compare=False)

    def __post_init__(self):
        present = {name: value for name, value in self.readings.items() if value is not None}
        object.__setattr__(self, "readings", MappingProxyType(present))

    def reading(self, channel):
        return self.readings.get(channel.name)

    def with_readings(self, readings):
        """A copy of this Frame with these Readings (Channel name -> value) replacing or adding to its own."""
        return Frame({**self.readings, **readings}, self.timestamp, self.received_at)

    def without_readings(self, channel_names):
        """A copy of this Frame with the Readings of these Channels (by name) removed."""
        kept = {name: value for name, value in self.readings.items() if name not in channel_names}
        return Frame(kept, self.timestamp, self.received_at)


def decode_frame(registers, received_at):
    """Build a Frame from raw register values (address -> raw); unread registers are absent."""
    readings = {
        channel.name: channel.decode(registers[channel.address])
        for channel in CHANNELS
        if channel.address in registers
    }
    timestamp = TIMESTAMP.decode(registers[TIMESTAMP.address]) if TIMESTAMP.address in registers else None
    return Frame(readings, timestamp, received_at)
