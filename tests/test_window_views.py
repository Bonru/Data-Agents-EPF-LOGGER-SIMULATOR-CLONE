"""The two views of the window: the data view (cards) and the chart view."""
import pytest

from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import TickingFakeTransport
from tests.support.heartbeat import run_until


@pytest.fixture
def window(qapp):
    transport = TickingFakeTransport({224: 32})
    window = MainWindow(transport, poll_interval_ms=50)
    window.show()
    window.fake_transport = transport
    yield window
    window.close()


def test_the_cards_follow_the_frames_the_simulator_produces(window):
    timestamp_card = window.channel_cards.timestamp_card

    def timestamp_shown():
        """The card's time of day in seconds, or -1 until the first Frame arrives."""
        shown = timestamp_card.label.text().split()[1]
        if shown == "—":
            return -1
        hours, minutes, seconds = (int(part) for part in shown.split(":"))
        return hours * 3600 + minutes * 60 + seconds

    assert run_until(lambda: timestamp_shown() >= 8)  # the fake Simulator advances the register by 2 (4 s) per Frame
