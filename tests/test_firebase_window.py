"""The Firebase sender inside the window: the status indicator, when uploads happen, and a hung Firebase."""
import time

import pytest
import requests

from datalogger_client.core.registry import channel_named
from datalogger_client.io_layer import firebase_sender
from datalogger_client.io_layer.firebase_sender import FirebaseSender
from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import FakeTransport, TickingFakeTransport
from tests.support.firebase_stub import HangingPut, OkResponse, RecordingPut
from tests.support.heartbeat import Heartbeat, run_for, run_until

WIND = channel_named("velocidade_vento")


@pytest.fixture
def make_window(qapp):
    windows = []

    def make(transport, put=None, **options):
        firebase = FirebaseSender(put=put) if put is not None else None
        window = MainWindow(transport, poll_interval_ms=50, firebase=firebase, **options)
        window.show()
        windows.append(window)
        return window

    yield make
    for window in windows:
        window.close()


def firebase_text(window):
    return window.status_area.firebase_label.text()


def test_the_indicator_starts_waiting_and_shows_ok_after_a_successful_upload(make_window):
    window = make_window(FakeTransport({224: 32}), put=RecordingPut())
    assert firebase_text(window) == "Firebase: aguardando"

    assert run_until(lambda: firebase_text(window) == "Firebase: OK")


def test_the_indicator_shows_failing_after_an_upload_error_and_recovers_after_the_next_success(make_window):
    outcome = {"fail": True}

    def put(url, json, timeout):
        if outcome["fail"]:
            raise requests.exceptions.ConnectionError("no network")
        return OkResponse()

    window = make_window(TickingFakeTransport({224: 32}), put=put)
    assert run_until(lambda: firebase_text(window) == "Firebase: falhando")

    outcome["fail"] = False  # the next Frame that is uploaded succeeds

    assert run_until(lambda: firebase_text(window) == "Firebase: OK")


def test_the_firebase_indicator_is_separate_from_the_connection_state(make_window):
    window = make_window(TickingFakeTransport(), put=RecordingPut(error=requests.exceptions.Timeout("slow")))

    assert run_until(lambda: firebase_text(window) == "Firebase: falhando")
    assert run_until(lambda: window.status_area.connection_label.text() == "Conectado")  # the link is fine


def test_the_upload_can_be_switched_off_and_the_indicator_says_so(make_window):
    window = make_window(FakeTransport({224: 32}), firebase_enabled=False)

    run_for(200)

    assert firebase_text(window) == "Firebase: desligado"
    assert window._firebase_thread is None  # no sender thread at all


def test_the_default_follows_the_configuration_switch(make_window, monkeypatch):
    monkeypatch.setattr(firebase_sender, "FIREBASE_ENABLED", False)

    window = make_window(FakeTransport())

    assert firebase_text(window) == "Firebase: desligado"


def test_one_upload_per_new_frame_not_per_poll(make_window):
    put = RecordingPut()
    make_window(FakeTransport({224: 32, 500: 100}), put=put)  # many Polls, but the Frame never changes

    run_for(600)

    assert len(put.payloads) == 1


def test_an_upload_follows_each_new_frame(make_window):
    put = RecordingPut()
    make_window(TickingFakeTransport({224: 32}), put=put)

    assert run_until(lambda: len(put.payloads) >= 3)


def test_a_manual_override_is_in_the_uploaded_payload(make_window):
    put = RecordingPut()
    window = make_window(TickingFakeTransport({224: 32}), put=put)
    field = window.override_fields[WIND.name]
    field.line_edit.setText("12.5")
    field.line_edit.editingFinished.emit()

    assert run_until(lambda: put.payloads and put.payloads[-1][0]["value"] == 12.5)  # the Frame already overlays it


# --- a Firebase that hangs -----------------------------------------------------------------------------


def test_a_hanging_firebase_does_not_slow_polling_or_stall_the_ui(make_window):
    hanging = HangingPut()
    transport = TickingFakeTransport({224: 32})
    window = make_window(transport, put=hanging)
    try:
        assert run_until(hanging.started.is_set)  # the first upload is now stuck
        run_for(200)
        reads_before, frames_before = len(transport.calls_named("read")), window.history.version
        heartbeat = Heartbeat(interval_ms=20)
        heartbeat.start()
        started = time.monotonic()

        run_for(1500)

        heartbeat.stop()
        elapsed = time.monotonic() - started
        polls = (len(transport.calls_named("read")) - reads_before) / 6  # six reads per Poll
        frames = window.history.version - frames_before
        assert polls >= elapsed / 0.05 * 0.6  # the 50 ms cadence held (allowing for timer coarseness)
        assert frames >= 10  # Frames kept reaching the UI while the upload hung
        assert heartbeat.max_gap_ms < 100
    finally:
        hanging.release.set()  # let the stuck upload finish so the sender thread can end
