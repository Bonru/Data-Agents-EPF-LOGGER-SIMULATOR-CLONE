import time

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot

from ..core.frame import decode_frame
from ..core.registry import BLOCKS, TIMESTAMP, block_containing

TIMESTAMP_BLOCK = block_containing(TIMESTAMP.address)
OTHER_BLOCKS = tuple(block for block in BLOCKS if block != TIMESTAMP_BLOCK)
MAX_ATTEMPTS_PER_POLL = 2  # the first read of the Frame, plus one retry


class ModbusWorker(QObject):
    """Owns the Modbus connection and the poll timer; lives on its own QThread.

    The UI talks to it only through queued signals: it never calls these methods.
    """

    frame_ready = pyqtSignal(object)
    stopped = pyqtSignal()

    def __init__(self, transport, interval_ms=500):
        super().__init__()
        self._transport = transport
        self._interval_ms = interval_ms
        self._timer = None
        self._last_frame = None

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

    @pyqtSlot(int, int)
    def write_register(self, address, value):
        try:
            print(self._transport.write_single_register(address, value))
        except Exception as e:
            print(f"Erro ao tentar escrever no registrador: {e}")

    @pyqtSlot()
    def poll(self):
        """Read one Frame and emit it if it differs from the last one emitted."""
        try:
            registers = self._read_registers()
            if registers is None:  # interrupted
                return
            frame = decode_frame(registers, received_at=time.time())
            if frame != self._last_frame:
                self._last_frame = frame
                self.frame_ready.emit(frame)
        except Exception as e:
            print(f"Erro ao tentar ler os registradores: {e}")

    def _read_registers(self):
        """Read every block, guarding against a Frame torn by a Simulator tick mid-Poll.

        The Timestamp block is read first and again last; if the Timestamp moved in
        between, the Simulator ticked during the Poll, so the attempt is discarded and
        made once more. Returns address -> raw value, or None if a stop was requested.
        """
        for _ in range(MAX_ATTEMPTS_PER_POLL):
            attempt = self._read_attempt()
            if attempt is None:
                return None
            registers, timestamp_at_end = attempt
            if timestamp_at_end == registers[TIMESTAMP.address]:
                break
        return registers

    def _read_attempt(self):
        """The five blocks, then the Timestamp block again: (registers, raw Timestamp at the end)."""
        registers = {}
        for block in (TIMESTAMP_BLOCK, *OTHER_BLOCKS):
            values = self._read_block(block)
            if values is None:
                return None
            registers.update(values)
        values_at_end = self._read_block(TIMESTAMP_BLOCK)
        if values_at_end is None:
            return None
        return registers, values_at_end[TIMESTAMP.address]

    def _read_block(self, block):
        """One block request. Returns address -> raw value; None if a stop was requested.

        A failed read yields zeros, as the old Client did (#7 replaces this).
        """
        # A hung Simulator makes each read wait for the transport timeout;
        # give up between reads so a stop request is not stuck behind them.
        if QThread.currentThread().isInterruptionRequested():
            return None
        values = self._transport.read_holding_registers(block.start, block.count)
        if not values or len(values) != block.count:
            print(f"Falha ao ler os registradores {block.start}-{block.end}")
            values = [0] * block.count
        return {block.start + offset: value for offset, value in enumerate(values)}
