import time
from collections import deque

FRAME_HISTORY_LENGTH = 30


def seconds_to_hms(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


class FrameHistory:
    """The last few Frames, owned by the UI side; the Client only ever emits the latest Frame.

    The time axis is each Frame's Timestamp as hh:mm:ss, or the time the Client received the
    Frame when the Timestamp is absent. A Channel with no Reading in a Frame has no value there
    (None), never 0. `version` changes with every appended Frame, so a chart can tell whether
    it has drawn the current data.
    """

    def __init__(self, length=FRAME_HISTORY_LENGTH):
        self._entries = deque(maxlen=length)  # (time label, Frame), oldest first
        self.version = 0

    def append(self, frame):
        if frame.timestamp is None:
            label = time.strftime("%H:%M:%S", time.localtime(frame.received_at))
        else:
            label = seconds_to_hms(frame.timestamp)
        self._entries.append((label, frame))
        self.version += 1

    def __len__(self):
        return len(self._entries)

    def time_labels(self):
        return [label for label, _ in self._entries]

    def readings(self, channel):
        """The Channel's Readings, oldest first, aligned with time_labels(); None where a Frame had none."""
        return [frame.reading(channel) for _, frame in self._entries]
