"""The immutable Frame. Pure Python: no Qt anywhere in these tests."""
import dataclasses

import pytest

from datalogger_client.core.frame import Frame, decode_frame
from datalogger_client.core.registry import CHANNELS, TIMESTAMP, channel_named


def test_a_frame_is_immutable():
    frame = Frame({"velocidade_vento": 3.2}, 100, received_at=1.0)

    with pytest.raises(dataclasses.FrozenInstanceError):
        frame.timestamp = 5
    with pytest.raises(TypeError):
        frame.readings["velocidade_vento"] = 9.9


def test_a_frame_does_not_change_when_the_source_mapping_does():
    source = {"velocidade_vento": 3.2}
    frame = Frame(source, 100, received_at=1.0)

    source["velocidade_vento"] = 9.9

    assert frame.readings["velocidade_vento"] == 3.2


def test_readings_can_be_absent():
    frame = Frame({"velocidade_vento": 3.2}, 100, received_at=1.0)

    assert frame.reading(channel_named("velocidade_vento")) == 3.2
    assert frame.reading(channel_named("umidade_ar")) is None


def test_an_explicit_none_reading_is_the_same_as_an_absent_one():
    assert Frame({"umidade_ar": None}, 100, 1.0) == Frame({}, 100, 1.0)


def test_the_timestamp_can_be_absent():
    frame = Frame({}, None, received_at=1.0)

    assert frame.timestamp is None


def test_equality_ignores_the_receive_time():
    assert Frame({"umidade_ar": 40.0}, 100, received_at=1.0) == Frame({"umidade_ar": 40.0}, 100, received_at=99.0)


def test_frames_with_different_readings_or_timestamps_differ():
    base = Frame({"umidade_ar": 40.0}, 100, 1.0)

    assert base != Frame({"umidade_ar": 41.0}, 100, 1.0)
    assert base != Frame({"umidade_ar": 40.0}, 102, 1.0)
    assert base != Frame({}, 100, 1.0)
    assert base != Frame({"umidade_ar": 40.0}, None, 1.0)


def test_with_readings_replaces_and_adds_readings_and_keeps_the_rest():
    frame = Frame({"velocidade_vento": 3.2, "umidade_ar": 40.0}, 100, received_at=5.0)

    changed = frame.with_readings({"velocidade_vento": 12.5, "temperatura_ar": 20.0})

    assert dict(changed.readings) == {"velocidade_vento": 12.5, "umidade_ar": 40.0, "temperatura_ar": 20.0}
    assert changed.timestamp == 100 and changed.received_at == 5.0
    assert dict(frame.readings) == {"velocidade_vento": 3.2, "umidade_ar": 40.0}  # the original is untouched


def test_without_readings_drops_the_named_channels():
    frame = Frame({"velocidade_vento": 3.2, "umidade_ar": 40.0}, 100, received_at=5.0)

    assert dict(frame.without_readings({"velocidade_vento"}).readings) == {"umidade_ar": 40.0}
    assert frame.without_readings(set()) == frame


def test_decode_frame_applies_each_channels_scale_and_the_timestamp_scale():
    registers = {channel.address: 10 * (i + 1) for i, channel in enumerate(CHANNELS)}
    registers[TIMESTAMP.address] = 3725

    frame = decode_frame(registers, received_at=7.0)

    assert frame.reading(CHANNELS[0]) == 1.0
    assert frame.reading(CHANNELS[19]) == 20.0
    assert frame.timestamp == 3725
    assert frame.received_at == 7.0


def test_decode_frame_leaves_unread_registers_absent():
    frame = decode_frame({224: 32}, received_at=1.0)

    assert frame.reading(channel_named("velocidade_vento")) == 3.2
    assert frame.reading(channel_named("umidade_ar")) is None
    assert frame.timestamp is None
