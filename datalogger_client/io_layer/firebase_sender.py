import requests
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from ..core.registry import CHANNELS

# Configuration. FIREBASE_ENABLED is the on/off switch (it was `post_requests` in the old Client).
FIREBASE_ENABLED = True
FIREBASE_URL = "https://monitoramento-usf-default-rtdb.firebaseio.com/parametros.json"
FIREBASE_TIMEOUT_S = 10


def build_firebase_payload(frame):
    """A list of {name, value, unit} in registry order, `name` being the display label.

    A Channel with no Reading is sent with `value: null`, which the web view shows as an empty cell.
    """
    return [
        {"name": channel.label, "value": frame.reading(channel), "unit": channel.unit}
        for channel in CHANNELS
    ]


class FirebaseSender(QObject):
    """Uploads Frames to Firebase from its own thread, so a slow upload delays neither polling nor the UI.

    It receives Frames only through the queued `submit` signal (Frames are immutable) and keeps
    nothing another thread can touch, so no lock is needed. It holds only the latest Frame: the
    upload is a PUT that replaces the same node, so a Frame that was overtaken while an upload was
    in flight is dropped, and nothing is lost.

    Every `submit` that queued up during an upload runs before the zero-delay timer that follows
    it, each overwriting the one before, so the next upload is of the newest Frame.
    """

    upload_finished = pyqtSignal(bool)  # whether the PUT succeeded

    def __init__(self, url=FIREBASE_URL, timeout=FIREBASE_TIMEOUT_S, put=requests.put):
        super().__init__()
        self._url = url
        self._timeout = timeout
        self._put = put
        self._latest = None
        self._upload_scheduled = False

    @pyqtSlot(object)
    def submit(self, frame):
        self._latest = frame
        if not self._upload_scheduled:
            self._upload_scheduled = True
            QTimer.singleShot(0, self._upload_latest)

    def _upload_latest(self):
        self._upload_scheduled = False
        frame, self._latest = self._latest, None
        if frame is not None:
            self.upload_finished.emit(self._upload(frame))

    def _upload(self, frame):
        try:
            response = self._put(self._url, json=build_firebase_payload(frame), timeout=self._timeout)
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            print(f"Erro HTTP ao enviar para Firebase: {e.response.status_code} {e.response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão com Firebase: {e}")
        except Exception as e:
            print(f"Erro inesperado ao enviar para Firebase: {e}")
        return False
