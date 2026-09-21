"""Helpers to build the Simulator's register bank (Pymodbus_Server.MyDataBank) in tests."""


def quiet_bank(simulator, *args, **kwargs):
    """The register bank without its background thread: the test advances the rows itself."""

    class QuietBank(simulator.MyDataBank):
        def update_values_periodically(self):
            pass

    return QuietBank(*args, **kwargs)
