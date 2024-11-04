from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, QTimer, QProcess
from PyQt6.QtGui import QPalette
import sys, os, json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Configuração da janela principal
        self.setWindowTitle("Interface Datalogger")
        self.setGeometry(100, 100, 1440, 810)
        
        # Widget principal e layout
        central_widget = QWidget()
        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # Retângulo azul superior esquerdo com título
        admin_label = QLabel("Admin")
        admin_label.setFixedSize(160, 90)
        admin_label.setStyleSheet("background-color: #4a90e2; color: #ffffff; border-radius: 10px; padding: 10px;")
        font = QFont()
        font.setPixelSize(40)
        admin_label.setFont(font)
        admin_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(admin_label, 0, 0, 1, 1)
        
        # Barra superior com botão "Config"
        header_widget = QWidget()
        header_widget.setFixedSize(1220, 90)
        header_widget.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        
        # Botão Config para alternar entre dados e gráficos
        self.config_button = QPushButton("Exibir Gráfico")
        self.config_button.setFixedSize(150, 40)
        self.config_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #4a90e2;
                font-size: 14px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.config_button.clicked.connect(self.toggle_view)
        header_layout = QGridLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 20, 0)
        header_layout.addWidget(self.config_button, 0, 0, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(header_widget, 0, 1, 1, 1)
        
        # Barra lateral esquerda
        sidebar_widget = QWidget()
        sidebar_widget.setFixedSize(160, 710)
        sidebar_widget.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        layout.addWidget(sidebar_widget, 1, 0, 1, 1)
        
        # Layout da grade para os labels e gráficos
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(20)
        
        # Listas para armazenar labels e gráficos
        self.labels = []
        self.graphs = []
        
        # Preenchendo a grade com widgets de labels e gráficos
        for row in range(3):
            for col in range(2):
                # Widget para gráfico com canvas do matplotlib
                graph_canvas = FigureCanvas(plt.Figure(figsize=(5, 4)))
                graph_canvas.setFixedSize(500, 200)
                self.graphs.append(graph_canvas)
                
                # Widget com label para exibir texto
                rect_widget = QWidget()
                rect_widget.setFixedSize(500, 120)
                rect_widget.setStyleSheet("background-color: #f0f0f0; border: 1px solid #d0d0d0; border-radius: 10px;")
                
                label = QLabel("Texto Inicial")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setStyleSheet("color: #333333;")
                font = QFont()
                font.setPixelSize(22)
                label.setFont(font)
                
                self.labels.append(label)
                
                # Layout para o label e adição ao widget
                rect_layout = QGridLayout(rect_widget)
                rect_layout.setContentsMargins(0, 0, 0, 0)
                rect_layout.addWidget(label, 0, 0)
                
                # Adicionar widgets ao grid
                self.grid_layout.addWidget(rect_widget, row, col)
                self.grid_layout.addWidget(graph_canvas, row, col)
                graph_canvas.hide()  # Ocultar gráficos inicialmente
                
        self.grid_widget.setLayout(self.grid_layout)
        layout.addWidget(self.grid_widget, 1, 1, 1, 1)
        
        # Configuração do timer para atualizar números
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_numbers)
        self.timer.start(1500)
        
        # Fundo claro
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#f8f8f8"))
        self.setPalette(palette)
        
        # Label para mensagens de erro
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label, 2, 1, 1, 1)
        
        # Atualizar números no início
        self.update_numbers()

        # Iniciar o script pymodbus_cliente.py
        self.process = QProcess(self)
        self.process.start("python3", [os.path.join(os.path.dirname(__file__), "Pymodbus_Server.py")])

        # Iniciar o script pymodbus_cliente.py
        self.process2 = QProcess(self)
        self.process2.start("python3", [os.path.join(os.path.dirname(__file__), "Pymodbus_cliente.py")])

    def update_numbers(self):
        try:
            file_path = os.path.join(os.path.dirname(__file__), "lista.json")
            
            if os.path.exists(file_path):
                with open(file_path, "r") as file:
                    lista = json.load(file)
                    
                    for i, label in enumerate(self.labels):
                        if i < len(lista):
                            text = f"{lista[i][1]}: {lista[i][0]} {lista[i][2]}"
                            label.setText(text) #atualiza o texto correspondente
                            self.display_graph(self.graphs[i], label.text().split(":")[0]) #atualizar o gráfico correspondente
                self.error_label.setText("")  # Limpar mensagem de erro
            else:
                self.error_label.setText("Arquivo 'lista.json' não encontrado.")
        
        except json.JSONDecodeError:
            self.error_label.setText("Erro ao decodificar JSON de 'lista.json'")
            
    def toggle_view(self):
        if self.labels[0].isVisible():
            # Oculta os labels e exibe gráficos
            for label, graph_canvas in zip(self.labels, self.graphs):
                label.hide()
                self.config_button.setText("Exibir Dados")
                self.display_graph(graph_canvas, label.text().split(":")[0])
                graph_canvas.show()
        else:
            # Oculta gráficos e exibe labels
            for label, graph_canvas in zip(self.labels, self.graphs):
                graph_canvas.hide()
                self.config_button.setText("Exibir Gráfico")
                label.show()

    def display_graph(self, graph_canvas, data_type):
        ax = graph_canvas.figure.subplots()
        fig = graph_canvas.figure
        ax.clear()

        #apaga a figura anterior
        fig.clear()

        #cria um novo eixo pra figura
        ax = fig.add_subplot(111)
        
        file_path = os.path.join(os.path.dirname(__file__), "historico_leituras.json")
        
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                dados = json.load(file)
                
                if data_type in dados:
                    x = list(range(len(dados[data_type])))
                    y = dados[data_type]
                    ax.plot(x, y, marker='o')
                    ax.set_title(f"Gráfico de {data_type}")
                    ax.set_xlabel("Tempo")
                else:
                    self.error_label.setText(f"Dados de {data_type} não encontrados no arquivo JSON.")
        else:
            self.error_label.setText("Arquivo 'historico_leituras.json' não encontrado.")

        graph_canvas.draw()

# Execução da aplicação
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
