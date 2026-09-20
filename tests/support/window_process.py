"""Runs the real window in its own process and closes it after a moment.

Usage: python -m tests.support.window_process <modbus|blocked> [port]

Prints "CLOSING <wall clock time>" right before closing the window, so the
parent test can measure how long the process takes to end after that.
"""
import os
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from datalogger_client.io_layer.transport import ModbusTcpTransport
from datalogger_client.ui.app import run_event_loop
from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import FakeTransport

CLOSE_AFTER_MS = 800


def main():
    kind = sys.argv[1]
    if kind == "modbus":
        transport = ModbusTcpTransport("127.0.0.1", int(sys.argv[2]))  # default timeout, as in the app
    else:
        transport = FakeTransport(block=threading.Event())  # every read blocks forever

    app = QApplication([])
    window = MainWindow(transport, poll_interval_ms=100, submit_firebase=lambda payload: None)
    window.show()

    def close():
        print(f"CLOSING {time.time()}", flush=True)
        window.close()

    QTimer.singleShot(CLOSE_AFTER_MS, close)
    sys.exit(run_event_loop(app, window))


if __name__ == "__main__":
    main()
