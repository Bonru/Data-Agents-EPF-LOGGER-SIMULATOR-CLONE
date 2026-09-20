from typing import Optional, Protocol

from pyModbusTCP.client import ModbusClient

REQUEST_TIMEOUT_S = 2.0  # for every request, connecting included


class Transport(Protocol):
    """The only way the worker touches Modbus, so tests can substitute a fake."""

    def open(self) -> bool: ...

    def close(self) -> None: ...

    def read_holding_registers(self, address: int, count: int = 1) -> Optional[list[int]]: ...

    def write_single_register(self, address: int, value: int) -> bool: ...


class ModbusTcpTransport:
    def __init__(self, host="localhost", port=8080, timeout=REQUEST_TIMEOUT_S):
        # auto_open makes every call reconnect, so a Simulator started late is picked up.
        self._client = ModbusClient(host=host, port=port, timeout=timeout)

    def open(self):
        return self._client.open()

    def close(self):
        self._client.close()

    def read_holding_registers(self, address, count=1):
        return self._client.read_holding_registers(address, count)

    def write_single_register(self, address, value):
        return self._client.write_single_register(address, value)
