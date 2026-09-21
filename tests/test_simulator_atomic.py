"""Each Simulator tick is applied to the register bank all at once, so one read never sees two Frames mixed."""
import socket
import sys
import threading
import time

import pytest
from pyModbusTCP.client import ModbusClient
from pyModbusTCP.server import ModbusServer

from tests.support.simulator_banks import quiet_bank

READS = 30000  # "tens of thousands" of reads in the stress test
BLOCKS = [(224, 63), (384, 9)]  # the register ranges the Client reads: 224-286 and 384-392

# Which spreadsheet column feeds which register (the Simulator's register map, written out independently of its code).
REGISTER_COLUMNS = {
    224: "v_vento", 226: "temp_1", 228: "umidade_higromet", 230: "temp_2", 232: "temp_higrometro",
    276: "ref_cel_40", 278: "ref_40_temp", 280: "ref_cel_30", 282: "ref_30_temp", 284: "ref_cel_10",
    286: "ref_10_temp", 384: "ghi", 386: "poa_1", 388: "poa_ri_1", 390: "poa_2", 392: "poa_ri_2",
    501: "testecel40", 1: "Irradiance", 2: "Apparent Power",
}
ABSOLUTE_COLUMNS = {"ghi", "Irradiance", "Apparent Power"}
TIMESTAMP_REGISTER = 500
FAULT_CODE_REGISTER = 5054


@pytest.fixture
def fast_thread_switching():
    """Make Python switch threads far more often, so that a read halfway through an update is very likely
    without the lock (with the default 5 ms it can take many reads to hit the window)."""
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    yield
    sys.setswitchinterval(previous)


def frames_a_and_b(bank):
    """Two complete Frames: every register the Simulator writes set to 1, or to 2."""
    addresses = list(bank.register_values())
    return {address: 1 for address in addresses}, {address: 2 for address in addresses}


def written_values(result, first_address, written):
    """The values in a read result that are registers the Simulator writes."""
    return [value for offset, value in enumerate(result) if first_address + offset in written]


class Applier(threading.Thread):
    """Applies Frame A, then Frame B, over and over, as fast as it can."""

    def __init__(self, bank, frame_a, frame_b):
        super().__init__(daemon=True)
        self.bank, self.frames = bank, (frame_a, frame_b)
        self.stopping = threading.Event()
        self.applied = 0

    def run(self):
        while not self.stopping.is_set():
            for frame in self.frames:
                self.bank.apply_register_values(frame)
                self.applied += 1


# --- the values served are unchanged ----------------------------------------------------------------------


def scaled(value):
    """integer(value x 10), negative values as 0: how the Simulator has always stored a measurement."""
    if isinstance(value, str):
        value = value.replace(",", ".")
    return max(0, int(float(value) * 10))


def expected_registers(simulator, row):
    values = {}
    for address, column in REGISTER_COLUMNS.items():
        value = scaled(simulator.df[column].iloc[row])
        values[address] = abs(value) if column in ABSOLUTE_COLUMNS else value
    hours, minutes, seconds = (int(part) for part in simulator.df["TIME"].iloc[row].split(":"))
    values[TIMESTAMP_REGISTER] = (hours * 3600 + minutes * 60 + seconds) // 2
    values[FAULT_CODE_REGISTER] = 0
    return values


def test_the_registers_hold_the_same_values_as_before_for_the_same_row(simulator):
    bank = quiet_bank(simulator)

    for row in list(range(0, 60)) + [380, 381, 382, 500, 1000, 5000, 20000, 28348]:
        bank.leitura = row
        bank.update_values()
        served = {address: bank._h_regs[address] for address in expected_registers(simulator, row)}
        assert served == expected_registers(simulator, row), f"row {row}"


def test_the_bank_writes_exactly_the_registers_of_the_register_map(simulator):
    bank = quiet_bank(simulator)
    bank.leitura = 0
    bank.update_values()

    assert set(bank.register_values()) == set(REGISTER_COLUMNS) | {TIMESTAMP_REGISTER, FAULT_CODE_REGISTER}
    assert len(bank.register_values()) == 21


def test_reading_returns_the_registers_and_none_for_unknown_ones_as_before(simulator):
    bank = quiet_bank(simulator)
    bank.apply_register_values({224: 7, 226: 8})

    assert bank.get_holding_registers(224, 3) == [7, 0, 8]
    assert bank.get_holding_registers(224) == [7]


# --- one read never sees two Frames -----------------------------------------------------------------------


@pytest.mark.parametrize("first_address, count", BLOCKS)
def test_a_read_never_returns_a_mix_of_two_frames(simulator, fast_thread_switching, first_address, count):
    bank = quiet_bank(simulator)
    frame_a, frame_b = frames_a_and_b(bank)
    written = set(frame_a)
    applier = Applier(bank, frame_a, frame_b)
    bank.apply_register_values(frame_a)
    applier.start()
    mixed = []
    try:
        for _ in range(READS):
            result = bank.get_holding_registers(first_address, count)
            values = written_values(result, first_address, written)
            if len(set(values)) != 1:
                mixed.append(values)
                if len(mixed) >= 5:
                    break
    finally:
        applier.stopping.set()
        applier.join(timeout=5)

    assert applier.applied > 100, "the applier barely ran, so the test proved nothing"
    assert mixed == [], f"a read saw two Frames at once, e.g. {mixed[0]}"


def test_the_update_and_a_read_do_not_deadlock(simulator, fast_thread_switching):
    bank = quiet_bank(simulator)
    frame_a, frame_b = frames_a_and_b(bank)
    applier = Applier(bank, frame_a, frame_b)
    applier.start()
    try:
        deadline = time.monotonic() + 1.0
        reads = 0
        while time.monotonic() < deadline:
            bank.get_holding_registers(224, 63)
            bank.get_holding_registers(384, 9)
            reads += 1
    finally:
        applier.stopping.set()
        applier.join(timeout=5)

    assert not applier.is_alive() and reads > 100


def test_a_real_tick_is_applied_through_the_same_lock_as_a_read(simulator):
    """update_values() applies its Frame while holding the bank's lock, so a read waits for it to finish."""
    bank = quiet_bank(simulator)
    bank.leitura = 0
    bank._h_regs_lock.acquire()
    finished = threading.Event()

    def tick():
        bank.update_values()
        finished.set()

    thread = threading.Thread(target=tick, daemon=True)
    thread.start()
    try:
        assert not finished.wait(0.3), "the tick wrote to the registers without taking the lock"
    finally:
        bank._h_regs_lock.release()
    assert finished.wait(5)


def test_a_read_waits_while_the_lock_is_held(simulator):
    bank = quiet_bank(simulator)
    bank._h_regs_lock.acquire()
    result = []
    thread = threading.Thread(target=lambda: result.append(bank.get_holding_registers(224, 1)), daemon=True)
    thread.start()
    try:
        thread.join(0.3)
        assert thread.is_alive() and result == [], "the read did not take the lock"
    finally:
        bank._h_regs_lock.release()
    thread.join(5)
    assert result == [[0]]


# --- over Modbus ------------------------------------------------------------------------------------------


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_a_client_reading_the_block_224_to_286_never_receives_a_mix_of_two_frames(simulator, fast_thread_switching):
    bank = quiet_bank(simulator)
    frame_a, frame_b = frames_a_and_b(bank)
    written = set(frame_a)
    bank.apply_register_values(frame_a)
    port = free_port()
    server = ModbusServer("127.0.0.1", port, no_block=True, data_bank=bank)
    server.start()
    client = ModbusClient("127.0.0.1", port, timeout=2.0)
    applier = Applier(bank, frame_a, frame_b)
    applier.start()
    mixed, seen_values = [], set()
    try:
        for _ in range(3000):
            result = client.read_holding_registers(224, 63)
            assert result, "the read failed"
            values = written_values(result, 224, written)
            seen_values.update(values)
            if len(set(values)) != 1:
                mixed.append(values)
                if len(mixed) >= 5:
                    break
    finally:
        applier.stopping.set()
        applier.join(timeout=5)
        client.close()
        server.stop()

    assert seen_values == {1, 2}, "the client saw only one of the two Frames, so it proved nothing"
    assert mixed == [], f"a client received two Frames at once, e.g. {mixed[0]}"
