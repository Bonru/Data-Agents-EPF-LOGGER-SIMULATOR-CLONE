"""The Channel registry. Pure Python: no Qt anywhere in these tests."""
from datalogger_client.core.registry import BLOCKS, CHANNELS, TIMESTAMP, block_containing, channel_named

# Canonical names, in registry order, from the alias table in CONTEXT.md.
ALIAS_TABLE_NAMES = [
    "velocidade_vento", "temperatura_modulo_1", "umidade_ar", "temperatura_modulo_2", "temperatura_ar",
    "radiacao_celula_40m", "teste_celula_40m", "radiacao_celula_30m", "radiacao_celula_10m",
    "temperatura_celula_40m", "temperatura_celula_30m", "temperatura_celula_10m",
    "radiacao_solar_poa_ri2", "radiacao_solar_poa2", "radiacao_solar_poa_ri1", "radiacao_solar_poa1",
    "radiacao_solar_ghi", "fault_code", "Irradiance", "Apparent Power",
]

# What the old list-position pairing (the Client's `addresses` and `parametros` lists,
# minus their Timestamp entry) produced: (address, label, unit).
OLD_PAIRING = [
    (224, "Vel. vento", "m/s"),
    (226, "Temperatura 1", "°C"),
    (228, "Umidade H.", "%"),
    (230, "Temperatura 2", "°C"),
    (232, "Temp H.", "°C"),
    (276, "Ref Cel 40", "W/m²"),
    (501, "Teste Cel 40", "°C"),
    (280, "Ref Cel 30", "W/m²"),
    (284, "Ref Cel 10", "W/m²"),
    (278, "Ref 40 Temp", "°C"),
    (282, "Ref 30 Temp", "°C"),
    (286, "Ref 10 Temp", "°C"),
    (392, "POA RI 2", "W/m²"),
    (390, "POA 2", "W/m²"),
    (388, "POA RI 1", "W/m²"),
    (386, "POA 1", "W/m²"),
    (384, "GHI", "W/m²"),
    (5054, "Fault_code", " "),
    (1, "Irradiance", "W/m²"),
    (2, "Apparent Power", "kVA"),
]


def test_there_are_twenty_channels():
    assert len(CHANNELS) == 20


def test_canonical_names_match_the_alias_table():
    assert [channel.name for channel in CHANNELS] == ALIAS_TABLE_NAMES


def test_label_unit_and_address_equal_the_old_list_position_pairing():
    assert [(c.address, c.label, c.unit) for c in CHANNELS] == OLD_PAIRING


def test_the_timestamp_is_not_a_channel():
    assert TIMESTAMP.address == 500
    assert all(channel.address != TIMESTAMP.address for channel in CHANNELS)
    assert all(channel.name != "Timestamp" and channel.label != "Timestamp" for channel in CHANNELS)


def test_the_scales_are_ten_for_measurements_and_one_for_the_fault_code():
    assert {channel.scale for channel in CHANNELS if channel.name != "fault_code"} == {10}
    assert channel_named("fault_code").scale == 1  # a protocol value, an unscaled integer
    assert TIMESTAMP.seconds_per_register == 2  # its register holds half the seconds of day


def test_channel_decoding_and_encoding_use_the_scale():
    wind = channel_named("velocidade_vento")
    assert wind.decode(32) == 3.2
    assert wind.encode(3.2) == 32
    assert wind.encode(12) == 120


def test_the_timestamp_decodes_to_seconds_of_day():
    assert TIMESTAMP.decode(3725) == 7450  # the register holds the seconds of day divided by two


def test_every_channel_is_overridable():
    assert all(channel.overridable for channel in CHANNELS)


def test_names_are_unique_and_lookup_by_name_works():
    assert len({channel.name for channel in CHANNELS}) == len(CHANNELS)
    assert channel_named("radiacao_celula_40m").label == "Ref Cel 40"


def test_the_five_blocks_cover_every_register_exactly_once():
    assert [(block.start, block.end) for block in BLOCKS] == [(224, 286), (384, 392), (500, 501), (5054, 5054), (1, 2)]
    for address in [channel.address for channel in CHANNELS] + [TIMESTAMP.address]:
        assert len([block for block in BLOCKS if block.contains(address)]) == 1
    assert block_containing(TIMESTAMP.address) == (500, 2)
