"""Manual override end to end: the sidebar, the worker that holds it, and the Simulator's registers."""
import pytest
from PyQt6.QtWidgets import QLabel

from datalogger_client.core.registry import CHANNELS, channel_named
from datalogger_client.io_layer.transport import ModbusTcpTransport
from datalogger_client.ui.cards import OVERRIDDEN_BORDER
from datalogger_client.ui.main_window import MainWindow
from datalogger_client.ui.override_field import ACTIVE_TEXT
from tests.support.fake_transport import FakeTransport
from tests.support.heartbeat import run_for, run_until
from tests.support.modbus_server import FakeModbusServer

WIND = channel_named("velocidade_vento")  # register 224
TEMPERATURE_1 = channel_named("temperatura_modulo_1")  # register 226
SIMULATOR_VALUES = {224: 32, 226: 251, 500: 1000}  # wind 3.2, temperature 25.1


@pytest.fixture
def make_window(qapp):
    windows = []

    def make(transport, poll_interval_ms=50):
        window = MainWindow(transport, poll_interval_ms)
        window.show()
        window.frames = []
        window._worker.frame_ready.connect(window.frames.append)
        window.sent = []  # what the UI asked the worker to do
        window.override_set_requested.connect(lambda name, value: window.sent.append(("set", name, value)))
        window.override_clear_requested.connect(lambda name: window.sent.append(("clear", name)))
        windows.append(window)
        return window

    yield make
    for window in windows:
        window.close()


def latest_wind(window):
    """The wind Reading of the latest Frame, or None before any Frame arrived."""
    return window.frames[-1].reading(WIND) if window.frames else None


def type_and_confirm(window, channel, text):
    field = window.override_fields[channel.name]
    field.line_edit.setText(text)
    field.line_edit.editingFinished.emit()  # Enter, or leaving the field
    return field


# --- the sidebar ----------------------------------------------------------------------------------


def test_the_sidebar_has_one_input_per_channel_with_its_display_label_and_none_for_the_timestamp(make_window):
    window = make_window(FakeTransport())

    assert list(window.override_fields) == [channel.name for channel in CHANNELS]  # registry order, all 20
    shown_labels = {label.text() for label in window.findChildren(QLabel)}
    assert {channel.label for channel in CHANNELS} <= shown_labels
    assert "Timestamp" not in shown_labels


def test_a_valid_value_asks_the_worker_to_hold_the_override(make_window):
    window = make_window(FakeTransport())

    type_and_confirm(window, WIND, "12.5")

    assert window.sent == [("set", "velocidade_vento", 12.5)]


@pytest.mark.parametrize("text", ["-1", "6553.6", "abc", "12.55"])
def test_an_invalid_value_shows_an_inline_message_and_sends_nothing(make_window, text):
    window = make_window(FakeTransport())

    field = type_and_confirm(window, WIND, text)

    assert window.sent == []
    assert "6553.5" in field.message_label.text()
    assert not field.message_label.isHidden()


def test_editing_again_dismisses_the_message(make_window):
    window = make_window(FakeTransport())
    field = type_and_confirm(window, WIND, "abc")

    field.line_edit.textEdited.emit("ab")

    assert field.message_label.isHidden()


def test_clearing_the_field_asks_the_worker_to_clear_the_override(make_window):
    window = make_window(FakeTransport())
    type_and_confirm(window, WIND, "12.5")

    type_and_confirm(window, WIND, "")

    assert window.sent == [("set", "velocidade_vento", 12.5), ("clear", "velocidade_vento")]


def test_every_channel_can_be_overridden_including_the_two_that_had_no_field_before(make_window):
    window = make_window(FakeTransport())

    type_and_confirm(window, channel_named("Irradiance"), "800")
    type_and_confirm(window, channel_named("Apparent Power"), "1.5")

    assert window.sent == [("set", "Irradiance", 800.0), ("set", "Apparent Power", 1.5)]


# --- the indicator --------------------------------------------------------------------------------


def test_an_overridden_channel_shows_an_override_active_state_and_clearing_removes_it(make_window):
    window = make_window(FakeTransport(SIMULATOR_VALUES))
    field = type_and_confirm(window, WIND, "12.5")

    assert run_until(lambda: field.message_label.text() == ACTIVE_TEXT)  # the worker confirmed it holds the override
    assert OVERRIDDEN_BORDER in window.cards[WIND.name].styleSheet()
    other = window.override_fields[TEMPERATURE_1.name]
    assert other.message_label.isHidden()  # only the overridden Channel
    assert OVERRIDDEN_BORDER not in window.cards[TEMPERATURE_1.name].styleSheet()

    type_and_confirm(window, WIND, "")

    assert run_until(lambda: field.message_label.isHidden())
    assert OVERRIDDEN_BORDER not in window.cards[WIND.name].styleSheet()


def test_the_overridden_value_shows_on_the_card(make_window):
    window = make_window(FakeTransport(SIMULATOR_VALUES))
    assert run_until(lambda: window.cards[WIND.name].label.text() == "Vel. vento: 3.2 m/s")

    type_and_confirm(window, WIND, "12.5")

    assert run_until(lambda: window.cards[WIND.name].label.text() == "Vel. vento: 12.5 m/s")


# --- against the Simulator, which keeps overwriting the register every tick -----------------------


def test_frames_keep_showing_the_override_and_the_register_receives_the_write_through(make_window):
    with FakeModbusServer() as server:
        server.run_simulator(SIMULATOR_VALUES)
        window = make_window(ModbusTcpTransport("127.0.0.1", server.port, timeout=0.5))
        assert run_until(lambda: latest_wind(window) == 3.2)

        type_and_confirm(window, WIND, "12.5")

        assert run_until(lambda: latest_wind(window) == 12.5)
        first_override_frame = len(window.frames)
        run_for(700)  # several Simulator ticks, each overwriting register 224 with 32
        assert (224, 125) in server.writes  # the write-through: 12.5 times the scale
        assert all(frame.reading(WIND) == 12.5 for frame in window.frames[first_override_frame - 1:])
        assert window.frames[-1].reading(TEMPERATURE_1) == 25.1  # the other Channels are the Simulator's own


def test_the_override_is_written_at_most_once_per_poll(make_window):
    with FakeModbusServer() as server:
        server.run_simulator(SIMULATOR_VALUES)
        window = make_window(ModbusTcpTransport("127.0.0.1", server.port, timeout=0.5))
        type_and_confirm(window, WIND, "12.5")
        assert run_until(lambda: (224, 125) in server.writes)
        writes_before, polls_before = len(server.writes), len([r for r in server.reads if r == (224, 63)])

        run_for(800)

        writes = len(server.writes) - writes_before
        polls = len([r for r in server.reads if r == (224, 63)]) - polls_before
        assert 3 <= writes <= polls  # re-asserted on every Poll, never more than once each


def test_clearing_the_override_ends_it_and_the_simulators_own_value_shows_again(make_window):
    with FakeModbusServer() as server:
        server.run_simulator(SIMULATOR_VALUES)
        window = make_window(ModbusTcpTransport("127.0.0.1", server.port, timeout=0.5))
        type_and_confirm(window, WIND, "12.5")
        assert run_until(lambda: latest_wind(window) == 12.5)

        type_and_confirm(window, WIND, "")

        assert run_until(lambda: latest_wind(window) == 3.2)  # back once the Simulator's tick restores it
        writes_after_clear = len(server.writes)
        run_for(600)
        assert len(server.writes) == writes_after_clear  # nothing is written any more
        assert window.frames[-1].reading(WIND) == 3.2


def test_the_override_is_held_through_a_lost_connection(make_window):
    with FakeModbusServer() as server:
        server.run_simulator(SIMULATOR_VALUES)
        window = make_window(ModbusTcpTransport("127.0.0.1", server.port, timeout=0.5))
        type_and_confirm(window, WIND, "12.5")
        assert run_until(lambda: latest_wind(window) == 12.5)

        server.mode = "drop"
        run_for(400)
        server.mode = "normal"
        writes_before = len(server.writes)

        assert run_until(lambda: len(server.writes) > writes_before, timeout_ms=8000)  # asserted again after reconnecting
        assert window.frames[-1].reading(WIND) == 12.5
