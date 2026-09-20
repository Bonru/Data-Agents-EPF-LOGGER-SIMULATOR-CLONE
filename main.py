import sys

from PyQt6.QtWidgets import QApplication

from datalogger_client.ui.app import run_event_loop
from datalogger_client.ui.main_window import MainWindow

# Execução da aplicação
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    sys.exit(run_event_loop(app, window))
