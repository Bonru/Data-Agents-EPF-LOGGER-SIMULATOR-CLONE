"""Temporary compatibility adapter (ticket #6, fed with Frames since #18).

Keeps the Firebase upload (#10) working on top of the Frame stream until
that ticket replaces it; #12 deletes this module.
"""
import threading

import requests

from ..core.registry import CHANNELS

FIREBASE_URL = "https://monitoramento-usf-default-rtdb.firebaseio.com/{child_name}.json"


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


class CompatibilityAdapter:
    def __init__(self, submit_firebase):
        self._submit_firebase = submit_firebase

    def consume(self, frame):
        self._submit_firebase(build_firebase_payload(frame))
