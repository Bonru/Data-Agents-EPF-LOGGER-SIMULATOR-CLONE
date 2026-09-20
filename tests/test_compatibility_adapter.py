"""Behavior kept working by the temporary compatibility adapter, until #8, #9 and #10 replace it."""
import time

import pytest
import requests

from datalogger_client.io_layer.channels import CHANNELS, OVERRIDABLE_CHANNELS
from datalogger_client.io_layer.snapshot import ChannelEntry, Snapshot
from datalogger_client.ui import adapter as adapter_module
from datalogger_client.ui.adapter import CompatibilityAdapter, build_firebase_payload, seconds_to_hms
from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import FakeTransport
from tests.support.heartbeat import run_for, run_until

TIMESTAMP_SECONDS = 3725  # 01:02:05


def make_snapshot(value=1.5):
    entries = tuple(ChannelEntry(value, channel.label, channel.unit) for channel in CHANNELS)
    return Snapshot(entries, TIMESTAMP_SECONDS)


class FakeLineEdit:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text


def make_adapter(texts=(), writes=None, submitted=None):
    writes = [] if writes is None else writes
    submitted = [] if submitted is None else submitted
    line_edits = [FakeLineEdit(text) for text in texts] + [FakeLineEdit()] * (len(OVERRIDABLE_CHANNELS) - len(texts))
    return CompatibilityAdapter(
        line_edits,
        request_write=lambda address, value: writes.append((address, value)),
        submit_firebase=submitted.append,
    )


def test_firebase_payload_has_the_same_shape_as_before():
    payload = build_firebase_payload(make_snapshot(1.5))

    assert len(payload) == 21
    assert payload[0] == {"name": "Vel. vento", "value": 1.5, "unit": "m/s"}
    assert payload[20] == {"name": "Apparent Power", "value": 1.5, "unit": "kVA"}
    assert all(set(item) == {"name", "value", "unit"} for item in payload)


def test_each_snapshot_is_handed_to_the_firebase_submission():
    submitted = []
    adapter = make_adapter(submitted=submitted)

    adapter.consume(make_snapshot())

    assert submitted == [build_firebase_payload(make_snapshot())]


def test_chart_history_keeps_the_last_30_values_and_the_timestamp_as_hms():
    adapter = make_adapter(writes=[], submitted=[])
    for i in range(35):
        adapter.consume(make_snapshot(float(i)))

    assert list(adapter.chart_history["Vel. vento"]) == [float(i) for i in range(5, 35)]
    assert set(adapter.chart_history["Timestamp"]) == {"01:02:05"}
    assert len(adapter.chart_history["Timestamp"]) == 30
    assert set(adapter.chart_history) == {channel.label for channel in CHANNELS}


def test_seconds_to_hms():
    assert seconds_to_hms(0) == "00:00:00"
    assert seconds_to_hms(TIMESTAMP_SECONDS) == "01:02:05"


def test_every_non_empty_manual_field_is_re_sent_on_each_snapshot_scaled_by_ten():
    writes = []
    adapter = make_adapter(texts=["5", "", "-7"], writes=writes, submitted=[])

    adapter.consume(make_snapshot())
    adapter.consume(make_snapshot())

    expected = [(OVERRIDABLE_CHANNELS[0].address, 50), (OVERRIDABLE_CHANNELS[2].address, -70)]
    assert writes == expected + expected


def test_an_unparsable_manual_field_is_skipped_and_the_others_are_still_sent():
    writes = []
    adapter = make_adapter(texts=["-", "4"], writes=writes, submitted=[])

    adapter.consume(make_snapshot())

    assert writes == [(OVERRIDABLE_CHANNELS[1].address, 40)]


def test_submit_to_firebase_puts_the_payload_on_a_background_thread(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "put", lambda url, json, timeout: calls.append((url, json, timeout)))
    payload = build_firebase_payload(make_snapshot())

    adapter_module.submit_to_firebase(payload)

    deadline = time.monotonic() + 2
    while not calls and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calls == [("https://monitoramento-usf-default-rtdb.firebaseio.com/parametros.json", payload, 10)]


@pytest.fixture
def window(qapp):
    transport = FakeTransport({224: 32})
    window = MainWindow(transport, poll_interval_ms=50, submit_firebase=lambda payload: None)
    window.show()
    window.fake_transport = transport
    yield window
    window.close()


def test_charts_are_drawn_only_while_the_chart_view_is_visible(window, monkeypatch):
    drawn = []
    monkeypatch.setattr(window, "display_graph", lambda canvas, data_type: drawn.append(data_type))
    snapshots = []
    window._worker.snapshot_ready.connect(snapshots.append)

    assert run_until(lambda: len(snapshots) >= 3)
    assert drawn == []  # data view: no chart is redrawn on a snapshot

    window.toggle_view()
    assert len(drawn) == len(CHANNELS)  # switching draws each chart once
    seen = len(snapshots)
    assert run_until(lambda: len(snapshots) >= seen + 2)
    assert len(drawn) > len(CHANNELS)  # chart view: snapshots redraw

    window.toggle_view()
    drawn.clear()
    seen = len(snapshots)
    assert run_until(lambda: len(snapshots) >= seen + 2)
    assert drawn == []


def test_the_toggle_swaps_cards_and_charts_and_the_button_text(window):
    run_until(lambda: window.cards[0].label.text().startswith("Vel. vento: 3.2"))

    window.toggle_view()
    assert not window.cards[0].isVisible() and window.graphs[0].isVisible()
    assert window.config_button.text() == "Exibir Dados"

    window.toggle_view()
    assert window.cards[0].isVisible() and not window.graphs[0].isVisible()
    assert window.config_button.text() == "Exibir Gráfico"


def test_manual_insertion_writes_the_value_times_ten_to_the_register(window):
    window.line_edits[1].setText("25")  # Temperatura 1, register 226

    assert run_until(lambda: (226, 250) in window.fake_transport.calls_named("write"))
