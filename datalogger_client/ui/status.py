from enum import Enum

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QBoxLayout, QHBoxLayout, QLabel, QWidget

from ..core.connection_state import ConnectionState
from .layout import CONTROL_POINT_SIZE


class FirebaseStatus(Enum):
    DISABLED = "disabled"  # the on/off switch is off
    WAITING = "waiting"  # nothing uploaded yet
    OK = "ok"
    FAILING = "failing"  # the last upload failed


# text, colour of the text
CONNECTION_DISPLAY = {
    ConnectionState.CONNECTED: ("Conectado", "#2e7d32"),
    ConnectionState.STALE: ("Sem atualização", "#b26a00"),
    ConnectionState.DISCONNECTED: ("Desconectado", "#c62828"),
}
FIREBASE_DISPLAY = {
    FirebaseStatus.DISABLED: ("Firebase: desligado", "#6b6b6b"),
    FirebaseStatus.WAITING: ("Firebase: aguardando", "#6b6b6b"),
    FirebaseStatus.OK: ("Firebase: OK", "#2e7d32"),
    FirebaseStatus.FAILING: ("Firebase: falhando", "#c62828"),
}


class StatusArea(QWidget):
    """The header's status area: the Connection state, and beside it the Firebase upload status
    (separate: a failing upload says nothing about the link to the Simulator). Sized by its layout."""

    def __init__(self):
        super().__init__()
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.connection_label = self._add_label(self._layout)
        self.firebase_label = self._add_label(self._layout)
        self.show_connection_state(ConnectionState.DISCONNECTED)
        self.show_firebase_status(FirebaseStatus.WAITING)

    def set_compact(self, compact):
        """Stack the two labels instead of putting them side by side (a narrow header has no room)."""
        direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        self._layout.setDirection(direction)

    def show_connection_state(self, state):
        self._show(self.connection_label, *CONNECTION_DISPLAY[state])

    def show_firebase_status(self, status):
        self._show(self.firebase_label, *FIREBASE_DISPLAY[status])

    @staticmethod
    def _add_label(layout):
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return label

    @staticmethod
    def _show(label, text, color):
        label.setText(text)
        label.setStyleSheet(
            f"background-color: #ffffff; color: {color}; border-radius: 5px; padding: 4px 10px; "
            f"font-weight: bold; font-size: {CONTROL_POINT_SIZE}pt;"
        )
