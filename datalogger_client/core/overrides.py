"""Manual override: a value the user types for a Channel that replaces the Simulator's value.

It is held (re-asserted on every Poll) until the user clears it. The Client overlays it on
each Frame it emits and writes it to the Simulator's register.
"""
import math
import re
from decimal import Decimal

REGISTER_MAX = 0xFFFF  # registers are unsigned 16-bit


class InvalidOverride(ValueError):
    """The text is not a valid override for the Channel; the message is fit to show the user."""


def parse_override(channel, text):
    """The value the user typed for a Channel, or InvalidOverride.

    The Channel's scale fixes the rules: the register holds `value * scale` in 16 bits, so the
    largest value is 65535 / scale, with as many decimal places as the scale has zeros
    (x10: 0 to 6553.5 with one decimal place).
    """
    decimals = max(0, round(math.log10(channel.scale)))
    maximum = Decimal(REGISTER_MAX) / Decimal(str(channel.scale))
    pattern = r"\d+(\.\d{1,%d})?" % decimals if decimals else r"\d+"
    text = text.strip()
    if not re.fullmatch(pattern, text) or Decimal(text) > maximum:
        places = {0: "inteiro", 1: "1 casa decimal"}.get(decimals, f"{decimals} casas decimais")
        raise InvalidOverride(f"Use 0 a {format(maximum.normalize(), 'f')} ({places})")
    return float(Decimal(text))


class ManualOverrides:
    """The overrides the Client holds. Owned by the worker thread alone; nothing else touches it."""

    def __init__(self):
        self._entries = {}  # Channel name -> (Channel, raw register value)

    def set(self, channel, value):
        raw = channel.encode(value)
        if not 0 <= raw <= REGISTER_MAX:
            raise ValueError(f"{value} does not fit the register of {channel.name}")
        self._entries[channel.name] = (channel, raw)

    def clear(self, channel):
        self._entries.pop(channel.name, None)

    def names(self):
        return frozenset(self._entries)

    def overlay(self, frame):
        """The Frame with each overridden Channel's Reading replaced by (or set to) the override."""
        if not self._entries:
            return frame
        return frame.with_readings({name: channel.decode(raw) for name, (channel, raw) in self._entries.items()})

    def register_writes(self):
        """One (address, raw value) per override: the value times the Channel's scale."""
        return [(channel.address, raw) for channel, raw in self._entries.values()]
