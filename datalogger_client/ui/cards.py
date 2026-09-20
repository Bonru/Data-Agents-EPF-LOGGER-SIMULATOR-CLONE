from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget

from ..core.registry import CHANNELS, TIMESTAMP

NO_READING = "--"


class ChannelCard(QWidget):
    def __init__(self, label, unit, size):
        super().__init__()
        self._label = label
        self._unit = unit
        self.setFixedSize(*size)
        self.setStyleSheet("background-color: #f0f0f0; border: 1px solid #d0d0d0; border-radius: 10px;")

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #333333;")
        font = QFont()
        font.setPixelSize(22)
        self.label.setFont(font)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label, 0, 0)
        self.show_value(None)

    def show_value(self, value):
        shown = NO_READING if value is None else value
        self.label.setText(f"{self._label}: {shown} {self._unit}")


class ChannelCards:
    """One card per Channel, plus one for the Frame's Timestamp, updated from each Frame."""

    def __init__(self, size):
        self.cards = {channel.name: ChannelCard(channel.label, channel.unit, size) for channel in CHANNELS}
        self.timestamp_card = ChannelCard(TIMESTAMP.label, TIMESTAMP.unit, size)

    def show_frame(self, frame):
        for channel in CHANNELS:
            self.cards[channel.name].show_value(frame.reading(channel))
        self.timestamp_card.show_value(frame.timestamp)
