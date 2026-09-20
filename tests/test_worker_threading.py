import gc
import threading

import pytest
from PyQt6.QtCore import qInstallMessageHandler

from datalogger_client.core.registry import channel_named
from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import FakeTransport
from tests.support.heartbeat import run_for, run_until

READS_PER_POLL = 6  # five blocks plus the Timestamp block again
WIND = channel_named("velocidade_vento")


@pytest.fixture
def make_window(qapp):
    windows = []

    def make(transport, poll_interval_ms=50, submit_firebase=lambda payload: None):
        window = MainWindow(transport, poll_interval_ms, submit_firebase)
        window.show()
        windows.append(window)
        return window

    yield make
    for window in windows:
        window.close()


def test_every_modbus_call_happens_on_the_worker_thread(make_window):
    transport = FakeTransport()
    window = make_window(transport)
    window.override_fields[WIND.name].line_edit.setText("12")
    window.override_fields[WIND.name].line_edit.editingFinished.emit()  # the user confirms: the override is held and written on every Poll
    assert run_until(lambda: transport.calls_named("write") and len(transport.calls_named("read")) >= READS_PER_POLL)
    window.close()

    kinds = {name for name, _, _ in transport.calls}
    assert {"open", "read", "write", "close"} <= kinds
    threads = {ident for _, _, ident in transport.calls}
    assert threading.get_ident() not in threads
    assert len(threads) == 1


def test_a_write_request_produces_exactly_one_modbus_write(make_window):
    transport = FakeTransport()
    window = make_window(transport, poll_interval_ms=60000)
    assert run_until(lambda: len(transport.calls_named("read")) >= READS_PER_POLL)

    window.write_requested.emit(224, 50)

    assert run_until(lambda: transport.calls_named("write"))
    run_for(200)
    assert transport.calls_named("write") == [(224, 50)]


def test_cards_show_the_polled_values(make_window):
    transport = FakeTransport({224: 32, 226: 251, 500: 3725})
    window = make_window(transport)
    assert run_until(lambda: window.cards["velocidade_vento"].label.text().startswith("Vel. vento: 3.2"))
    assert window.cards["temperatura_modulo_1"].label.text() == "Temperatura 1: 25.1 °C"
    assert window.channel_cards.timestamp_card.label.text() == "Timestamp: 3725 s"


def test_the_window_starts_without_a_simulator_and_shows_no_reading_rather_than_zero(make_window):
    class DownTransport(FakeTransport):
        def read_holding_registers(self, address, count=1):
            self._record("read", address, count)
            return None

    transport = DownTransport()
    window = make_window(transport)
    assert run_until(lambda: len(transport.calls_named("read")) >= READS_PER_POLL)
    run_for(100)

    assert window.cards["velocidade_vento"].label.text() == "Vel. vento: — m/s"
    assert window.status_area.connection_label.text() == "Desconectado"


def test_closing_the_window_stops_the_worker_thread_cleanly(make_window):
    messages = []
    previous = qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    try:
        transport = FakeTransport()
        window = make_window(transport)
        assert run_until(lambda: transport.calls_named("read"))
        thread = window._thread

        window.close()
        gc.collect()

        assert thread.isFinished()
        assert transport.calls_named("close")
        assert not [m for m in messages if "Destroyed while thread is still running" in m]
    finally:
        qInstallMessageHandler(previous)

