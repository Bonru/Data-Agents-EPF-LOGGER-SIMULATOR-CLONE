"""Manual override: validation, the overlay on a Frame, and the register writes. Pure Python: no Qt."""
import pytest

from datalogger_client.core.frame import Frame
from datalogger_client.core.overrides import InvalidOverride, ManualOverrides, parse_override
from datalogger_client.core.registry import CHANNELS, Channel, channel_named

WIND = channel_named("velocidade_vento")  # register 224, scale 10
HUMIDITY = channel_named("umidade_ar")  # register 228, scale 10
UNSCALED = Channel("contador", "Contador", " ", 4000, scale=1)  # like the fault code will be after #16


def make_frame(**readings):
    return Frame(readings, 3600, received_at=1.0)


# --- validation: one decimal place, 0 to 6553.5 (unsigned 16-bit register, x10 scale) ---------------


@pytest.mark.parametrize("text, expected", [("12.5", 12.5), ("0", 0.0), ("6553.5", 6553.5), ("7", 7.0), ("0.0", 0.0), (" 12.5 ", 12.5)])
def test_valid_override_text_is_accepted(text, expected):
    assert parse_override(WIND, text) == expected


@pytest.mark.parametrize("text", ["-1", "6553.6", "abc", "12.55", "", "   ", ".5", "5.", "1e2", "12,5", "+3", "--1", "6554", "99999"])
def test_invalid_override_text_is_rejected(text):
    with pytest.raises(InvalidOverride):
        parse_override(WIND, text)


def test_the_rejection_carries_a_message_for_the_inline_display():
    with pytest.raises(InvalidOverride) as error:
        parse_override(WIND, "6553.6")

    assert str(error.value) == "Use 0 a 6553.5 (1 casa decimal)"


def test_the_accepted_range_and_decimals_follow_the_channels_scale():
    assert parse_override(UNSCALED, "65535") == 65535.0
    assert parse_override(UNSCALED, "0") == 0.0
    for text in ("65536", "1.5", "-1"):
        with pytest.raises(InvalidOverride):
            parse_override(UNSCALED, text)


def test_the_message_for_an_unscaled_channel_asks_for_an_integer():
    with pytest.raises(InvalidOverride) as error:
        parse_override(UNSCALED, "1.5")

    assert str(error.value) == "Use 0 a 65535 (inteiro)"


def test_every_registered_channel_accepts_its_own_maximum():
    for channel in CHANNELS:
        maximum = 65535 / channel.scale
        assert channel.encode(parse_override(channel, f"{maximum:g}")) == 65535


# --- the override set ---------------------------------------------------------------------------


def test_it_starts_with_no_overrides():
    overrides = ManualOverrides()

    assert overrides.names() == frozenset()
    assert overrides.register_writes() == []


def test_setting_and_clearing_an_override_changes_the_names():
    overrides = ManualOverrides()

    overrides.set(WIND, 12.5)
    overrides.set(HUMIDITY, 40.0)
    assert overrides.names() == {WIND.name, HUMIDITY.name}

    overrides.clear(WIND)
    assert overrides.names() == {HUMIDITY.name}


def test_clearing_a_channel_that_has_no_override_is_harmless():
    overrides = ManualOverrides()

    overrides.clear(WIND)

    assert overrides.names() == frozenset()


def test_setting_again_replaces_the_value():
    overrides = ManualOverrides()
    overrides.set(WIND, 12.5)

    overrides.set(WIND, 3.0)

    assert overrides.register_writes() == [(224, 30)]


def test_there_is_one_register_write_per_override_with_the_value_times_the_scale():
    overrides = ManualOverrides()
    overrides.set(WIND, 12.5)
    overrides.set(HUMIDITY, 0.0)
    overrides.set(UNSCALED, 7.0)

    assert overrides.register_writes() == [(224, 125), (228, 0), (4000, 7)]


# --- the overlay on a Frame ---------------------------------------------------------------------


def test_the_overlay_replaces_the_overridden_readings_and_leaves_the_rest():
    overrides = ManualOverrides()
    overrides.set(WIND, 12.5)
    frame = make_frame(velocidade_vento=3.2, umidade_ar=41.0)

    overlaid = overrides.overlay(frame)

    assert overlaid.reading(WIND) == 12.5
    assert overlaid.reading(HUMIDITY) == 41.0
    assert overlaid.timestamp == 3600
    assert overlaid.received_at == 1.0


def test_the_overlay_shows_the_override_even_where_the_channel_had_no_reading():
    overrides = ManualOverrides()
    overrides.set(WIND, 12.5)

    overlaid = overrides.overlay(make_frame(umidade_ar=41.0))  # a Partial Frame without the wind Reading

    assert overlaid.reading(WIND) == 12.5


def test_the_overlay_does_not_touch_the_original_frame():
    overrides = ManualOverrides()
    overrides.set(WIND, 12.5)
    frame = make_frame(velocidade_vento=3.2)

    overrides.overlay(frame)

    assert frame.reading(WIND) == 3.2


def test_without_overrides_the_overlay_is_the_same_frame():
    frame = make_frame(velocidade_vento=3.2)

    assert ManualOverrides().overlay(frame) == frame


def test_the_overlaid_reading_is_what_the_register_will_hold():
    overrides = ManualOverrides()
    overrides.set(WIND, 12.5)

    assert overrides.overlay(make_frame()).reading(WIND) == WIND.decode(dict(overrides.register_writes())[WIND.address])


def test_a_cleared_override_shows_the_simulators_value_again():
    overrides = ManualOverrides()
    overrides.set(WIND, 12.5)
    overrides.clear(WIND)

    assert overrides.overlay(make_frame(velocidade_vento=3.2)).reading(WIND) == 3.2
