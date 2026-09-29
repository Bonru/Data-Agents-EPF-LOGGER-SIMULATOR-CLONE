class Backoff:
    """How long to wait before the next reconnect attempt: doubles from `initial` up to `cap` seconds."""

    def __init__(self, initial=1.0, cap=5.0):
        self._initial = initial
        self._cap = cap
        self._next = initial

    def next_delay(self):
        delay = self._next
        self._next = min(self._next * 2, self._cap)
        return delay

    def reset(self):
        self._next = self._initial
