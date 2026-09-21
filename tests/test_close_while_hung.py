"""Closing the window while the Simulator is hung must end the process quickly and cleanly."""
import os
import subprocess
import sys
import time
from pathlib import Path


from tests.support.firebase_stub import HangingHttpServer
from tests.support.modbus_server import FakeModbusServer

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_SECONDS_AFTER_CLOSE = 5


def run_window_process(*args):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    process = subprocess.run(
        [sys.executable, "-m", "tests.support.window_process", *args],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=30,
    )
    ended = time.time()
    closing_lines = [line for line in process.stdout.splitlines() if line.startswith("CLOSING ")]
    assert closing_lines, f"the window never closed:\n{process.stdout}\n{process.stderr}"
    seconds_after_close = ended - float(closing_lines[0].split()[1])
    return process, seconds_after_close


def assert_clean_exit(process, seconds_after_close):
    assert process.returncode == 0, process.stderr
    assert seconds_after_close < MAX_SECONDS_AFTER_CLOSE
    assert "Destroyed while thread is still running" not in process.stderr


def test_closing_with_a_hung_simulator_ends_the_process_quickly():
    with FakeModbusServer() as server:
        server.mode = "hang"
        process, seconds = run_window_process("modbus", str(server.port))
    assert_clean_exit(process, seconds)


def test_closing_ends_the_process_even_if_a_modbus_call_never_returns():
    process, seconds = run_window_process("blocked")
    assert_clean_exit(process, seconds)


def test_closing_ends_the_process_quickly_even_if_a_firebase_upload_is_hanging():
    with HangingHttpServer() as firebase:
        process, seconds = run_window_process("firebase-hang", str(firebase.port))
        uploads_started = firebase.requests_received

    assert uploads_started >= 1  # an upload really was in flight (and never answered) when the window closed
    assert_clean_exit(process, seconds)
