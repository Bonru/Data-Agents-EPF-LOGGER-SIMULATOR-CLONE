"""The UI event loop must never stall, whatever the Simulator does."""
import pytest

from datalogger_client.core.registry import CHANNELS
from datalogger_client.io_layer.transport import ModbusTcpTransport
from datalogger_client.ui.main_window import MainWindow
from tests.support.heartbeat import Heartbeat, run_for, run_until
from tests.support.modbus_server import FakeModbusServer

MAX_STALL_MS = 100
MEASURE_MS = 2500


def measure_stall_ms(qapp, port):
    transport = ModbusTcpTransport("127.0.0.1", port, timeout=0.5)
    window = MainWindow(transport, poll_interval_ms=100, submit_firebase=lambda payload: None)
    window.show()
    run_for(500)  # let the window finish its first paint before measuring
    heartbeat = Heartbeat(interval_ms=20)
    heartbeat.start()
    run_for(MEASURE_MS)
    heartbeat.stop()
    window.close()
    return heartbeat.max_gap_ms, len(heartbeat.gaps_ms)


def free_port_with_nothing_listening():
    with FakeModbusServer() as server:
        return server.port


def test_a_healthy_simulator_does_not_stall_the_ui(qapp):
    with FakeModbusServer({224: 32}) as server:
        max_gap, ticks = measure_stall_ms(qapp, server.port)
    assert ticks > MEASURE_MS / 20 / 2
    assert max_gap < MAX_STALL_MS


def test_a_hung_simulator_does_not_stall_the_ui(qapp):
    with FakeModbusServer() as server:
        server.mode = "hang"
        max_gap, _ = measure_stall_ms(qapp, server.port)
    assert max_gap < MAX_STALL_MS


def test_a_slow_simulator_does_not_stall_the_ui(qapp):
    with FakeModbusServer() as server:
        server.mode = "slow"
        server.delay = 0.3
        max_gap, _ = measure_stall_ms(qapp, server.port)
    assert max_gap < MAX_STALL_MS


def test_an_absent_simulator_does_not_stall_the_ui(qapp):
    max_gap, _ = measure_stall_ms(qapp, free_port_with_nothing_listening())
    assert max_gap < MAX_STALL_MS


def test_a_simulator_dropping_connections_does_not_stall_the_ui(qapp):
    with FakeModbusServer({224: 32}) as server:
        transport = ModbusTcpTransport("127.0.0.1", server.port, timeout=0.5)
        window = MainWindow(transport, poll_interval_ms=100, submit_firebase=lambda payload: None)
        window.show()
        run_for(500)
        heartbeat = Heartbeat(interval_ms=20)
        heartbeat.start()
        for _ in range(10):
            server.drop_connections()
            run_for(250)
        heartbeat.stop()
        window.close()
    assert heartbeat.max_gap_ms < MAX_STALL_MS


def test_the_ui_recovers_when_a_late_simulator_appears(qapp):
    with FakeModbusServer({224: 32}) as server:
        port = server.port
        server.mode = "hang"
        transport = ModbusTcpTransport("127.0.0.1", port, timeout=0.3)
        window = MainWindow(transport, poll_interval_ms=100, submit_firebase=lambda payload: None)
        window.show()
        run_for(600)
        assert window.cards["velocidade_vento"].label.text().startswith(f"{CHANNELS[0].label}: --")

        server.mode = "normal"

        assert run_until(lambda: window.cards["velocidade_vento"].label.text() == "Vel. vento: 3.2 m/s", timeout_ms=4000)
        window.close()
