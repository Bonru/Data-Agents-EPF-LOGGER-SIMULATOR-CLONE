import os
import sys


def run_event_loop(app, window):
    """Run the Qt event loop and return the exit code."""
    exit_code = app.exec()
    if window.needs_forced_exit:
        # Destroying a QThread that is still running aborts the process, so skip the normal
        # teardown when one could not be stopped: the worker, or a Firebase upload in flight.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)
    return exit_code
