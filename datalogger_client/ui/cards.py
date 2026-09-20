from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget

from ..core.registry import CHANNELS, TIMESTAMP

NO_READING = "—"
TEXT_COLOR = "#333333"
DIMMED_TEXT_COLOR = "#a8a8a8"
CARD_STYLE = "background-color: #f0f0f0; border: {border}; border-radius: 10px;"
NORMAL_BORDER = "1px solid #d0d0d0"
OVERRIDDEN_BORDER = "2px solid #e69500"


class ChannelCard(QWidget):
    def __init__(self, label, unit, size):
        super().__init__()
        self._label = label
        self._unit = unit
        self._missing = True  # no Reading yet
        self._dimmed = False  # the connection is not Connected
        self.setFixedSize(*size)
        self.set_overridden(False)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPixelSize(22)
        self.label.setFont(font)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label, 0, 0)
        self.show_value(None)

    def show_value(self, value):
        """Show a Reading, or "—" (dimmed) if there is none."""
        self._missing = value is None
        shown = NO_READING if self._missing else value
        self.label.setText(f"{self._label}: {shown} {self._unit}")
        self._refresh_color()

    def set_dimmed(self, dimmed):
        """Dim the whole card while the connection is not Connected; the last good value stays visible."""
        self._dimmed = dimmed
        self._refresh_color()

    def set_overridden(self, overridden):
        """Mark the card while its Channel has a Manual override."""
        self.setStyleSheet(CARD_STYLE.format(border=OVERRIDDEN_BORDER if overridden else NORMAL_BORDER))

    def _refresh_color(self):
        dim = self._missing or self._dimmed
        self.label.setStyleSheet(f"color: {DIMMED_TEXT_COLOR if dim else TEXT_COLOR};")


class ChannelCards:
    """One card per Channel, plus one for the Frame's Timestamp, updated from each Frame."""

    def __init__(self, size):
        self.cards = {channel.name: ChannelCard(channel.label, channel.unit, size) for channel in CHANNELS}
        self.timestamp_card = ChannelCard(TIMESTAMP.label, TIMESTAMP.unit, size)

    def show_frame(self, frame):
        for channel in CHANNELS:
            self.cards[channel.name].show_value(frame.reading(channel))
        self.timestamp_card.show_value(frame.timestamp)

    def set_dimmed(self, dimmed):
        for card in (*self.cards.values(), self.timestamp_card):
            card.set_dimmed(dimmed)

    def show_overrides(self, channel_names):
        for channel in CHANNELS:
            self.cards[channel.name].set_overridden(channel.name in channel_names)
