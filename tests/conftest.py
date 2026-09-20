import os

# Must be set before Qt is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from datalogger_client.io_layer import firebase_sender


@pytest.fixture(autouse=True)
def no_real_firebase(monkeypatch):
    """A window built without a Firebase sender must not upload to the real database."""
    monkeypatch.setattr(firebase_sender, "FIREBASE_ENABLED", False)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])
