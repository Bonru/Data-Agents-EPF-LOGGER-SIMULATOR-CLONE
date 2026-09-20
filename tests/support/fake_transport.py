import threading


class FakeTransport:
    """A Transport that records every call with the thread it was made on.

    `block` (a threading.Event) makes every read wait until it is set, to
    simulate a call that never returns. `on_read(transport, address, count)`,
    if given, runs before each read is answered, so a test can change registers
    in the middle of a Poll. `failing_addresses` are block start addresses whose
    reads fail (return None).
    """

    def __init__(self, registers=None, block=None, on_read=None, failing_addresses=()):
        self.registers = dict(registers or {})
        self.calls = []  # (name, args, thread ident)
        self.block = block
        self.on_read = on_read
        self.failing_addresses = set(failing_addresses)

    def _record(self, name, *args):
        self.calls.append((name, args, threading.get_ident()))

    def calls_named(self, name):
        return [args for call_name, args, _ in self.calls if call_name == name]

    def open(self):
        self._record("open")
        return True

    def close(self):
        self._record("close")

    def read_holding_registers(self, address, count=1):
        self._record("read", address, count)
        if self.block is not None:
            self.block.wait()
        if self.on_read is not None:
            self.on_read(self, address, count)
        if address in self.failing_addresses:
            return None
        return [self.registers.get(address + i, 0) for i in range(count)]

    def write_single_register(self, address, value):
        self._record("write", address, value)
        self.registers[address] = value
        return True


class TickingFakeTransport(FakeTransport):
    """A FakeTransport whose Timestamp advances by 2 s at the start of every Poll, like the Simulator.

    A Poll starts with a read of the Timestamp block, and the previous Poll ended with one, so
    two Timestamp-block reads in a row mean a new Poll began. The Timestamp never moves inside a Poll.
    """

    def __init__(self, registers=None, **kwargs):
        super().__init__({500: 0, **(registers or {})}, **kwargs)
        self._previous_address = None

    def read_holding_registers(self, address, count=1):
        if address == 500 and self._previous_address == 500:
            self.registers[500] += 2
        self._previous_address = address
        return super().read_holding_registers(address, count)
