"""The Timestamp in register 500 is seconds of day // 2, so it fits 16 bits for the whole day, and the Client decodes it."""
import socket

import pytest
from pyModbusTCP.server import ModbusServer

from datalogger_client.core.frame import decode_frame
from datalogger_client.core.frame_history import FrameHistory, seconds_to_hms
from datalogger_client.core.registry import CHANNELS, TIMESTAMP
from datalogger_client.io_layer.transport import ModbusTcpTransport
from datalogger_client.io_layer.worker import ModbusWorker
from datalogger_client.ui.cards import ChannelCards
from datalogger_client.ui.charts import ChannelChart
from tests.support.simulator_banks import quiet_bank

MAX_REGISTER = 65535
MAX_ENCODED = 43199  # 86399 // 2


def seconds_of(time_text):
    hours, minutes, seconds = (int(part) for part in time_text.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def use_sheet_with_times(simulator, monkeypatch, times):
    """Make the Simulator read a sheet whose rows are the spreadsheet's first row with these TIME values."""
    sheet = simulator.df.iloc[[0] * len(times)].copy()
    sheet["TIME"] = times
    monkeypatch.setattr(simulator, "df", sheet.reset_index(drop=True))


def register_500_after_tick(bank, row):
    bank.leitura = row
    bank.update_values()
    return bank._h_regs[500]


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def serve(simulator):
    servers = []

    def start(bank):
        port = free_port()
        server = ModbusServer("127.0.0.1", port, no_block=True, data_bank=bank)
        server.start()
        servers.append(server)
        return port

    yield start
    for server in servers:
        server.stop()


# --- the Simulator's side ---------------------------------------------------------------------------------


@pytest.mark.parametrize("time_text, expected", [
    ("00:00:00", 0),
    ("05:31:11", 9935),
    ("18:12:16", 32768),  # the first second whose seconds-of-day (65536) no longer fits 16 bits
    ("23:59:59", 43199),
])
def test_register_500_holds_the_seconds_of_day_divided_by_two_rounded_down(simulator, monkeypatch, time_text, expected):
    use_sheet_with_times(simulator, monkeypatch, [time_text])
    bank = quiet_bank(simulator)

    value = register_500_after_tick(bank, 0)

    assert value == expected == seconds_of(time_text) // 2
    assert value <= MAX_ENCODED <= MAX_REGISTER


def test_no_second_of_the_day_can_overflow_the_register(simulator):
    bank = quiet_bank(simulator)

    encoded = [bank.encode_timestamp(seconds) for seconds in range(86400)]

    assert max(encoded) == MAX_ENCODED
    assert min(encoded) == 0
    assert encoded == sorted(encoded)  # it never goes back within the day


# --- the Client's side --------------------------------------------------------------------------------------


def test_the_registry_decodes_the_timestamp_register_by_doubling_it():
    assert TIMESTAMP.decode(0) == 0 and seconds_to_hms(TIMESTAMP.decode(0)) == "00:00:00"
    assert TIMESTAMP.decode(43199) == 86398 and seconds_to_hms(TIMESTAMP.decode(43199)) == "23:59:58"


def test_decoding_undoes_the_simulators_encoding_to_within_one_second():
    for seconds in range(0, 86400, 7):
        decoded = TIMESTAMP.decode(TIMESTAMP.encode(seconds))
        assert seconds - 1 <= decoded <= seconds


def test_a_frame_from_the_simulators_first_row_shows_05_31_10_on_the_card_and_the_chart_axis(qapp, simulator):
    bank = quiet_bank(simulator)
    bank.leitura = 0
    bank.update_values()  # the spreadsheet's first row: TIME 05:31:11
    registers = {channel.address: bank._h_regs[channel.address] for channel in CHANNELS}
    registers[TIMESTAMP.address] = bank._h_regs[TIMESTAMP.address]

    frame = decode_frame(registers, received_at=0.0)

    assert frame.timestamp == 19870
    cards = ChannelCards()
    cards.show_frame(frame)
    assert cards.timestamp_card.label.text() == "Timestamp: 05:31:10"
    history = FrameHistory()
    history.append(frame)
    assert history.time_labels() == ["05:31:10"]
    chart = ChannelChart(CHANNELS[0])
    chart.redraw(history)
    assert [label.get_text() for label in chart.axes.get_xticklabels()] == ["05:31:10"]


# --- across the wire, with a real Modbus server ------------------------------------------------------------


def test_register_500_can_be_read_late_in_the_day_and_decodes_to_23_59_58(simulator, monkeypatch, serve):
    use_sheet_with_times(simulator, monkeypatch, ["23:59:59"])
    bank = quiet_bank(simulator)
    register_500_after_tick(bank, 0)
    transport = ModbusTcpTransport("127.0.0.1", serve(bank), timeout=2.0)

    raw = transport.read_holding_registers(500, 1)

    assert raw == [43199]  # the read succeeds: no "socket recv error"
    assert seconds_to_hms(TIMESTAMP.decode(raw[0])) == "23:59:58"
    worker = ModbusWorker(transport)
    frames = []
    worker.frame_ready.connect(frames.append)
    worker.poll()  # the whole Client path: block reads, decoding, a Frame
    assert frames and frames[0].timestamp == 86398
    assert seconds_to_hms(frames[0].timestamp) == "23:59:58"


def test_a_bank_started_after_18_12_16_keeps_register_500_readable_on_every_tick(simulator, serve):
    first_late_row = next(i for i in range(len(simulator.df)) if seconds_of(simulator.df["TIME"].iloc[i]) > 65536)
    assert first_late_row == 381  # about 13 minutes in, where the old encoding failed
    bank = quiet_bank(simulator)
    transport = ModbusTcpTransport("127.0.0.1", serve(bank), timeout=2.0)

    for row in range(first_late_row, first_late_row + 173):  # the rest of the first day, tick by tick
        expected = seconds_of(simulator.df["TIME"].iloc[row]) // 2
        assert register_500_after_tick(bank, row) == expected
        assert transport.read_holding_registers(500, 1) == [expected], f"row {row} ({simulator.df['TIME'].iloc[row]})"
