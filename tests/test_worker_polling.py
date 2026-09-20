"""What one Poll reads, when it emits a Frame, and how it reports failures. The worker's poll() is
called directly on the test thread with a fake transport and a fake clock, so no event loop is needed."""
from datalogger_client.core.connection_state import ConnectionState
from datalogger_client.core.registry import BLOCKS, channel_named
from datalogger_client.io_layer.worker import ModbusWorker
from tests.support.fake_transport import FakeTransport

FIRST_BLOCK_ORDER = [(500, 2), (224, 63), (384, 9), (5054, 1), (1, 2)]
ONE_ATTEMPT = FIRST_BLOCK_ORDER + [(500, 2)]  # the five blocks, then the Timestamp block again

WIND = channel_named("velocidade_vento")
HUMIDITY = channel_named("umidade_ar")
GHI = channel_named("radiacao_solar_ghi")
TESTE_CELULA = channel_named("teste_celula_40m")  # register 501, in the same block as the Timestamp
ALL_BLOCK_STARTS = {block.start for block in BLOCKS}


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_worker(transport, clock=None):
    worker = ModbusWorker(transport, clock=clock or FakeClock())
    frames = []
    worker.frame_ready.connect(frames.append)
    return worker, frames


def watch_states(worker):
    states = []
    worker.connection_state_changed.connect(states.append)
    return states


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


# --- Failure model: partial Frames -------------------------------------------------------------


def test_a_failed_block_read_leaves_its_channels_without_a_reading_and_the_frame_is_still_emitted():
    transport = FakeTransport({224: 32, 228: 415, 384: 500, 500: 100}, failing_addresses={224})
    worker, frames = make_worker(transport)

    worker.poll()

    assert len(frames) == 1
    assert frames[0].reading(WIND) is None  # not 0
    assert frames[0].reading(HUMIDITY) is None
    assert frames[0].reading(GHI) == 50.0  # other blocks unaffected
    assert frames[0].timestamp == 100


def test_a_failed_timestamp_block_gives_a_partial_frame_with_no_timestamp_and_no_zero():
    transport = FakeTransport({224: 32, 500: 100, 501: 70}, failing_addresses={500})
    worker, frames = make_worker(transport)

    worker.poll()

    assert len(frames) == 1
    assert frames[0].timestamp is None  # not 0
    assert frames[0].reading(TESTE_CELULA) is None  # same block as the Timestamp
    assert frames[0].reading(WIND) == 3.2
    assert len(read_requests(transport)) == 6  # both Timestamp reads failed alike: no mismatch, no retry


def test_a_timestamp_read_that_fails_only_once_counts_as_a_mismatch():
    def fail_only_the_first_timestamp_read(transport, address, count):
        transport.failing_addresses = {500} if address == 500 and not transport.failed_once else set()
        if address == 500:
            transport.failed_once = True

    transport = FakeTransport({500: 100}, on_read=fail_only_the_first_timestamp_read)
    transport.failed_once = False
    worker, frames = make_worker(transport)

    worker.poll()

    assert len(read_requests(transport)) == 12  # torn first attempt, then one retry
    assert frames[0].timestamp == 100


def test_a_poll_where_every_block_fails_emits_no_frame():
    transport = FakeTransport({224: 32}, failing_addresses=ALL_BLOCK_STARTS)
    worker, frames = make_worker(transport)

    worker.poll()

    assert frames == []


def test_a_poll_gives_up_after_two_failed_block_reads_in_a_row_instead_of_waiting_out_every_block():
    transport = FakeTransport({224: 32}, failing_addresses=ALL_BLOCK_STARTS)
    worker, frames = make_worker(transport)

    worker.poll()

    assert read_requests(transport) == FIRST_BLOCK_ORDER[:2]  # the Timestamp block, then the next: both failed
    assert frames == []


def test_two_failed_blocks_that_are_not_in_a_row_do_not_end_the_poll():
    transport = FakeTransport({224: 32, 500: 100}, failing_addresses={500, 5054})
    worker, frames = make_worker(transport)

    worker.poll()

    assert len(read_requests(transport)) == 6  # every block was still tried
    assert frames[0].reading(WIND) == 3.2


def test_a_poll_where_the_transport_raises_counts_as_no_response():
    class Broken(FakeTransport):
        def read_holding_registers(self, address, count=1):
            raise OSError("boom")

    worker, frames = make_worker(Broken())

    worker.poll()

    assert frames == []


# --- Failure model: Connection state and reconnect backoff --------------------------------------


def test_the_first_answered_poll_makes_the_state_connected():
    worker, _ = make_worker(FakeTransport({500: 100}))
    states = watch_states(worker)

    worker.poll()

    assert states == [ConnectionState.CONNECTED]


def test_two_failed_polls_make_the_state_disconnected_and_a_partial_poll_does_not():
    clock = FakeClock()
    transport = FakeTransport({500: 100})
    worker, _ = make_worker(transport, clock)
    states = watch_states(worker)
    worker.poll()
    transport.failing_addresses = {224}  # a partial Poll is still a usable response
    worker.poll()
    assert states == [ConnectionState.CONNECTED]

    transport.failing_addresses = ALL_BLOCK_STARTS
    worker.poll()  # first failed Poll
    clock.advance(1.0)
    worker.poll()  # second failed Poll, after the backoff

    assert states == [ConnectionState.CONNECTED, ConnectionState.DISCONNECTED]


def test_after_a_failed_poll_the_worker_waits_out_the_backoff_before_trying_again():
    clock = FakeClock()
    transport = FakeTransport(failing_addresses=ALL_BLOCK_STARTS)
    worker, _ = make_worker(transport, clock)

    worker.poll()
    reads_per_poll = len(read_requests(transport))
    clock.advance(0.9)
    worker.poll()
    assert len(read_requests(transport)) == reads_per_poll  # still backing off (1 s)

    clock.advance(0.2)
    worker.poll()
    assert len(read_requests(transport)) == 2 * reads_per_poll  # 1 s passed: reconnect attempt

    clock.advance(1.9)
    worker.poll()
    assert len(read_requests(transport)) == 2 * reads_per_poll  # the next wait is 2 s
    clock.advance(0.2)
    worker.poll()
    assert len(read_requests(transport)) == 3 * reads_per_poll


def test_the_backoff_starts_over_once_the_simulator_answers_again():
    clock = FakeClock()
    transport = FakeTransport({500: 100}, failing_addresses=ALL_BLOCK_STARTS)
    worker, frames = make_worker(transport, clock)
    states = watch_states(worker)
    for _ in range(3):  # three failed Polls push the wait to 4 s
        worker.poll()
        clock.advance(6.0)
    transport.failing_addresses = set()

    worker.poll()  # answered: the Simulator is back
    transport.failing_addresses = ALL_BLOCK_STARTS
    worker.poll()  # fails again
    reads = len(read_requests(transport))
    clock.advance(1.1)
    worker.poll()

    assert len(frames) == 1
    assert len(read_requests(transport)) > reads  # the wait is 1 s again, not 4 or 8
    assert states == [ConnectionState.CONNECTED, ConnectionState.DISCONNECTED]  # that retry was the second failure


def test_an_answering_simulator_that_stops_changing_goes_stale_and_a_change_reconnects_it():
    clock = FakeClock()
    transport = FakeTransport({224: 32, 500: 100})
    worker, _ = make_worker(transport, clock)
    states = watch_states(worker)
    worker.poll()

    clock.advance(6.5)
    worker.poll()  # answered, identical Frame: nothing new for more than 6 s
    transport.registers[224] = 40
    clock.advance(0.5)
    worker.poll()

    assert states == [ConnectionState.CONNECTED, ConnectionState.STALE, ConnectionState.CONNECTED]


def test_the_state_goes_stale_by_time_even_while_the_worker_is_backing_off():
    clock = FakeClock()
    transport = FakeTransport({500: 100})
    worker, _ = make_worker(transport, clock)
    states = watch_states(worker)
    worker.poll()
    transport.failing_addresses = ALL_BLOCK_STARTS
    clock.advance(5.5)
    worker.poll()  # first failure: a 1 s backoff starts
    clock.advance(0.5)
    worker.poll()  # skipped (backing off); 6.0+ s since the last new Frame
    clock.advance(0.1)
    worker.poll()  # skipped again, now past 6 s

    assert states == [ConnectionState.CONNECTED, ConnectionState.STALE]


# --- Manual override: held, overlaid and written through ------------------------------------------


def watch_overrides(worker):
    changes = []
    worker.overrides_changed.connect(changes.append)
    return changes


def writes(transport):
    return transport.calls_named("write")


def test_an_override_is_overlaid_on_the_next_frame_and_written_to_the_register():
    transport = FakeTransport({224: 32, 500: 100})
    worker, frames = make_worker(transport)
    worker.poll()

    worker.set_override("velocidade_vento", 12.5)
    worker.poll()

    assert frames[-1].reading(WIND) == 12.5  # the Simulator still says 3.2
    assert writes(transport) == [(224, 125)]  # the value times the scale


def test_the_override_is_re_asserted_with_exactly_one_write_per_poll():
    transport = FakeTransport({224: 32, 500: 100})
    worker, _ = make_worker(transport)
    worker.set_override("velocidade_vento", 12.5)
    worker.set_override("umidade_ar", 40.0)

    worker.poll()
    assert writes(transport) == [(224, 125), (228, 400)]  # one each
    worker.poll()
    worker.poll()

    assert len(writes(transport)) == 6  # still one per override per Poll, not more


def test_a_torn_poll_that_is_retried_still_writes_each_override_once():
    def change_timestamp_once_mid_poll(transport, address, count):
        if address == 5054 and not transport.changed:
            transport.changed = True
            transport.registers[500] += 2

    transport = FakeTransport({500: 100}, on_read=change_timestamp_once_mid_poll)
    transport.changed = False
    worker, _ = make_worker(transport)
    worker.set_override("velocidade_vento", 12.5)

    worker.poll()  # the first attempt is discarded and read again

    assert writes(transport) == [(224, 125)]


def test_frames_keep_showing_the_override_while_the_simulator_overwrites_the_register():
    transport = FakeTransport({224: 32, 500: 100})
    worker, frames = make_worker(transport)
    worker.set_override("velocidade_vento", 12.5)

    for tick in range(3):
        transport.registers[224] = 30 + tick  # the Simulator's own tick overwrites the register
        transport.registers[500] += 2
        worker.poll()

    assert [frame.reading(WIND) for frame in frames] == [12.5, 12.5, 12.5]


def test_clearing_an_override_ends_it_on_the_next_poll_and_the_simulators_value_shows_again():
    transport = FakeTransport({224: 32, 500: 100})
    worker, frames = make_worker(transport)
    worker.set_override("velocidade_vento", 12.5)
    worker.poll()
    transport.registers[224] = 32  # the Simulator's next tick

    worker.clear_override("velocidade_vento")
    worker.poll()

    assert frames[-1].reading(WIND) == 3.2
    assert len(writes(transport)) == 1  # nothing written after the clear


def test_setting_an_override_emits_a_new_frame_even_if_the_simulator_did_not_change():
    transport = FakeTransport({224: 32, 500: 100})
    worker, frames = make_worker(transport)
    worker.poll()
    worker.poll()
    assert len(frames) == 1

    worker.set_override("velocidade_vento", 12.5)
    worker.poll()
    worker.poll()
    assert len(frames) == 2  # once, not on every Poll

    transport.registers[224] = 32  # the Simulator's own next tick puts its value back
    worker.clear_override("velocidade_vento")
    worker.poll()
    assert [frame.reading(WIND) for frame in frames] == [3.2, 12.5, 3.2]


def test_an_override_does_not_make_a_stalled_simulator_look_alive():
    clock = FakeClock()
    transport = FakeTransport({224: 32, 500: 100})
    worker, _ = make_worker(transport, clock)
    states = watch_states(worker)
    worker.poll()

    clock.advance(5.0)
    worker.set_override("velocidade_vento", 12.5)  # the emitted Frame changes, the Simulator's did not
    worker.poll()
    clock.advance(1.5)
    worker.poll()

    assert states == [ConnectionState.CONNECTED, ConnectionState.STALE]  # 6.5 s without a Simulator Frame


def test_the_worker_reports_which_channels_are_overridden():
    worker, _ = make_worker(FakeTransport())
    changes = watch_overrides(worker)

    worker.set_override("velocidade_vento", 12.5)
    worker.set_override("umidade_ar", 40.0)
    worker.clear_override("velocidade_vento")

    assert changes == [frozenset({"velocidade_vento"}), frozenset({"velocidade_vento", "umidade_ar"}), frozenset({"umidade_ar"})]


def test_an_override_for_an_unknown_channel_or_an_out_of_range_value_is_ignored():
    transport = FakeTransport({500: 100})
    worker, frames = make_worker(transport)
    changes = watch_overrides(worker)

    worker.set_override("no_such_channel", 1.0)
    worker.set_override("velocidade_vento", 7000.0)  # does not fit the 16-bit register
    worker.poll()

    assert changes == []
    assert writes(transport) == []
    assert frames[0].reading(WIND) == 0.0  # the Simulator's own value


def test_no_write_is_attempted_while_the_simulator_does_not_answer():
    transport = FakeTransport({500: 100}, failing_addresses=ALL_BLOCK_STARTS)
    worker, _ = make_worker(transport)
    worker.set_override("velocidade_vento", 12.5)

    worker.poll()

    assert writes(transport) == []


def test_the_override_survives_a_reconnection_and_is_written_again():
    clock = FakeClock()
    transport = FakeTransport({224: 32, 500: 100})
    worker, frames = make_worker(transport, clock)
    worker.set_override("velocidade_vento", 12.5)
    worker.poll()
    transport.failing_addresses = ALL_BLOCK_STARTS
    worker.poll()
    clock.advance(1.5)
    transport.failing_addresses = set()

    worker.poll()

    assert len(writes(transport)) == 2  # once when it first answered, once after coming back
