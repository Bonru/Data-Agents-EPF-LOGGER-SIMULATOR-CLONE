import time

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot

from ..core.backoff import Backoff
from ..core.connection_state import ConnectionStateMachine
from ..core.frame import decode_frame
from ..core.overrides import ManualOverrides
from ..core.registry import BLOCKS, TIMESTAMP, block_containing, channel_named

TIMESTAMP_BLOCK = block_containing(TIMESTAMP.address)
OTHER_BLOCKS = tuple(block for block in BLOCKS if block != TIMESTAMP_BLOCK)
MAX_ATTEMPTS_PER_POLL = 2  # the first read of the Frame, plus one retry
MAX_FAILED_BLOCKS_IN_A_ROW = 2  # then the Simulator is taken as not answering and the Poll gives up


class ModbusWorker(QObject):
    """Owns the Modbus connection and the poll timer; lives on its own QThread.

    The UI talks to it only through queued signals: it never calls these methods.
    """

    frame_ready = pyqtSignal(object)
    connection_state_changed = pyqtSignal(object)
    overrides_changed = pyqtSignal(object)  # frozenset of the overridden Channel names
    stopped = pyqtSignal()

    def __init__(self, transport, interval_ms=500, connection=None, backoff=None, clock=time.monotonic):
        super().__init__()
        self._transport = transport
        self._interval_ms = interval_ms
        self._connection = connection or ConnectionStateMachine()
        self._backoff = backoff or Backoff()
        self._clock = clock
        self._timer = None
        self._last_frame = None  # the last Frame emitted, overrides included
        self._last_raw_frame = None  # the last Frame the Simulator gave, before overrides
        self._overrides = ManualOverrides()
        self._retry_at = float("-inf")  # no Poll before this time (reconnect backoff)

    @pyqtSlot()
    def start(self):
        try:
            print("Abrindo cliente...")
            self._transport.open()
            print("Cliente aberto\n")
        except Exception as e:
            print(f"Unexpected error: {e}")
            print("Fechando cliente...")
            self._transport.close()
            print("Cliente Fechado")
        # Created here so the timer belongs to the worker thread.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.poll)
        self._timer.start(self._interval_ms)
        self.poll()

    @pyqtSlot()
    def stop(self):
        if self._timer is not None:
            self._timer.stop()
        try:
            self._transport.close()
        except Exception as e:
            print(f"Erro ao fechar o cliente: {e}")
        self.stopped.emit()

    @pyqtSlot(str, float)
    def set_override(self, channel_name, value):
        try:
            self._overrides.set(channel_named(channel_name), value)
        except (KeyError, ValueError, OverflowError) as e:
            print(f"Override ignorado para {channel_name}: {e}")
            return
        self.overrides_changed.emit(self._overrides.names())

    @pyqtSlot(str)
    def clear_override(self, channel_name):
        try:
            self._overrides.clear(channel_named(channel_name))
        except KeyError:
            print(f"Override desconhecido: {channel_name}")
            return
        self.overrides_changed.emit(self._overrides.names())

    @pyqtSlot(int, int)
    def write_register(self, address, value):
        self._write(address, value)

    def _write(self, address, value):
        """One register write. Returns whether the Simulator accepted it."""
        try:
            written = self._transport.write_single_register(address, value)
            print(written)
            return bool(written)
        except Exception as e:
            print(f"Erro ao tentar escrever no registrador: {e}")
            return False

    @pyqtSlot()
    def poll(self):
        """Read one Frame and emit it if it differs from the last one emitted.

        A Poll where no block answered emits nothing (the UI keeps the last good values),
        counts towards Disconnected, and delays the next reconnect attempt (backoff).
        """
        now = self._clock()
        if now < self._retry_at:  # backing off after a Poll that got no response
            self._publish_state(self._connection.tick(now))
            return
        try:
            registers = self._read_registers()
            if registers is None:  # interrupted
                return
            now = self._clock()
            if not registers:
                self._retry_at = now + self._backoff.next_delay()
                self._publish_state(self._connection.poll_failed(now))
                return
            self._backoff.reset()
            simulator_frame = decode_frame(registers, received_at=time.time())
            new_frame = self._simulator_advanced(simulator_frame)
            self._last_raw_frame = simulator_frame
            frame = self._overrides.overlay(simulator_frame)
            if frame != self._last_frame:
                self._last_frame = frame
                self.frame_ready.emit(frame)
            self._publish_state(self._connection.poll_answered(now, new_frame))
            self._write_overrides()
        except Exception as e:
            print(f"Erro ao tentar ler os registradores: {e}")

    def _simulator_advanced(self, simulator_frame):
        """Whether the Simulator gave a new Frame. Overridden Channels are left out of the
        comparison: their registers hold what this Client wrote, not what the Simulator produced,
        so setting an override must not make a stalled Simulator look alive."""
        if self._last_raw_frame is None:
            return True
        overridden = self._overrides.names()
        return simulator_frame.without_readings(overridden) != self._last_raw_frame.without_readings(overridden)

    def _write_overrides(self):
        """Re-assert every override on the Simulator: one write each, per Poll.

        Stops at the first failed write, or when a stop was requested: a Simulator that
        answers reads but not writes would otherwise cost a full timeout per override,
        and a stop request would wait behind all of them.
        """
        for address, raw in self._overrides.register_writes():
            if QThread.currentThread().isInterruptionRequested():
                return
            if not self._write(address, raw):
                return

    def _publish_state(self, changed):
        if changed:
            self.connection_state_changed.emit(self._connection.state)

    def _read_registers(self):
        """Read every block, guarding against a Frame torn by a Simulator tick mid-Poll.

        The Timestamp block is read first and again last; if the Timestamp moved in
        between, the Simulator ticked during the Poll, so the attempt is discarded and
        made once more. Returns address -> raw value for the registers that could be read
        (empty if none could), or None if a stop was requested.
        """
        for _ in range(MAX_ATTEMPTS_PER_POLL):
            attempt = self._read_attempt()
            if attempt is None:
                return None
            registers, torn = attempt
            if not torn:
                break
        return registers

    def _read_attempt(self):
        """The five blocks, then the Timestamp block again: (registers, whether the Frame was torn).

        Gives up early, not torn, once several block reads in a row fail: a dead or hung
        Simulator would otherwise cost a full timeout for every block of every Poll.
        Returns None if a stop was requested.
        """
        registers = {}
        failed_in_a_row = 0
        for block in (TIMESTAMP_BLOCK, *OTHER_BLOCKS):
            values = self._read_block(block)
            if values is None:
                return None
            registers.update(values)
            failed_in_a_row = 0 if values else failed_in_a_row + 1
            if failed_in_a_row >= MAX_FAILED_BLOCKS_IN_A_ROW:
                return registers, False
        values_at_end = self._read_block(TIMESTAMP_BLOCK)
        if values_at_end is None:
            return None
        torn = values_at_end.get(TIMESTAMP.address) != registers.get(TIMESTAMP.address)
        return registers, torn

    def _read_block(self, block):
        """One block request. Returns address -> raw value, empty if the read failed
        (those registers get no Reading), or None if a stop was requested.
        """
        # A hung Simulator makes each read wait for the transport timeout;
        # give up between reads so a stop request is not stuck behind them.
        if QThread.currentThread().isInterruptionRequested():
            return None
        try:
            values = self._transport.read_holding_registers(block.start, block.count)
        except Exception as e:
            print(f"Erro ao ler os registradores {block.start}-{block.end}: {e}")
            values = None
        if not values or len(values) != block.count:
            print(f"Falha ao ler os registradores {block.start}-{block.end}")
            return {}
        return {block.start + offset: value for offset, value in enumerate(values)}
