"""The Fault code is an unscaled integer: registry scale, override validation and write, display, payload."""
import json
from pathlib import Path

import pytest

from datalogger_client.core.frame import Frame, decode_frame
from datalogger_client.core.overrides import InvalidOverride, ManualOverrides, parse_override
from datalogger_client.core.registry import CHANNELS, channel_named
from datalogger_client.io_layer.firebase_sender import FirebaseSender, build_firebase_payload
from datalogger_client.io_layer.transport import ModbusTcpTransport
from datalogger_client.io_layer.worker import ModbusWorker
from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import FakeTransport
from tests.support.firebase_stub import RecordingPut
from tests.support.heartbeat import run_until
from tests.support.modbus_server import FakeModbusServer

FAULT = channel_named("fault_code")  # register 5054
WIND = channel_named("velocidade_vento")  # register 224, x10
REPO_ROOT = Path(__file__).resolve().parent.parent


def fault_entry(payload):
    return next(item for item in payload if item["name"] == "Fault_code")


def frame_with_fault(raw):
    """A Frame as the Client builds it from the registers, with this raw Fault code and 3.2 m/s of wind."""
    return decode_frame({5054: raw, 224: 32}, received_at=0.0)


# --- the registry ---------------------------------------------------------------------------------


def test_the_fault_code_has_scale_1_and_every_other_channel_keeps_scale_10():
    assert FAULT.scale == 1
    assert {channel.scale for channel in CHANNELS if channel is not FAULT} == {10}


def test_the_fault_code_is_read_and_written_as_a_plain_integer():
    assert FAULT.decode(3) == 3 and type(FAULT.decode(3)) is int
    assert FAULT.decode(0) == 0 and type(FAULT.decode(0)) is int
    assert FAULT.encode(3) == 3  # not 30
    assert FAULT.encode(65535) == 65535


def test_the_other_channels_are_still_read_as_tenths():
    assert WIND.decode(32) == 3.2
    assert WIND.decode(0) == 0.0 and type(WIND.decode(0)) is float
    assert WIND.encode(3.2) == 32


def test_a_frame_built_from_registers_holds_the_fault_code_as_an_integer():
    frame = frame_with_fault(3)

    assert frame.reading(FAULT) == 3 and type(frame.reading(FAULT)) is int
    assert frame.reading(WIND) == 3.2


# --- validation of the override ---------------------------------------------------------------------


@pytest.mark.parametrize("text", ["3", "65535", "0", " 7 "])
def test_the_fault_code_override_accepts_integers_from_0_to_65535(text):
    assert parse_override(FAULT, text) == float(text)


@pytest.mark.parametrize("text", ["3.5", "3.0", "65536", "-1", "abc", "", ".5", "1e2"])
def test_the_fault_code_override_rejects_anything_else(text):
    with pytest.raises(InvalidOverride) as error:
        parse_override(FAULT, text)

    assert str(error.value) == "Use 0 a 65535 (inteiro)"


def test_the_other_channels_keep_one_decimal_and_the_range_0_to_6553_5():
    assert [parse_override(WIND, text) for text in ("12.5", "0", "6553.5")] == [12.5, 0.0, 6553.5]
    for text in ("12.55", "6553.6", "-1", "abc", "7000"):
        with pytest.raises(InvalidOverride):
            parse_override(WIND, text)


# --- writing the override -----------------------------------------------------------------------------


def test_overriding_the_fault_code_writes_the_raw_integer_and_shows_it_unscaled():
    overrides = ManualOverrides()
    overrides.set(FAULT, 3.0)

    assert overrides.register_writes() == [(5054, 3)]  # not 30
    shown = overrides.overlay(Frame({}, 3600, received_at=0.0)).reading(FAULT)
    assert shown == 3 and type(shown) is int


def test_the_worker_writes_3_to_register_5054_and_emits_frames_showing_3():
    transport = FakeTransport({5054: 0, 500: 100})
    worker = ModbusWorker(transport)
    frames = []
    worker.frame_ready.connect(frames.append)
    worker.poll()

    worker.set_override("fault_code", 3.0)
    worker.poll()

    assert transport.calls_named("write") == [(5054, 3)]
    assert frames[0].reading(FAULT) == 0 and frames[-1].reading(FAULT) == 3


def test_other_channels_still_write_ten_times_the_value():
    transport = FakeTransport({500: 100})
    worker = ModbusWorker(transport)
    worker.set_override("velocidade_vento", 12.5)

    worker.poll()

    assert transport.calls_named("write") == [(224, 125)]


# --- display and payload ------------------------------------------------------------------------------


@pytest.fixture
def make_window(qapp):
    windows = []

    def make(transport, firebase=None):
        window = MainWindow(transport, poll_interval_ms=50, firebase=firebase)
        window.show()
        windows.append(window)
        return window

    yield make
    for window in windows:
        window.close()


def test_when_the_simulator_reports_0_the_card_shows_0_not_0_point_0(make_window):
    window = make_window(FakeTransport({5054: 0, 224: 32, 500: 100}))

    assert run_until(lambda: window.cards["fault_code"].label.text().startswith("Fault_code: 0"))
    assert "0.0" not in window.cards["fault_code"].label.text()
    assert run_until(lambda: window.cards["velocidade_vento"].label.text() == "Vel. vento: 3.2 m/s")  # others as before


def test_a_non_zero_fault_code_is_displayed_as_is_not_divided_by_ten(make_window):
    window = make_window(FakeTransport({5054: 3, 500: 100}))

    assert run_until(lambda: window.cards["fault_code"].label.text().startswith("Fault_code: 3"))
    assert "0.3" not in window.cards["fault_code"].label.text()


def test_the_payload_sends_an_integer_for_the_fault_code():
    for raw in (0, 3):
        payload = build_firebase_payload(frame_with_fault(raw))

        assert fault_entry(payload)["value"] == raw and type(fault_entry(payload)["value"]) is int
        assert next(i for i in payload if i["name"] == "Vel. vento")["value"] == 3.2

    assert '{"name": "Fault_code", "value": 0, "unit": " "}' in json.dumps(build_firebase_payload(frame_with_fault(0)))



# --- the sidebar ----------------------------------------------------------------------------------------


def type_and_confirm(window, channel, text):
    field = window.override_fields[channel.name]
    field.line_edit.setText(text)
    field.line_edit.editingFinished.emit()
    return field


def test_the_sidebar_field_for_the_fault_code_takes_integers_only(make_window):
    window = make_window(FakeTransport())
    sent = []
    window.override_set_requested.connect(lambda name, value: sent.append((name, value)))

    field = type_and_confirm(window, FAULT, "3.5")
    assert sent == [] and field.message_label.text() == "Use 0 a 65535 (inteiro)"

    type_and_confirm(window, FAULT, "3")
    assert sent == [("fault_code", 3.0)]

    type_and_confirm(window, WIND, "12.5")  # and a scaled Channel still takes one decimal
    assert sent[-1] == ("velocidade_vento", 12.5)


# --- against the Simulator, end to end ----------------------------------------------------------------------


def test_overriding_the_fault_code_makes_the_register_receive_3_and_the_frame_card_and_payload_show_3(make_window):
    put = RecordingPut()
    with FakeModbusServer() as server:
        server.run_simulator({224: 32, 5054: 0, 500: 1000})  # the Simulator: fault code 0, unscaled
        window = make_window(ModbusTcpTransport("127.0.0.1", server.port, timeout=0.5), FirebaseSender(put=put))
        frames = []
        window._worker.frame_ready.connect(frames.append)
        assert run_until(lambda: frames and frames[-1].reading(FAULT) == 0)
        assert window.cards["fault_code"].label.text().startswith("Fault_code: 0")
        assert type(fault_entry(put.payloads[-1])["value"]) is int and fault_entry(put.payloads[-1])["value"] == 0

        type_and_confirm(window, FAULT, "3")

        assert run_until(lambda: frames[-1].reading(FAULT) == 3)
        assert run_until(lambda: window.cards["fault_code"].label.text().startswith("Fault_code: 3"))
        assert run_until(lambda: (5054, 3) in server.writes)
        assert (5054, 30) not in server.writes  # the raw integer, never times ten
        assert run_until(lambda: put.payloads and fault_entry(put.payloads[-1])["value"] == 3)
        assert type(fault_entry(put.payloads[-1])["value"]) is int


# --- the glossary -------------------------------------------------------------------------------------------


def test_the_glossary_records_the_decision_and_what_the_manual_does_and_does_not_say():
    text = (REPO_ROOT / "CONTEXT.md").read_text(encoding="utf-8")

    assert "Fault code scale (unverified)" not in text  # the open question is closed
    assert "unscaled integer" in text
    assert "406-414" in text  # what the manual does document
    assert "32-bit" in text and "float" in text
    for undocumented in ("5054", "500", "501"):
        assert undocumented in text
    assert "couldn't be read in this environment" not in text  # the manual has now been read
    assert "poppler" not in text
    assert "per the Datalogger's manual" not in text
