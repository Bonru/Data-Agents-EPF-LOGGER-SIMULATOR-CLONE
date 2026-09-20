import os
import sys


def run_event_loop(app, window):
    """Run the Qt event loop and return the exit code."""
    exit_code = app.exec()
    if window.worker_abandoned:
        # Destroying a QThread that is still running aborts the process, so
        # skip the normal teardown when the worker could not be stopped.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)
    return exit_code
