"""The Firebase sender: payload, the latest-Frame slot, upload status, and no shared mutable state."""
import json
import threading
from pathlib import Path

import pytest
import requests
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal

from datalogger_client.core.frame import Frame
from datalogger_client.core.registry import CHANNELS
from datalogger_client.io_layer import firebase_sender
from datalogger_client.io_layer.firebase_sender import (
    FIREBASE_TIMEOUT_S,
    FIREBASE_URL,
    FirebaseSender,
    build_firebase_payload,
)
from tests.support.firebase_stub import OkResponse
from tests.support.heartbeat import run_until

SENDER_SOURCE = Path(firebase_sender.__file__)

# The payload shape and order the web view was built against: display label and unit, in registry order.
EXPECTED_NAMES_AND_UNITS = [
    ("Vel. vento", "m/s"), ("Temperatura 1", "°C"), ("Umidade H.", "%"), ("Temperatura 2", "°C"),
    ("Temp H.", "°C"), ("Ref Cel 40", "W/m²"), ("Teste Cel 40", "°C"), ("Ref Cel 30", "W/m²"),
    ("Ref Cel 10", "W/m²"), ("Ref 40 Temp", "°C"), ("Ref 30 Temp", "°C"), ("Ref 10 Temp", "°C"),
    ("POA RI 2", "W/m²"), ("POA 2", "W/m²"), ("POA RI 1", "W/m²"), ("POA 1", "W/m²"),
    ("GHI", "W/m²"), ("Fault_code", " "), ("Irradiance", "W/m²"), ("Apparent Power", "kVA"),
]


def make_frame(marker=1.0, missing=()):
    readings = {c.name: marker for c in CHANNELS if c.name not in missing}
    return Frame(readings, 3600, received_at=0.0)


# --- the payload --------------------------------------------------------------------------------------


def test_the_payload_has_the_same_shape_and_order_as_before():
    payload = build_firebase_payload(make_frame(1.5))

    assert [(item["name"], item["unit"]) for item in payload] == EXPECTED_NAMES_AND_UNITS
    assert all(list(item) == ["name", "value", "unit"] for item in payload)
    assert all(item["value"] == 1.5 for item in payload)


def test_a_channel_without_a_reading_is_sent_as_null():
    payload = build_firebase_payload(make_frame(2.0, missing={"velocidade_vento", "teste_celula_40m"}))

    by_name = {item["name"]: item["value"] for item in payload}
    assert by_name["Vel. vento"] is None and by_name["Teste Cel 40"] is None
    assert by_name["Umidade H."] == 2.0
    assert '"value": null' in json.dumps(payload)  # what the web view receives


def test_the_payload_is_json_serialisable():
    json.dumps(build_firebase_payload(make_frame()))


def test_the_configuration_is_the_existing_database_node_with_a_ten_second_timeout():
    assert FIREBASE_URL == "https://monitoramento-usf-default-rtdb.firebaseio.com/parametros.json"
    assert FIREBASE_TIMEOUT_S == 10
    assert firebase_sender.FIREBASE_ENABLED in (True, False)  # the on/off switch


# --- a sender running on its own thread ----------------------------------------------------------------


class Feeder(QObject):
    """Stands in for the worker: emits Frames to the sender through a queued signal."""

    frame = pyqtSignal(object)


class SenderRig:
    """A sender on its own QThread, with a stub in place of the HTTP PUT."""

    def __init__(self, put):
        self.puts = []  # (url, payload, timeout, thread ident) of every PUT that finished or is running
        self.results = []  # what the sender reported after each upload
        self.put_threads = set()
        self._put = put
        self.sender = FirebaseSender(put=self._recording_put)
        self.thread = QThread()
        self.sender.moveToThread(self.thread)
        self.feeder = Feeder()
        self.feeder.frame.connect(self.sender.submit, Qt.ConnectionType.QueuedConnection)
        self.sender.upload_finished.connect(self.results.append, Qt.ConnectionType.DirectConnection)
        self.thread.start()

    def _recording_put(self, url, json, timeout):
        self.put_threads.add(threading.get_ident())
        self.puts.append((url, json, timeout))
        return self._put(url, json, timeout)

    def send(self, frame):
        self.feeder.frame.emit(frame)

    def markers(self):
        """The reading of the first Channel in each payload sent, in order."""
        return [payload[0]["value"] for _, payload, _ in self.puts]

    def stop(self):
        self.thread.quit()
        self.thread.wait(3000)


@pytest.fixture
def rig(qapp):
    made = []

    def make(put=lambda url, json, timeout: OkResponse()):
        made.append(SenderRig(put))
        return made[-1]

    yield make
    for each in made:
        each.stop()


def test_a_frame_is_put_to_the_database_node_with_the_timeout(rig):
    sending = rig()

    sending.send(make_frame(7.0))

    assert run_until(lambda: sending.puts)
    url, payload, timeout = sending.puts[0]
    assert url == FIREBASE_URL and timeout == 10
    assert payload == build_firebase_payload(make_frame(7.0))


def test_the_upload_happens_on_the_sender_thread_not_the_caller(rig):
    sending = rig()

    sending.send(make_frame())

    assert run_until(lambda: sending.puts)
    assert threading.get_ident() not in sending.put_threads
    assert len(sending.put_threads) == 1


def test_with_a_slow_sender_intermediate_frames_are_dropped_and_the_newest_is_sent(rig):
    release = threading.Event()
    slow = rig(put=lambda url, json, timeout: (release.wait(5), OkResponse())[1])

    slow.send(make_frame(1.0))
    assert run_until(lambda: len(slow.puts) == 1)  # the first upload is in flight (blocked)
    for marker in (2.0, 3.0, 4.0, 5.0):
        slow.send(make_frame(marker))  # they arrive while it is still uploading
    release.set()

    assert run_until(lambda: len(slow.puts) == 2)
    assert run_until(lambda: len(slow.results) == 2)
    assert slow.markers() == [1.0, 5.0]  # 2, 3 and 4 were dropped: only the newest went out


def test_frames_that_arrive_one_at_a_time_are_each_sent_once(rig):
    sending = rig()

    for marker in (1.0, 2.0, 3.0):
        sending.send(make_frame(marker))
        assert run_until(lambda n=int(marker): len(sending.puts) == n)

    assert sending.markers() == [1.0, 2.0, 3.0]


def test_a_successful_upload_reports_ok(rig):
    sending = rig()

    sending.send(make_frame())

    assert run_until(lambda: sending.results == [True])


def test_a_failed_upload_reports_failing_and_the_next_success_recovers(rig):
    outcome = {"fail": True}

    def put(url, json, timeout):
        if outcome["fail"]:
            raise requests.exceptions.ConnectionError("no network")
        return OkResponse()

    sending = rig(put)

    sending.send(make_frame(1.0))
    assert run_until(lambda: sending.results == [False])

    outcome["fail"] = False
    sending.send(make_frame(2.0))
    assert run_until(lambda: sending.results == [False, True])


def test_an_http_error_status_counts_as_a_failed_upload(rig):
    class Rejected:
        def raise_for_status(self):
            error = requests.exceptions.HTTPError("401")
            error.response = type("Response", (), {"status_code": 401, "text": "Permission denied"})()
            raise error

    sending = rig(lambda url, json, timeout: Rejected())

    sending.send(make_frame())

    assert run_until(lambda: sending.results == [False])


def test_a_failed_upload_does_not_stop_the_sender(rig):
    calls = []

    def put(url, json, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return OkResponse()

    sending = rig(put)
    sending.send(make_frame(1.0))
    assert run_until(lambda: sending.results == [False])

    sending.send(make_frame(2.0))

    assert run_until(lambda: sending.results == [False, True])


# --- no shared mutable state ---------------------------------------------------------------------------


def test_the_sender_shares_no_mutable_state_and_uses_no_locks_or_queues():
    source = SENDER_SOURCE.read_text(encoding="utf-8")

    for forbidden in ("Lock", "RLock", "Condition", "Semaphore", "Queue", "threading", "global "):
        assert forbidden not in source, f"{forbidden!r} found in firebase_sender.py"


def test_the_latest_frame_is_held_only_by_the_sender_object(qapp):
    sender = FirebaseSender(put=lambda url, json, timeout: OkResponse())

    assert sender._latest is None  # private to the sender; Frames are immutable, so handing one over is safe
