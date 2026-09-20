"""What one Poll reads and when it emits a Frame. The worker's poll() is called directly on the
test thread with a fake transport, so no event loop is needed."""
import pytest

from datalogger_client.core.registry import channel_named
from datalogger_client.io_layer.worker import ModbusWorker
from tests.support.fake_transport import FakeTransport

FIRST_BLOCK_ORDER = [(500, 2), (224, 63), (384, 9), (5054, 1), (1, 2)]
ONE_ATTEMPT = FIRST_BLOCK_ORDER + [(500, 2)]  # the five blocks, then the Timestamp block again

WIND = channel_named("velocidade_vento")
HUMIDITY = channel_named("umidade_ar")


def make_worker(transport):
    worker = ModbusWorker(transport)
    frames = []
    worker.frame_ready.connect(frames.append)
    return worker, frames


def read_requests(transport):
    return transport.calls_named("read")


def test_a_poll_reads_five_blocks_plus_one_timestamp_re_read():
    transport = FakeTransport({224: 32})
    worker, _ = make_worker(transport)

    worker.poll()

    assert read_requests(transport) == ONE_ATTEMPT
    assert len(set(read_requests(transport))) == 5  # five distinct block requests


def test_the_poll_interval_defaults_to_500_ms():
    assert ModbusWorker(FakeTransport())._interval_ms == 500


def test_the_emitted_frame_holds_the_decoded_readings_and_timestamp():
    transport = FakeTransport({224: 32, 228: 415, 500: 3725})
    worker, frames = make_worker(transport)

    worker.poll()

    assert len(frames) == 1
    assert frames[0].reading(WIND) == 3.2
    assert frames[0].reading(HUMIDITY) == 41.5
    assert frames[0].timestamp == 3725


def test_two_identical_consecutive_polls_emit_one_frame():
    transport = FakeTransport({224: 32, 500: 100})
    worker, frames = make_worker(transport)

    worker.poll()
    worker.poll()

    assert len(frames) == 1


def test_a_changed_value_emits_a_new_frame():
    transport = FakeTransport({224: 32, 500: 100})
    worker, frames = make_worker(transport)
    worker.poll()

    transport.registers[224] = 40
    worker.poll()

    assert [frame.reading(WIND) for frame in frames] == [3.2, 4.0]


def test_a_changed_timestamp_alone_emits_a_new_frame():
    transport = FakeTransport({500: 100})
    worker, frames = make_worker(transport)
    worker.poll()

    transport.registers[500] = 102
    worker.poll()

    assert [frame.timestamp for frame in frames] == [100, 102]


def test_a_timestamp_mismatch_triggers_exactly_one_retry_and_then_proceeds():
    def change_timestamp_once_mid_poll(transport, address, count):
        if address == 5054 and not transport.changed:
            transport.changed = True
            transport.registers[500] += 2

    transport = FakeTransport({224: 32, 500: 100}, on_read=change_timestamp_once_mid_poll)
    transport.changed = False
    worker, frames = make_worker(transport)

    worker.poll()

    assert read_requests(transport) == ONE_ATTEMPT + ONE_ATTEMPT  # the torn attempt, then one retry
    assert [frame.timestamp for frame in frames] == [102]


def test_a_mismatch_that_persists_after_the_retry_is_not_retried_again():
    def change_timestamp_every_attempt(transport, address, count):
        if address == 5054:
            transport.registers[500] += 2

    transport = FakeTransport({500: 100}, on_read=change_timestamp_every_attempt)
    worker, frames = make_worker(transport)

    worker.poll()

    assert len(read_requests(transport)) == 2 * len(ONE_ATTEMPT)  # exactly one retry
    assert len(frames) == 1  # and then it proceeds with what it has


def test_a_failed_block_read_makes_its_values_zero_for_now():
    transport = FakeTransport({224: 32, 228: 415, 384: 500, 500: 100}, failing_addresses={224})
    worker, frames = make_worker(transport)

    worker.poll()

    assert frames[0].reading(WIND) == 0.0
    assert frames[0].reading(HUMIDITY) == 0.0
    assert frames[0].reading(channel_named("radiacao_solar_ghi")) == 50.0  # other blocks unaffected


def test_a_poll_that_raises_emits_nothing_and_does_not_propagate():
    class Broken(FakeTransport):
        def read_holding_registers(self, address, count=1):
            raise OSError("boom")

    worker, frames = make_worker(Broken())

    worker.poll()

    assert frames == []
