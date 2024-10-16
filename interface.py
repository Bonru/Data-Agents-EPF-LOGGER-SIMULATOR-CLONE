import sys, os
import random
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
import json

from pyModbusTCP.client import ModbusClient
from time import sleep

client = ModbusClient("localhost", 8080)
lista = []

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simulated Logger Interface")
        self.setFixedSize(700, 500)

        layout = QVBoxLayout()

        self.labels = [self.create_label() for _ in range(4)]
        for label in self.labels:
            layout.addWidget(label)
        self.setLayout(layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_numbers)
        self.timer.start(2000)

    def create_label(self):
        label = QLabel("0", self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 30px;")
        return label

    def update_numbers(self):
        try:
            file_path = os.path.join(os.path.dirname(__file__), "lista.json")
            if os.path.exists(file_path):
                with open(file_path, "r") as file:
                    lista = json.load(file)
                    print(lista)
                    for i, label in enumerate(self.labels):
                        text = str(lista[i][1] + ": " + str(lista[i][0]) + " " + lista[i][2])
                        label.setText(text)
            else:
                print("lista.json not found")
        except json.JSONDecodeError:
            print("Error decoding JSON from lista.json")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())