"""The Connection state machine and the reconnect backoff. Pure Python: no Qt anywhere in these tests."""
import pytest

from datalogger_client.core.backoff import Backoff
from datalogger_client.core.connection_state import ConnectionState, ConnectionStateMachine

CONNECTED = ConnectionState.CONNECTED
STALE = ConnectionState.STALE
DISCONNECTED = ConnectionState.DISCONNECTED


def connected_machine(now=0.0):
    machine = ConnectionStateMachine()
    machine.poll_answered(now, new_frame=True)
    assert machine.state == CONNECTED
    return machine


def test_it_starts_disconnected_until_a_frame_arrives():
    machine = ConnectionStateMachine()

    assert machine.state == DISCONNECTED
    assert machine.tick(100.0) is False  # time alone does not change it


def test_disconnected_to_connected_when_a_poll_is_answered_with_a_new_frame():
    machine = ConnectionStateMachine()

    changed = machine.poll_answered(0.0, new_frame=True)

    assert changed is True
    assert machine.state == CONNECTED


def test_connected_to_stale_when_no_new_frame_for_more_than_six_seconds():
    machine = connected_machine(0.0)

    machine.poll_answered(6.0, new_frame=False)
    assert machine.state == CONNECTED  # exactly 6 s is still Connected

    changed = machine.poll_answered(6.1, new_frame=False)
    assert changed is True
    assert machine.state == STALE


def test_stale_to_connected_when_a_new_frame_arrives():
    machine = connected_machine(0.0)
    machine.poll_answered(7.0, new_frame=False)
    assert machine.state == STALE

    changed = machine.poll_answered(8.0, new_frame=True)

    assert changed is True
    assert machine.state == CONNECTED


def test_connected_to_disconnected_after_two_consecutive_polls_without_a_response():
    machine = connected_machine(0.0)

    assert machine.poll_failed(1.0) is False
    assert machine.state == CONNECTED  # one failed Poll is not enough

    assert machine.poll_failed(2.0) is True
    assert machine.state == DISCONNECTED


def test_stale_to_disconnected_after_two_consecutive_polls_without_a_response():
    machine = connected_machine(0.0)
    machine.poll_answered(7.0, new_frame=False)
    assert machine.state == STALE

    machine.poll_failed(8.0)
    machine.poll_failed(9.0)

    assert machine.state == DISCONNECTED


def test_disconnected_to_connected_when_the_answered_poll_brings_a_new_frame():
    machine = connected_machine(0.0)
    machine.poll_failed(1.0)
    machine.poll_failed(2.0)
    assert machine.state == DISCONNECTED

    machine.poll_answered(3.0, new_frame=True)

    assert machine.state == CONNECTED


def test_disconnected_to_stale_when_answers_return_but_the_last_new_frame_is_old():
    machine = connected_machine(0.0)
    machine.poll_failed(10.0)
    machine.poll_failed(11.0)
    assert machine.state == DISCONNECTED

    machine.poll_answered(12.0, new_frame=False)  # the Simulator answers but has not advanced

    assert machine.state == STALE


def test_connected_becomes_stale_by_time_alone_on_a_tick():
    machine = connected_machine(0.0)

    machine.tick(7.0)

    assert machine.state == STALE


def test_an_answered_poll_resets_the_failure_count():
    machine = connected_machine(0.0)
    machine.poll_failed(1.0)
    machine.poll_answered(2.0, new_frame=False)

    machine.poll_failed(3.0)

    assert machine.state == CONNECTED  # failures were not consecutive


def test_changed_is_false_when_the_state_stays_the_same():
    machine = connected_machine(0.0)

    assert machine.poll_answered(1.0, new_frame=True) is False


def test_the_thresholds_can_be_changed():
    machine = ConnectionStateMachine(stale_after=1.0, failures_before_disconnected=3)
    machine.poll_answered(0.0, new_frame=True)

    machine.poll_answered(1.5, new_frame=False)
    assert machine.state == STALE

    machine.poll_failed(2.0)
    machine.poll_failed(3.0)
    assert machine.state == STALE
    machine.poll_failed(4.0)
    assert machine.state == DISCONNECTED


def test_backoff_starts_at_one_second_doubles_and_caps_at_five():
    backoff = Backoff()

    assert [backoff.next_delay() for _ in range(6)] == [1.0, 2.0, 4.0, 5.0, 5.0, 5.0]


def test_backoff_starts_over_after_a_reset():
    backoff = Backoff()
    backoff.next_delay()
    backoff.next_delay()

    backoff.reset()

    assert backoff.next_delay() == 1.0
