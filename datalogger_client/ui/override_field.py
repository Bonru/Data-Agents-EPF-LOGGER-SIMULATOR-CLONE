from PyQt6.QtCore import QObject, pyqtSignal

from ..core.overrides import InvalidOverride, parse_override

ACTIVE_BORDER = "border: 2px solid #e69500;"
ERROR_STYLE = "background-color: #ffffff; color: #c62828;"
ACTIVE_STYLE = "background-color: #ffffff; color: #b26a00;"
ACTIVE_TEXT = "Override ativo"


class OverrideField(QObject):
    """A sidebar input for one Channel's Manual override.

    When the user finishes editing (Enter, or leaving the field) the text is checked: valid text
    asks for the override to be held, empty text asks for it to be cleared, anything else shows an
    inline message and sends nothing. The UI only emits signals; the worker holds the override
    and reports back which ones are active (`show_active`).
    """

    set_requested = pyqtSignal(str, float)  # Channel name, value
    clear_requested = pyqtSignal(str)

    def __init__(self, channel, line_edit, message_label, base_style):
        super().__init__()
        self.channel = channel
        self.line_edit = line_edit
        self.message_label = message_label
        self._base_style = base_style
        self._error = ""
        self._active = False
        line_edit.editingFinished.connect(self._apply)
        line_edit.textEdited.connect(self._dismiss_error)
        self._render()

    def show_active(self, active):
        self._active = active
        self._render()

    def _apply(self):
        text = self.line_edit.text().strip()
        if text == "":
            self._error = ""
            self._render()
            self.clear_requested.emit(self.channel.name)
            return
        try:
            value = parse_override(self.channel, text)
        except InvalidOverride as invalid:
            self._error = str(invalid)
            self._render()
            return
        self._error = ""
        self._render()
        self.set_requested.emit(self.channel.name, value)

    def _dismiss_error(self):
        self._error = ""
        self._render()

    def _render(self):
        self.line_edit.setStyleSheet(self._base_style + (ACTIVE_BORDER if self._active else ""))
        self.line_edit.setToolTip(ACTIVE_TEXT if self._active else "")
        text = self._error or (ACTIVE_TEXT if self._active else "")
        self.message_label.setText(text)
        self.message_label.setStyleSheet(ERROR_STYLE if self._error else ACTIVE_STYLE)
        self.message_label.setVisible(bool(text))
