from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot

from .channels import CHANNELS, REGISTER_SCALE, TIMESTAMP_LABEL
from .snapshot import ChannelEntry, Snapshot


class ModbusWorker(QObject):
    """Owns the Modbus connection and the poll timer; lives on its own QThread.

    The UI talks to it only through queued signals: it never calls these methods.
    """

    snapshot_ready = pyqtSignal(object)
    stopped = pyqtSignal()

    def __init__(self, transport, interval_ms=2000, channels=CHANNELS):
        super().__init__()
        self._transport = transport
        self._interval_ms = interval_ms
        self._channels = channels
        self._timer = None

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
        try:
            raw_values = []
            for channel in self._channels:
                # A hung Simulator makes each read wait for the transport timeout;
                # give up between reads so a stop request is not stuck behind them.
                if QThread.currentThread().isInterruptionRequested():
                    return
                value = self._transport.read_holding_registers(channel.address, 1)
                if value:
                    raw_values.append(value[0])
                else:
                    raw_values.append(0)  # kept from the old Client; #7 replaces it
                    print("Falha ao ler o registrador", channel.address)
            self.snapshot_ready.emit(self._build_snapshot(raw_values))
        except Exception as e:
            print(f"Erro ao tentar ler os registradores: {e}")

    def _build_snapshot(self, raw_values):
        entries = tuple(
            ChannelEntry(raw / REGISTER_SCALE, channel.label, channel.unit)
            for channel, raw in zip(self._channels, raw_values)
        )
        timestamp = next(
            raw for channel, raw in zip(self._channels, raw_values) if channel.label == TIMESTAMP_LABEL
        )
        return Snapshot(entries, timestamp)
