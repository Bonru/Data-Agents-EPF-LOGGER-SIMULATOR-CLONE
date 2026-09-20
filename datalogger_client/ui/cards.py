from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget

from ..io_layer.channels import CHANNELS


class ChannelCard(QWidget):
    def __init__(self, channel, size):
        super().__init__()
        self.setFixedSize(*size)
        self.setStyleSheet("background-color: #f0f0f0; border: 1px solid #d0d0d0; border-radius: 10px;")

        self.label = QLabel(f"{channel.label}: -- {channel.unit}")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #333333;")
        font = QFont()
        font.setPixelSize(22)
        self.label.setFont(font)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label, 0, 0)

    def show_entry(self, entry):
        self.label.setText(f"{entry.label}: {entry.value} {entry.unit}")


class ChannelCards:
    """One card per Channel, updated from each snapshot."""

    def __init__(self, size, channels=CHANNELS):
        self.cards = [ChannelCard(channel, size) for channel in channels]

    def show_snapshot(self, snapshot):
        for card, entry in zip(self.cards, snapshot.entries):
            card.show_entry(entry)
