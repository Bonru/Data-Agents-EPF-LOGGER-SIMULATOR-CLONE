from enum import Enum


class ConnectionState(Enum):
    CONNECTED = "connected"
    STALE = "stale"
    DISCONNECTED = "disconnected"


class ConnectionStateMachine:
    """Health of the Client's link to the Simulator, from what each Poll found.

    - Disconnected: no Frame has arrived yet, or `failures_before_disconnected`
      Polls in a row got no usable response.
    - Connected: Polls get answers and a new Frame arrived within `stale_after` seconds.
    - Stale: Polls get answers but no new Frame for more than `stale_after` seconds.

    Time is passed in (`now`, seconds on any monotonic clock) so it is testable without waiting.
    Every method returns whether the state changed.
    """

    def __init__(self, stale_after=6.0, failures_before_disconnected=2):
        self._stale_after = stale_after
        self._failures_before_disconnected = failures_before_disconnected
        self._consecutive_failures = 0
        self._last_new_frame_at = None
        self.state = ConnectionState.DISCONNECTED

    def poll_answered(self, now, new_frame):
        """A Poll got a usable response; `new_frame` is whether it produced a Frame that differs from the last."""
        self._consecutive_failures = 0
        if new_frame:
            self._last_new_frame_at = now
        return self._evaluate(now)

    def poll_failed(self, now):
        """A Poll got no usable response."""
        self._consecutive_failures += 1
        return self._evaluate(now)

    def tick(self, now):
        """Let time pass without a Poll (a Connected link goes Stale by itself)."""
        return self._evaluate(now)

    def _evaluate(self, now):
        if self._consecutive_failures >= self._failures_before_disconnected or self._last_new_frame_at is None:
            new_state = ConnectionState.DISCONNECTED
        elif now - self._last_new_frame_at <= self._stale_after:
            new_state = ConnectionState.CONNECTED
        else:
            new_state = ConnectionState.STALE
        changed = new_state != self.state
        self.state = new_state
        return changed
