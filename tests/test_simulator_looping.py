"""The Simulator's updater loops the dataset and survives a failed update instead of dying silently."""
import socket
import threading
import time

import pytest
from pyModbusTCP.client import ModbusClient
from pyModbusTCP.server import ModbusServer

# The updater loop never ends by itself, so the tests end it by raising SystemExit inside it; pytest reports
# any exception that ends a thread, and here that is the intended way for it to end.
pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")

WRAP_MESSAGE = "End of dataset reached; restarting from the first row."
ROW_VALUES = [1.0, 2.0, 3.0]  # wind speed of the three rows: registers 10, 20, 30
WIND_REGISTERS = [10, 20, 30]
TICK = 0.01


def three_rows(simulator, wind_speeds=ROW_VALUES):
    """A small dataset: the spreadsheet's first row three times, with a different wind speed in each."""
    rows = simulator.df.iloc[[0] * len(wind_speeds)].copy().reset_index(drop=True)
    rows["v_vento"] = wind_speeds
    return rows


def recording_bank(simulator, *args, **kwargs):
    """A register bank that records what its updater does, and whose updater thread can be ended by the test."""

    class RecordingBank(simulator.MyDataBank):
        def __init__(self, *bank_args, **bank_kwargs):
            self.rows_read = []  # the row number of every read, the one at start-up included
            self.served = []  # register 224 after every successful update made by the updater thread
            self.done = threading.Event()
            super().__init__(*bank_args, **bank_kwargs)

        def next_row_number(self):
            row = super().next_row_number()
            self.rows_read.append(row)
            return row

        def update_values(self):
            if self.done.is_set():
                raise SystemExit  # ends the updater thread quietly (it is not an Exception, so the loop lets it go)
            values = super().update_values()
            self.served.append(self._h_regs[224])
            return values

        def finish(self):
            self.done.set()
            self.update_thread.join(timeout=5)

    return RecordingBank(*args, **kwargs)


def wait_until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.005)
    return True


# --- looping ----------------------------------------------------------------------------------------------


def test_over_seven_ticks_the_rows_follow_0_1_2_0_1_2_0_and_the_updater_is_still_alive(simulator):
    bank = recording_bank(simulator, three_rows(simulator), tick_seconds=TICK)
    try:
        assert wait_until(lambda: len(bank.served) >= 6)  # six ticks have finished their updates

        assert bank.rows_read[:7] == [0, 1, 2, 0, 1, 2, 0]  # start-up read row 0, then six ticks
        assert bank.served[:6] == [20, 30, 10, 20, 30, 10]  # the values the ticks served: rows 1, 2, 0, 1, 2, 0
        assert bank.update_thread.is_alive()
    finally:
        bank.finish()
    assert not bank.update_thread.is_alive()  # and it ended only because the test asked it to


def test_the_wrap_message_is_printed_once_per_wrap_not_once_per_tick(simulator, capsys):
    bank = recording_bank(simulator, three_rows(simulator), tick_seconds=TICK)
    try:
        assert wait_until(lambda: len(bank.rows_read) >= 10)
    finally:
        bank.finish()

    wraps = (len(bank.rows_read) - 1) // 3  # reads 3, 6, 9... come back to row 0
    output = capsys.readouterr().out
    assert wraps >= 3
    assert output.count(WRAP_MESSAGE) == wraps
    assert len(bank.rows_read) > output.count(WRAP_MESSAGE)  # far fewer messages than ticks


def test_no_message_is_printed_before_the_dataset_is_exhausted(simulator, capsys):
    bank = recording_bank(simulator, three_rows(simulator), tick_seconds=0.5)  # slow: the third read is 0.5 s away
    try:
        assert wait_until(lambda: len(bank.rows_read) >= 2)  # start-up (row 0) and the first tick (row 1)
        printed_so_far = capsys.readouterr().out
    finally:
        bank.finish()

    assert bank.rows_read[:2] == [0, 1]
    assert WRAP_MESSAGE not in printed_so_far


# --- surviving a failed update ------------------------------------------------------------------------------


def test_a_failed_update_is_printed_with_its_traceback_and_the_next_tick_updates_normally(simulator, capsys):
    rows = three_rows(simulator, [1.0, "abc", 3.0])  # row 1 has a non-numeric wind speed
    bank = recording_bank(simulator, rows, tick_seconds=TICK)
    try:
        assert wait_until(lambda: len(bank.served) >= 3)

        assert bank.update_thread.is_alive()
        assert bank.served[:3] == [30, 10, 30]  # row 1 served nothing; rows 2, 0 and 2 again updated normally
        assert bank.rows_read[:5] == [0, 1, 2, 0, 1]  # the bad row was passed over, not retried forever
    finally:
        bank.finish()

    printed = capsys.readouterr()
    assert "Traceback" in printed.out + printed.err
    assert "ValueError" in printed.out + printed.err
    assert "abc" in printed.out + printed.err


def test_the_registers_keep_their_last_good_values_while_an_update_fails(simulator):
    rows = three_rows(simulator, [1.0, 2.0, "abc", 3.0])  # row 2 is the bad one
    bank = recording_bank(simulator, rows, tick_seconds=0.2)  # slow enough to look between two ticks
    try:
        assert wait_until(lambda: bank.rows_read[-1:] == [2])  # the tick that reads the bad row has run

        assert bank.served == [20]  # only row 1's tick succeeded so far
        assert bank._h_regs[224] == 20  # still row 1's value: the failed update wrote nothing
    finally:
        bank.finish()


def test_a_bank_that_fails_at_start_up_still_raises_as_before(simulator):
    with pytest.raises(ValueError):
        simulator.MyDataBank(three_rows(simulator, ["abc", 2.0, 3.0]), tick_seconds=TICK)


# --- the constructor ------------------------------------------------------------------------------------------


def test_without_arguments_the_bank_uses_the_loaded_spreadsheet_a_two_second_tick_and_starts_at_row_0(simulator):
    bank = recording_bank(simulator)
    try:
        assert bank.dataset is simulator.df
        assert bank.timer == 2
        assert bank.rows_read[0] == 0
    finally:
        bank.finish()


def test_a_dataset_and_a_tick_can_be_given(simulator):
    dataset = three_rows(simulator)
    bank = recording_bank(simulator, dataset, tick_seconds=0.5)
    try:
        assert bank.dataset is dataset
        assert bank.timer == 0.5
    finally:
        bank.finish()


# --- end to end, over Modbus ----------------------------------------------------------------------------------


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_a_client_reading_register_224_sees_the_values_cycle_and_keep_advancing_after_the_wrap(simulator):
    bank = recording_bank(simulator, three_rows(simulator), tick_seconds=0.05)
    port = free_port()
    server = ModbusServer("127.0.0.1", port, no_block=True, data_bank=bank)
    server.start()
    client = ModbusClient("127.0.0.1", port, timeout=2.0)
    try:
        seen = []
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and len(seen) < 9:
            value = client.read_holding_registers(224, 1)
            assert value, "the read failed"
            if not seen or seen[-1] != value[0]:
                seen.append(value[0])  # only when the served value changes
            time.sleep(0.005)
    finally:
        client.close()
        server.stop()
        bank.finish()

    assert len(seen) >= 9, seen
    following = {10: 20, 20: 30, 30: 10}  # rows 0 -> 1 -> 2 -> 0
    assert all(following[a] == b for a, b in zip(seen, seen[1:])), seen  # it cycles, in order
    assert seen.count(10) >= 2  # and after the wrap it went on advancing: row 0 came round again
