"""Helpers to drive a hand-run QApplication and measure how long its event loop stalls."""
import time

from PyQt6.QtCore import QEventLoop, QTimer


def run_for(milliseconds):
    """Run the Qt event loop for the given time."""
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def run_until(predicate, timeout_ms=5000, step_ms=10):
    """Run the event loop until predicate() is true; returns whether it became true in time."""
    deadline = time.monotonic() + timeout_ms / 1000
    while not predicate():
        if time.monotonic() > deadline:
            return False
        run_for(step_ms)
    return True


class Heartbeat:
    """A timer that ticks every `interval_ms` on the UI thread and records the gaps between ticks.

    A gap much larger than the interval means the UI thread was blocked.
    """

    def __init__(self, interval_ms=20):
        self.gaps_ms = []
        self._last = None
        self._timer = QTimer()
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self.gaps_ms = []
        self._last = time.perf_counter()
        self._timer.start()

    def stop(self):
        self._timer.stop()

    @property
    def max_gap_ms(self):
        return max(self.gaps_ms, default=0.0)

    def _tick(self):
        now = time.perf_counter()
        self.gaps_ms.append((now - self._last) * 1000)
        self._last = now
