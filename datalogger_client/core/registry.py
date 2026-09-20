"""The Channel registry: the one place that ties each Channel's name, label, unit and register together.

`scale` is what the Simulator multiplies a value by before storing it in the
register: a Reading is `raw / scale`, and a value written back is `value * scale`.
"""
from dataclasses import dataclass
from typing import NamedTuple


@dataclass(frozen=True)
class Channel:
    name: str  # canonical, from the alias table in CONTEXT.md
    label: str  # display label
    unit: str
    address: int
    scale: float = 10
    overridable: bool = True

    def decode(self, raw):
        return raw / self.scale

    def encode(self, value):
        return int(round(value * self.scale))


@dataclass(frozen=True)
class TimestampField:
    """The Frame's own Timestamp register (seconds of day). Not a Channel."""

    address: int
    scale: float
    label: str = "Timestamp"
    unit: str = "s"

    def decode(self, raw):
        return int(round(raw / self.scale))


class RegisterBlock(NamedTuple):
    start: int
    count: int

    @property
    def end(self):
        return self.start + self.count - 1

    def contains(self, address):
        return self.start <= address <= self.end


# In Frame order. The last two cannot be overridden (they have no sidebar field today).
CHANNELS = (
    Channel("velocidade_vento", "Vel. vento", "m/s", 224),
    Channel("temperatura_modulo_1", "Temperatura 1", "°C", 226),
    Channel("umidade_ar", "Umidade H.", "%", 228),
    Channel("temperatura_modulo_2", "Temperatura 2", "°C", 230),
    Channel("temperatura_ar", "Temp H.", "°C", 232),
    Channel("radiacao_celula_40m", "Ref Cel 40", "W/m²", 276),
    Channel("teste_celula_40m", "Teste Cel 40", "°C", 501),
    Channel("radiacao_celula_30m", "Ref Cel 30", "W/m²", 280),
    Channel("radiacao_celula_10m", "Ref Cel 10", "W/m²", 284),
    Channel("temperatura_celula_40m", "Ref 40 Temp", "°C", 278),
    Channel("temperatura_celula_30m", "Ref 30 Temp", "°C", 282),
    Channel("temperatura_celula_10m", "Ref 10 Temp", "°C", 286),
    Channel("radiacao_solar_poa_ri2", "POA RI 2", "W/m²", 392),
    Channel("radiacao_solar_poa2", "POA 2", "W/m²", 390),
    Channel("radiacao_solar_poa_ri1", "POA RI 1", "W/m²", 388),
    Channel("radiacao_solar_poa1", "POA 1", "W/m²", 386),
    Channel("radiacao_solar_ghi", "GHI", "W/m²", 384),
    Channel("fault_code", "Fault_code", " ", 5054),
    Channel("Irradiance", "Irradiance", "W/m²", 1, overridable=False),
    Channel("Apparent Power", "Apparent Power", "kVA", 2, overridable=False),
)

TIMESTAMP = TimestampField(address=500, scale=1)

# The contiguous register ranges a Poll reads, one request each.
BLOCKS = (
    RegisterBlock(224, 63),
    RegisterBlock(384, 9),
    RegisterBlock(500, 2),
    RegisterBlock(5054, 1),
    RegisterBlock(1, 2),
)

_CHANNELS_BY_NAME = {channel.name: channel for channel in CHANNELS}


def channel_named(name):
    return _CHANNELS_BY_NAME[name]


def block_containing(address):
    return next(block for block in BLOCKS if block.contains(address))
