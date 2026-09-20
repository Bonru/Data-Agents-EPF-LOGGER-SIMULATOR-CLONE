"""What the temporary compatibility adapter still does (the Firebase upload), until #10 replaces it."""
import time

import pytest
import requests

from datalogger_client.core.frame import Frame
from datalogger_client.core.registry import CHANNELS, channel_named
from datalogger_client.ui import adapter as adapter_module
from datalogger_client.ui.adapter import CompatibilityAdapter, build_firebase_payload
from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import TickingFakeTransport
from tests.support.heartbeat import run_until

TIMESTAMP_SECONDS = 3725  # 01:02:05
WIND = channel_named("velocidade_vento")


def make_frame(value=1.5, timestamp=TIMESTAMP_SECONDS):
    return Frame({channel.name: value for channel in CHANNELS}, timestamp, received_at=0.0)


def make_adapter(submitted=None):
    submitted = [] if submitted is None else submitted
    return CompatibilityAdapter(submit_firebase=submitted.append)


def test_firebase_payload_has_one_entry_per_channel_in_registry_order_named_by_label():
    payload = build_firebase_payload(make_frame(1.5))

    assert len(payload) == 20
    assert payload[0] == {"name": "Vel. vento", "value": 1.5, "unit": "m/s"}
    assert payload[17] == {"name": "Fault_code", "value": 1.5, "unit": " "}
    assert payload[19] == {"name": "Apparent Power", "value": 1.5, "unit": "kVA"}
    assert [item["name"] for item in payload] == [channel.label for channel in CHANNELS]
    assert all(set(item) == {"name", "value", "unit"} for item in payload)


def test_a_channel_without_a_reading_has_a_null_value_in_the_payload():
    payload = build_firebase_payload(Frame({"velocidade_vento": 3.2}, 100, received_at=0.0))

    assert payload[0]["value"] == 3.2
    assert payload[1]["value"] is None


def test_each_frame_is_handed_to_the_firebase_submission():
    submitted = []
    adapter = make_adapter(submitted)

    adapter.consume(make_frame())

    assert submitted == [build_firebase_payload(make_frame())]


def test_submit_to_firebase_puts_the_payload_on_a_background_thread(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "put", lambda url, json, timeout: calls.append((url, json, timeout)))
    payload = build_firebase_payload(make_frame())

    adapter_module.submit_to_firebase(payload)

    deadline = time.monotonic() + 2
    while not calls and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calls == [("https://monitoramento-usf-default-rtdb.firebaseio.com/parametros.json", payload, 10)]


@pytest.fixture
def window(qapp):
    transport = TickingFakeTransport({224: 32})
    window = MainWindow(transport, poll_interval_ms=50, submit_firebase=lambda payload: None)
    window.show()
    window.fake_transport = transport
    yield window
    window.close()


def test_the_cards_follow_the_frames_the_simulator_produces(window):
    timestamp_card = window.channel_cards.timestamp_card

    def timestamp_shown():
        shown = timestamp_card.label.text().split()[1]
        return -1 if shown == "—" else int(shown)  # "—" until the first Frame arrives

    assert run_until(lambda: timestamp_shown() >= 4)  # the Simulator advances 2 s per Frame
