import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from src.infrastructure.bus import EventBus, Registry
from src.infrastructure.storage.persistence_manager import PersistenceManager
from src.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)

    # Infrastructure
    bus = EventBus()
    registry = Registry()
    registry.register("bus", bus)

    # Persistence
    persistence = PersistenceManager(bus, "Testes/DB.db")
    registry.register("persistence", persistence)

    # Driver - Now configuration-driven with multiple registers
    driver = MockModbusDriver(bus, registers=[0x0001, 0x0002, 0x0003])
    registry.register("driver", driver)

    # UI
    window = MainWindow()
    window.show()

    # Integration: Simulation loop
    timer = QTimer()
    timer.timeout.connect(lambda: driver.scan())
    timer.start(2000)  # Scan every 2 seconds

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
