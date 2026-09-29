"""The failure model end to end: the real window and transport against the misbehaving test server."""
import math
import time

import pytest

from datalogger_client.core.backoff import Backoff
from datalogger_client.core.connection_state import ConnectionStateMachine
from datalogger_client.core.registry import channel_named
from datalogger_client.io_layer.transport import REQUEST_TIMEOUT_S, ModbusTcpTransport
from datalogger_client.ui.cards import DIMMED_TEXT_COLOR
from datalogger_client.ui.main_window import MainWindow
from datalogger_client.io_layer.firebase_sender import FirebaseSender
from tests.support.firebase_stub import RecordingPut
from tests.support.heartbeat import run_until
from tests.support.modbus_server import FakeModbusServer

WIND_TEXT = "Vel. vento: 3.2 m/s"
TESTE_CELULA = channel_named("teste_celula_40m")


@pytest.fixture
def server():
    with FakeModbusServer({224: 32, 500: 1000, 501: 70}) as running:
        yield running


@pytest.fixture
def make_window(qapp, server):
    """A window on the test server, with short timeouts and backoff so the tests stay quick."""
    windows = []

    def make(stale_after=6.0, firebase=None):
        transport = ModbusTcpTransport("127.0.0.1", server.port, timeout=0.5)
        window = MainWindow(
            transport, poll_interval_ms=50, firebase=firebase,
            connection=ConnectionStateMachine(stale_after=stale_after),
            backoff=Backoff(initial=0.1, cap=0.3),
        )
        window.show()
        window.frames = []
        window._worker.frame_ready.connect(window.frames.append)
        windows.append(window)
        return window

    yield make
    for window in windows:
        window.close()


def status(window):
    return window.status_area.connection_label.text()


def wind_card(window):
    return window.cards["velocidade_vento"]


def is_dimmed(card):
    return DIMMED_TEXT_COLOR in card.label.styleSheet()


def test_dropping_connections_yields_disconnected_and_recovery_returns_to_connected(make_window, server):
    window = make_window()
    assert run_until(lambda: status(window) == "Conectado")
    assert not is_dimmed(wind_card(window))

    server.mode = "drop"

    assert run_until(lambda: status(window) == "Desconectado")
    assert wind_card(window).label.text() == WIND_TEXT  # the last good value stays visible...
    assert is_dimmed(wind_card(window))  # ...but dimmed
    assert is_dimmed(window.channel_cards.timestamp_card)

    server.mode = "normal"
    server.registers[224] = 40  # the Simulator ticked meanwhile

    assert run_until(lambda: status(window) == "Conectado")
    assert wind_card(window).label.text() == "Vel. vento: 4.0 m/s"
    assert not is_dimmed(wind_card(window))


def test_a_simulator_that_answers_but_stops_changing_yields_stale_and_a_change_returns_to_connected(make_window, server):
    window = make_window(stale_after=0.6)
    assert run_until(lambda: status(window) == "Conectado")

    assert run_until(lambda: status(window) == "Sem atualização")  # answers keep coming, nothing new
    assert wind_card(window).label.text() == WIND_TEXT
    assert is_dimmed(wind_card(window))

    server.registers[224] = 40

    assert run_until(lambda: status(window) == "Conectado")


def test_a_timestamp_register_above_65535_gives_a_partial_frame_with_no_error_and_no_zero(make_window, server):
    server.registers[500] = 70000  # cannot be sent in 16 bits: reading that block fails, the connection stays up
    put = RecordingPut()
    window = make_window(firebase=FirebaseSender(put=put))

    assert run_until(lambda: window.frames and put.payloads)

    frame = window.frames[0]
    assert frame.timestamp is None  # not 0
    assert frame.reading(TESTE_CELULA) is None  # register 501 shares the failed block
    assert frame.reading(channel_named("velocidade_vento")) == 3.2  # everything else is fine
    assert run_until(lambda: status(window) == "Conectado")  # a Partial Frame is not a failure
    assert window.error_label.text() == ""

    # ...and nothing downstream turned the missing values into 0:
    assert window.channel_cards.timestamp_card.label.text() == "Timestamp: —"
    assert window.cards["teste_celula_40m"].label.text() == "Teste Cel 40: — °C"
    assert is_dimmed(window.cards["teste_celula_40m"])
    assert not is_dimmed(wind_card(window))
    assert window.history.readings(TESTE_CELULA)[-1] is None
    assert window.history.time_labels()[-1] == time.strftime("%H:%M:%S", time.localtime(frame.received_at))  # receive time stands in
    by_name = {item["name"]: item["value"] for item in put.payloads[-1]}
    assert by_name["Teste Cel 40"] is None
    assert by_name["Vel. vento"] == 3.2


def test_the_chart_shows_a_missing_reading_as_a_gap_not_as_zero(make_window, server):
    server.registers[500] = 70000
    window = make_window()
    assert run_until(lambda: window.frames)

    chart = window.charts["teste_celula_40m"]
    chart.redraw(window.history)  # straight from the history

    line = chart.axes.lines[0]
    assert all(math.isnan(value) for value in line.get_ydata())


def test_once_the_timestamp_can_be_read_again_the_frame_is_complete(make_window, server):
    server.registers[500] = 70000
    window = make_window()
    assert run_until(lambda: window.frames)

    server.registers[500] = 1002

    assert run_until(lambda: window.frames[-1].timestamp == 2004)  # register 1002, times two
    assert window.frames[-1].reading(TESTE_CELULA) == 7.0


def test_the_request_timeout_is_two_seconds():
    assert REQUEST_TIMEOUT_S == 2.0
    assert ModbusTcpTransport()._client.timeout == 2.0


def test_a_request_to_a_hung_simulator_gives_up_after_the_two_second_timeout():
    with FakeModbusServer() as hung:
        hung.mode = "hang"
        transport = ModbusTcpTransport("127.0.0.1", hung.port)  # the default timeout

        started = time.monotonic()
        result = transport.read_holding_registers(224, 1)
        elapsed = time.monotonic() - started

    assert result is None
    assert 1.8 < elapsed < 3.0
