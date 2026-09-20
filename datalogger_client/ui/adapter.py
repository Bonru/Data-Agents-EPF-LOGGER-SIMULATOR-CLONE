"""Temporary compatibility adapter (ticket #6, fed with Frames since #18).

Keeps the features that later tickets will migrate working on top of the
Frame stream: chart history (#9), Firebase upload (#10) and the manual
insertion sidebar (#8). Each ticket replaces one piece; #12 deletes this module.
"""
import threading
import time
from collections import deque

import requests

from ..core.registry import CHANNELS

CHART_HISTORY_LENGTH = 30
FIREBASE_URL = "https://monitoramento-usf-default-rtdb.firebaseio.com/{child_name}.json"


def seconds_to_hms(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def build_firebase_payload(frame):
    return [
        {"name": channel.label, "value": frame.reading(channel), "unit": channel.unit}
        for channel in CHANNELS
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


class ChartHistory:
    """The last few Frames, as one time axis plus one series per Channel name."""

    def __init__(self):
        self.timestamps = deque(maxlen=CHART_HISTORY_LENGTH)
        self.values = {channel.name: deque(maxlen=CHART_HISTORY_LENGTH) for channel in CHANNELS}

    def append(self, frame):
        seconds = frame.timestamp
        if seconds is None:
            self.timestamps.append(time.strftime("%H:%M:%S", time.localtime(frame.received_at)))
        else:
            self.timestamps.append(seconds_to_hms(seconds))
        for channel in CHANNELS:
            self.values[channel.name].append(frame.reading(channel))


class CompatibilityAdapter:
    def __init__(self, manual_fields, request_write, submit_firebase):
        """manual_fields maps each overridable Channel to its sidebar input."""
        self._manual_fields = manual_fields
        self._request_write = request_write
        self._submit_firebase = submit_firebase
        self.chart_history = ChartHistory()

    def consume(self, frame):
        self.chart_history.append(frame)
        self._submit_firebase(build_firebase_payload(frame))
        self._resend_manual_values()

    def _resend_manual_values(self):
        for channel, line_edit in self._manual_fields.items():
            text = line_edit.text()
            if text == "":
                continue
            try:
                self._request_write(channel.address, channel.encode(int(text)))
            except ValueError:
                print(f"Valor inválido para {channel.label}: {text!r}")
