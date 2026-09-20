---
status: accepted
---

# The Client runs in a Qt worker thread and talks to the UI only through immutable Frames

The original UI called Modbus I/O directly from a UI timer, so a slow or hung Simulator froze the event loop (`moveToThread` was defeated by those direct calls), and the Firebase pool read a list the UI thread was mutating. We decided that all Modbus I/O lives in a worker `QObject` on its own `QThread`, which owns the connection and the poll timer. The UI and the worker communicate only through queued signals carrying immutable snapshots (Frames, Connection state, override changes); the UI never calls the worker directly and no mutable state is shared or locked. Firebase upload runs in its own sender thread fed by a single latest-Frame slot, so a slow upload can delay neither polling nor the UI.

## Considered Options

- **asyncio loop in a background thread**: rejected because the UI is already PyQt6, so queued signals give the same message passing without a second event loop, and asyncio would mean replacing `pyModbusTCP` with an async client.
- **Plain threads plus a `queue.Queue` drained by a `QTimer`**: rejected because it reinvents signals and slots and adds a polling timer on the UI thread.

## Consequences

- With no locks and no shared state, deadlock is impossible by construction, but every new cross-thread interaction must be a signal carrying immutable data. A direct method call into the worker is a bug; a test asserting that all Modbus calls happen on the worker thread guards this.
- The latest-Frame slot drops stale Frames under a slow Firebase. This is lossless here because the upload is a PUT that replaces the same node.
