from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QWidget

from ..core.frame_history import seconds_to_hms
from ..core.registry import CHANNELS, TIMESTAMP
from .layout import CARD_MIN_SIZE, CARD_POINT_SIZE

NO_READING = "—"
TEXT_COLOR = "#333333"
DIMMED_TEXT_COLOR = "#a8a8a8"
CARD_STYLE = "background-color: #f0f0f0; border: {border}; border-radius: 10px;"
NORMAL_BORDER = "1px solid #d0d0d0"
OVERRIDDEN_BORDER = "2px solid #e69500"


class ChannelCard(QWidget):
    def __init__(self, label, unit, formatter=None):
        super().__init__()
        self._label = label
        self._unit = unit
        self._formatter = formatter  # how a value is written; None writes it as it is
        self._missing = True  # no Reading yet
        self._dimmed = False  # the connection is not Connected
        self.setMinimumSize(*CARD_MIN_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)  # grows with its grid column
        self.set_overridden(False)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)  # a long text wraps instead of being clipped in a narrow card
        font = QFont()
        font.setPointSize(CARD_POINT_SIZE)
        self.label.setFont(font)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label, 0, 0)
        self.show_value(None)

    def show_value(self, value):
        """Show a Reading, or "—" (dimmed) if there is none."""
        self._missing = value is None
        shown = NO_READING if self._missing else (self._formatter(value) if self._formatter else value)
        text = f"{self._label}: {shown}"
        self.label.setText(f"{text} {self._unit}" if self._unit else text)
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

    def __init__(self):
        self.cards = {channel.name: ChannelCard(channel.label, channel.unit) for channel in CHANNELS}
        self.timestamp_card = ChannelCard(TIMESTAMP.label, "", formatter=seconds_to_hms)  # a time of day, hh:mm:ss

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
