"""Runs the real window in its own process and closes it after a moment.

Usage: python -m tests.support.window_process <modbus|blocked|firebase-hang> [port]

  modbus         a real Modbus transport to 127.0.0.1:<port>
  blocked        a transport whose every read blocks forever
  firebase-hang  a working transport whose Frames are uploaded to a Firebase at 127.0.0.1:<port>
                 that never answers

Firebase uploads are off except in firebase-hang (a child process is not covered by the test
suite's guard against reaching the real database).

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

from datalogger_client.io_layer.firebase_sender import FIREBASE_TIMEOUT_S, FirebaseSender
from datalogger_client.io_layer.transport import ModbusTcpTransport
from datalogger_client.ui.app import run_event_loop
from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import FakeTransport, TickingFakeTransport

CLOSE_AFTER_MS = 800


def main():
    kind = sys.argv[1]
    firebase = None
    if kind == "modbus":
        transport = ModbusTcpTransport("127.0.0.1", int(sys.argv[2]))  # default timeout, as in the app
    elif kind == "firebase-hang":
        transport = TickingFakeTransport()  # a new Frame on every Poll, so uploads start at once
        firebase = FirebaseSender(url=f"http://127.0.0.1:{sys.argv[2]}/parametros.json", timeout=FIREBASE_TIMEOUT_S)
    else:
        transport = FakeTransport(block=threading.Event())  # every read blocks forever

    app = QApplication([])
    window = MainWindow(transport, poll_interval_ms=100, firebase=firebase, firebase_enabled=firebase is not None)
    window.show()

    def close():
        print(f"CLOSING {time.time()}", flush=True)
        window.close()

    QTimer.singleShot(CLOSE_AFTER_MS, close)
    sys.exit(run_event_loop(app, window))


if __name__ == "__main__":
    main()
