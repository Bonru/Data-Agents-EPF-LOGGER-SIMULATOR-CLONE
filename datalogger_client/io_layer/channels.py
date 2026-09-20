from typing import NamedTuple


class Channel(NamedTuple):
    address: int
    label: str
    unit: str


# Every register the Client polls, in display order. The first 19 can be
# overridden from the manual-insertion sidebar; the last two (Irradiance and
# Apparent Power) cannot.
CHANNELS = (
    Channel(224, "Vel. vento", "m/s"),
    Channel(226, "Temperatura 1", "°C"),
    Channel(228, "Umidade H.", "%"),
    Channel(230, "Temperatura 2", "°C"),
    Channel(232, "Temp H.", "°C"),
    Channel(276, "Ref Cel 40", "W/m²"),
    Channel(501, "Teste Cel 40", "°C"),
    Channel(280, "Ref Cel 30", "W/m²"),
    Channel(284, "Ref Cel 10", "W/m²"),
    Channel(278, "Ref 40 Temp", "°C"),
    Channel(282, "Ref 30 Temp", "°C"),
    Channel(286, "Ref 10 Temp", "°C"),
    Channel(392, "POA RI 2", "W/m²"),
    Channel(390, "POA 2", "W/m²"),
    Channel(388, "POA RI 1", "W/m²"),
    Channel(386, "POA 1", "W/m²"),
    Channel(384, "GHI", "W/m²"),
    Channel(500, "Timestamp", "s"),
    Channel(5054, "Fault_code", " "),
    Channel(1, "Irradiance", "W/m²"),
    Channel(2, "Apparent Power", "kVA"),
)

TIMESTAMP_LABEL = "Timestamp"
OVERRIDABLE_CHANNELS = CHANNELS[:19]

# The Simulator stores every value multiplied by this factor.
REGISTER_SCALE = 10
