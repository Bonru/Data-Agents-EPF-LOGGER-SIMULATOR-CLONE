"""Temporary compatibility adapter (ticket #6).

Keeps the features that later tickets will migrate working on top of the
snapshot stream: chart history (#9), Firebase upload (#10) and the manual
insertion sidebar (#8). Each ticket replaces one piece; #12 deletes this module.
"""
import threading
from collections import deque

import requests

from ..io_layer.channels import CHANNELS, OVERRIDABLE_CHANNELS, REGISTER_SCALE, TIMESTAMP_LABEL

CHART_HISTORY_LENGTH = 30
FIREBASE_URL = "https://monitoramento-usf-default-rtdb.firebaseio.com/{child_name}.json"


def seconds_to_hms(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def build_firebase_payload(snapshot):
    return [
        {"name": entry.label, "value": entry.value, "unit": entry.unit}
        for entry in snapshot.entries
    ]


def submit_to_firebase(payload, child_name="parametros"):
    """Send the payload on a daemon thread, so it never blocks the caller or keeps the process alive."""
    threading.Thread(target=_put_to_firebase, args=(payload, child_name), daemon=True).start()


def _put_to_firebase(payload, child_name):
    try:
        response = requests.put(FIREBASE_URL.format(child_name=child_name), json=payload, timeout=10)
        response.raise_for_status()
        print(f"Firebase response: {response.text}")
    except requests.exceptions.HTTPError as e:
        print(f"Erro HTTP ao enviar para Firebase: {e.response.status_code} {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão com Firebase: {e}")
    except Exception as e:
        print(f"Erro inesperado ao enviar para Firebase: {e}")


class CompatibilityAdapter:
    def __init__(self, line_edits, request_write, submit_firebase, channels=CHANNELS):
        self._line_edits = line_edits
        self._request_write = request_write
        self._submit_firebase = submit_firebase
        self.chart_history = {
            channel.label: deque(maxlen=CHART_HISTORY_LENGTH) for channel in channels
        }

    def consume(self, snapshot):
        self._append_chart_history(snapshot)
        self._submit_firebase(build_firebase_payload(snapshot))
        self._resend_manual_values()

    def _append_chart_history(self, snapshot):
        for entry in snapshot.entries:
            if entry.label == TIMESTAMP_LABEL:
                self.chart_history[entry.label].append(seconds_to_hms(snapshot.timestamp))
            else:
                self.chart_history[entry.label].append(entry.value)

    def _resend_manual_values(self):
        for channel, line_edit in zip(OVERRIDABLE_CHANNELS, self._line_edits):
            text = line_edit.text()
            if text == "":
                continue
            try:
                self._request_write(channel.address, int(text) * REGISTER_SCALE)
            except ValueError:
                print(f"Valor inválido para {channel.label}: {text!r}")
