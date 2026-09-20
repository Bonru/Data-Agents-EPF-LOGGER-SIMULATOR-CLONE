import threading


class FakeTransport:
    """A Transport that records every call with the thread it was made on.

    `block` (a threading.Event) makes every read wait until it is set, to
    simulate a call that never returns.
    """

    def __init__(self, registers=None, block=None):
        self.registers = dict(registers or {})
        self.calls = []  # (name, args, thread ident)
        self.block = block

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
        return [self.registers.get(address, 0)]

    def write_single_register(self, address, value):
        self._record("write", address, value)
        self.registers[address] = value
        return True
