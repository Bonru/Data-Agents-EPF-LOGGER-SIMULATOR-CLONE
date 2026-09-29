"""Stand-ins for the Firebase PUT, and a local HTTP server that accepts a request and never answers."""
import socket
import threading


class OkResponse:
    def raise_for_status(self):
        pass


class RecordingPut:
    """A `put` that records every payload it is given and succeeds (or fails with `error`)."""

    def __init__(self, error=None):
        self.payloads = []
        self.error = error

    def __call__(self, url, json, timeout):
        self.payloads.append(json)
        if self.error is not None:
            raise self.error
        return OkResponse()


class HangingPut:
    """A `put` that blocks until `release` is set: a Firebase that never answers."""

    def __init__(self):
        self.release = threading.Event()
        self.started = threading.Event()

    def __call__(self, url, json, timeout):
        self.started.set()
        self.release.wait(30)
        return OkResponse()


class HangingHttpServer:
    """A real local HTTP server that reads a request and never replies (a hung Firebase)."""

    def __init__(self):
        self.requests_received = 0
        self._stopping = threading.Event()
        self._connections = []
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen()
        self._listener.settimeout(0.1)
        self.port = self._listener.getsockname()[1]
        threading.Thread(target=self._accept_loop, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/parametros.json"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._stopping.set()
        for connection in self._connections:
            connection.close()
        self._listener.close()

    def _accept_loop(self):
        while not self._stopping.is_set():
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self._connections.append(connection)
            threading.Thread(target=self._read_and_stay_silent, args=(connection,), daemon=True).start()

    def _read_and_stay_silent(self, connection):
        try:
            if connection.recv(65536):
                self.requests_received += 1
            while not self._stopping.is_set():
                self._stopping.wait(0.1)  # never answer
        except OSError:
            pass
