"""A minimal Modbus TCP server for tests that can misbehave on demand.

Supports function 3 (read holding registers) and 6 (write single register).
`mode` switches how it answers: "normal", "slow" (waits `delay` seconds before
each reply), "hang" (reads requests and never answers) or "drop" (closes every
connection as soon as a request arrives, so every request fails). `drop_connections()`
closes every open client connection once; `stop()` shuts the server down entirely,
which makes the port refuse connections.

A read that covers a register whose value does not fit in 16 bits (like the real
Simulator's Timestamp after about 13 minutes) makes the server drop the connection,
as the real pyModbusTCP server does; the client reconnects on its next request.
"""
import socket
import struct
import threading


class FakeModbusServer:
    def __init__(self, registers=None):
        self.registers = dict(registers or {})
        self.writes = []  # (address, value) in arrival order
        self.reads = []  # (address, count) in arrival order
        self.mode = "normal"
        self.delay = 0.0
        self._stopping = threading.Event()
        self._connections = []
        self._lock = threading.Lock()
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen()
        self._listener.settimeout(0.1)
        self.port = self._listener.getsockname()[1]
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()

    def run_simulator(self, values, interval=0.15, timestamp_step=2):
        """Behave like the Simulator: every `interval` seconds overwrite the registers with
        `values` (address -> raw) and advance the Timestamp (register 500) by `timestamp_step`."""
        threading.Thread(target=self._simulate, args=(dict(values), interval, timestamp_step), daemon=True).start()

    def _simulate(self, values, interval, timestamp_step):
        timestamp = values.get(500, 0)
        while not self._stopping.is_set():
            timestamp += timestamp_step
            self.registers.update(values)
            self.registers[500] = timestamp
            self._stopping.wait(interval)

    def drop_connections(self):
        with self._lock:
            connections, self._connections = self._connections, []
        for connection in connections:
            _close_quietly(connection)

    def stop(self):
        self._stopping.set()
        self.drop_connections()
        _close_quietly(self._listener)

    def _accept_loop(self):
        while not self._stopping.is_set():
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with self._lock:
                self._connections.append(connection)
            threading.Thread(target=self._serve, args=(connection,), daemon=True).start()

    def _serve(self, connection):
        try:
            while not self._stopping.is_set():
                header = _recv_exactly(connection, 7)
                transaction, protocol, length, unit = struct.unpack(">HHHB", header)
                pdu = _recv_exactly(connection, length - 1)
                if not self._wait_before_reply():
                    return
                reply = self._handle(pdu)
                if reply is None:
                    return  # no reply: the connection is closed below
                connection.sendall(struct.pack(">HHHB", transaction, protocol, len(reply) + 1, unit) + reply)
        except (OSError, ConnectionError):
            pass
        finally:
            _close_quietly(connection)

    def _wait_before_reply(self):
        """Returns False if the connection should be closed without a reply (server stopped, or "drop" mode)."""
        if self.mode == "drop":
            return False
        if self.mode == "hang":
            while self.mode == "hang":
                if self._stopping.wait(0.05):
                    return False
        elif self.mode == "slow":
            return not self._stopping.wait(self.delay)
        return True

    def _handle(self, pdu):
        function = pdu[0]
        if function == 3:
            address, count = struct.unpack(">HH", pdu[1:5])
            self.reads.append((address, count))
            values = [self.registers.get(address + i, 0) for i in range(count)]
            if any(not 0 <= value <= 0xFFFF for value in values):
                return None
            packed = b"".join(struct.pack(">H", value) for value in values)
            return bytes([3, len(packed)]) + packed
        if function == 6:
            address, value = struct.unpack(">HH", pdu[1:5])
            self.registers[address] = value
            self.writes.append((address, value))
            return pdu
        return bytes([function | 0x80, 1])  # illegal function


def _recv_exactly(connection, size):
    data = b""
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionError("closed")
        data += chunk
    return data


def _close_quietly(sock):
    try:
        sock.close()
    except OSError:
        pass
