from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..core.connection_state import ConnectionState

# text, colour of the text
CONNECTION_DISPLAY = {
    ConnectionState.CONNECTED: ("Conectado", "#2e7d32"),
    ConnectionState.STALE: ("Sem atualização", "#b26a00"),
    ConnectionState.DISCONNECTED: ("Desconectado", "#c62828"),
}


class StatusArea(QWidget):
    """The header's status area. Sized by its layout; the Firebase indicator (#10) goes here too."""

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.connection_label = QLabel()
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.connection_label)
        self.show_connection_state(ConnectionState.DISCONNECTED)

    def show_connection_state(self, state):
        text, color = CONNECTION_DISPLAY[state]
        self.connection_label.setText(text)
        self.connection_label.setStyleSheet(
            f"background-color: #ffffff; color: {color}; border-radius: 5px; padding: 4px 10px; font-weight: bold;"
        )
