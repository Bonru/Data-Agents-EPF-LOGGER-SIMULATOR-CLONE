---
name: keep-app-working
description: Ground rule for changing the PyQt UI or the Modbus Client (files under datalogger_client/ui/, datalogger_client/io_layer/, or main.py) — the app must still launch and every existing feature must still work afterward. Applies to any edit there: new feature, refactor, or bug fix, whether or not it's tied to a ticket.
---

# Keep the app working

Editing `datalogger_client/ui/`, `datalogger_client/io_layer/`, or `main.py` can silently break a feature your diff never mentions.

1. Run the full suite (same command as `implement-ticket` step 4).
2. Never leave one of these broken between commits: the data view / chart toggle, the manual-override sidebar, the Firebase upload, or the three Connection states (Connected/Stale/Disconnected).

## Done when

- The full suite passes and you can quote its last line.
- Every one of the four features above still has a passing test exercising it — or you added one.
