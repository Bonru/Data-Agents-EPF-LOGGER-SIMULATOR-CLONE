"""Behavior kept working by the temporary compatibility adapter, until #8, #9 and #10 replace it."""
import time

import pytest
import requests

from datalogger_client.core.frame import Frame
from datalogger_client.core.registry import CHANNELS, channel_named
from datalogger_client.ui import adapter as adapter_module
from datalogger_client.ui.adapter import CompatibilityAdapter, build_firebase_payload, seconds_to_hms
from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import TickingFakeTransport
from tests.support.heartbeat import run_until

TIMESTAMP_SECONDS = 3725  # 01:02:05
WIND = channel_named("velocidade_vento")
TEMPERATURE_1 = channel_named("temperatura_modulo_1")
HUMIDITY = channel_named("umidade_ar")


def make_frame(value=1.5, timestamp=TIMESTAMP_SECONDS):
    return Frame({channel.name: value for channel in CHANNELS}, timestamp, received_at=0.0)


class FakeLineEdit:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text


def make_adapter(texts=None, writes=None, submitted=None):
    """texts maps a Channel to what the user typed in its sidebar field."""
    writes = [] if writes is None else writes
    submitted = [] if submitted is None else submitted
    fields = {channel: FakeLineEdit(text) for channel, text in (texts or {}).items()}
    return CompatibilityAdapter(
        fields,
        request_write=lambda address, value: writes.append((address, value)),
        submit_firebase=submitted.append,
    )


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
    adapter = make_adapter(submitted=submitted)

    adapter.consume(make_frame())

    assert submitted == [build_firebase_payload(make_frame())]


def test_chart_history_keeps_the_last_30_frames_with_the_timestamp_as_hms():
    adapter = make_adapter()
    for i in range(35):
        adapter.consume(make_frame(float(i)))

    history = adapter.chart_history
    assert list(history.values[WIND.name]) == [float(i) for i in range(5, 35)]
    assert set(history.timestamps) == {"01:02:05"}
    assert len(history.timestamps) == 30
    assert set(history.values) == {channel.name for channel in CHANNELS}


def test_the_chart_time_axis_falls_back_to_the_receive_time_without_a_timestamp():
    adapter = make_adapter()
    received_at = time.mktime((2025, 1, 1, 13, 14, 15, 0, 0, -1))

    adapter.consume(Frame({}, None, received_at=received_at))

    assert list(adapter.chart_history.timestamps) == ["13:14:15"]


def test_seconds_to_hms():
    assert seconds_to_hms(0) == "00:00:00"
    assert seconds_to_hms(TIMESTAMP_SECONDS) == "01:02:05"


def test_every_non_empty_manual_field_is_re_sent_on_each_frame_scaled_by_the_channel():
    writes = []
    adapter = make_adapter({WIND: "5", TEMPERATURE_1: "", HUMIDITY: "-7"}, writes=writes)

    adapter.consume(make_frame())
    adapter.consume(make_frame())

    expected = [(WIND.address, 50), (HUMIDITY.address, -70)]
    assert writes == expected + expected


def test_an_unparsable_manual_field_is_skipped_and_the_others_are_still_sent():
    writes = []
    adapter = make_adapter({WIND: "-", TEMPERATURE_1: "4"}, writes=writes)

    adapter.consume(make_frame())

    assert writes == [(TEMPERATURE_1.address, 40)]


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


def test_the_sidebar_has_a_field_for_each_overridable_channel_and_none_for_the_timestamp(window):
    assert [channel.name for channel in window.manual_fields] == [c.name for c in CHANNELS if c.overridable]
    assert len(window.manual_fields) == 18


def test_charts_are_drawn_only_while_the_chart_view_is_visible(window, monkeypatch):
    drawn = []
    monkeypatch.setattr(window, "display_graph", lambda canvas, channel: drawn.append(channel.name))
    frames = []
    window._worker.frame_ready.connect(frames.append)

    assert run_until(lambda: len(frames) >= 3)
    assert drawn == []  # data view: no chart is redrawn on a Frame

    window.toggle_view()
    assert len(drawn) == len(CHANNELS)  # switching draws each chart once
    seen = len(frames)
    assert run_until(lambda: len(frames) >= seen + 2)
    assert len(drawn) > len(CHANNELS)  # chart view: Frames redraw

    window.toggle_view()
    drawn.clear()
    seen = len(frames)
    assert run_until(lambda: len(frames) >= seen + 2)
    assert drawn == []


def test_the_toggle_swaps_cards_and_charts_and_the_button_text(window):
    wind_card = window.cards["velocidade_vento"]
    timestamp_card = window.channel_cards.timestamp_card
    run_until(lambda: wind_card.label.text().startswith("Vel. vento: 3.2"))

    window.toggle_view()
    assert not wind_card.isVisible() and window.graphs["velocidade_vento"].isVisible()
    assert not timestamp_card.isVisible()
    assert window.config_button.text() == "Exibir Dados"

    window.toggle_view()
    assert wind_card.isVisible() and not window.graphs["velocidade_vento"].isVisible()
    assert timestamp_card.isVisible()
    assert window.config_button.text() == "Exibir Gráfico"


def test_the_cards_follow_the_frames_the_simulator_produces(window):
    timestamp_card = window.channel_cards.timestamp_card

    def timestamp_shown():
        shown = timestamp_card.label.text().split()[1]
        return -1 if shown == "—" else int(shown)  # "—" until the first Frame arrives

    assert run_until(lambda: timestamp_shown() >= 4)  # the Simulator advances 2 s per Frame


def test_manual_insertion_writes_the_value_times_ten_to_the_register(window):
    window.manual_fields[TEMPERATURE_1].setText("25")  # Temperatura 1, register 226

    assert run_until(lambda: (226, 250) in window.fake_transport.calls_named("write"))
