from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QVBoxLayout, QLineEdit, QScrollArea
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, QTimer, QProcess, QThread
from PyQt6.QtGui import QPalette
import sys, os, json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtGui import QIntValidator
from Pymodbus_cliente import ModbusClientHandler


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Intervalo de atualização de dados
        self.intervalo = 1500
        # Iniciar o script pymodbus_cliente.py
        self.client = ModbusClientHandler()
        self.thread = QThread()
        self.client.moveToThread(self.thread)
        self.thread.started.connect(self.client.start)
        self.thread.start()

        # Configuração da janela principal
        self.setWindowTitle("Interface Datalogger")
        screen_geometry = QApplication.primaryScreen().geometry()
        width = int(screen_geometry.width() * 0.87)
        height = int(screen_geometry.height() * 0.87)
        self.setGeometry(int(screen_geometry.width() * 0.1), int(screen_geometry.height() * 0.1), width, height)
        
        # Widget principal e layout
        central_widget = QWidget()
        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # Retângulo azul superior esquerdo com título
        admin_label = QLabel("Interface")
        admin_label.setFixedSize(int(width * 0.11), int(height * 0.11))
        admin_label.setStyleSheet("background-color: #4a90e2; color: #ffffff; border-radius: 10px; padding: 10px;")
        font = QFont()
        font.setPixelSize(32)
        admin_label.setFont(font)
        admin_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(admin_label, 0, 0, 1, 1)
        
        # Barra superior com botão "toggle"
        header_widget = QWidget()
        header_widget.setFixedSize(int(width * 1), int(height * 0.11))
        header_widget.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        
        # Botão toggle para alternar entre dados e gráficos
        self.config_button = QPushButton("Exibir Gráfico")
        self.config_button.setFixedSize(int(width * 0.1), int(height * 0.05))
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

        # Botão para fechar a aplicação
        self.close_button = QPushButton("Fechar Aplicação")
        self.close_button.setFixedSize(int(width * 0.1), int(height * 0.05))
        self.close_button.setStyleSheet("""
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
        self.close_button.clicked.connect(self.close_application) 

        # Layout do cabeçalho
        header_layout = QGridLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 20, 0)

        # Adiciona espaços vazios nas primeiras colunas
        for i in range(10):
            header_layout.addWidget(QWidget(), 0, i)

        # Adiciona os botões nas últimas duas colunas
        header_layout.addWidget(self.config_button, 0, 11, alignment=Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.close_button, 0, 12, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(header_widget, 0, 1, 1, 1)
        
        # Barra lateral esquerda com 5 linhas
        sidebar_widget = QWidget()
        sidebar_widget.setFixedSize(int(width * 0.11), int(height * 0.9))
        sidebar_widget.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        sidebar_layout = QVBoxLayout()
        self.line_edits = []

        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        
        # Adicionando titulo na barra lateral
        label = QLabel(f"Inserção manual")
        label.setStyleSheet("background-color: #ffffff; color: #4a90e2; font-size: 18px;")
        label.setFixedSize(int(width * 0.09), int(height * 0.06))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Definindo estilos e tamanhos padronizados
        label_style = "background-color: #ffffff; color: #4a90e2; font-size: 18px;"
        line_edit_style = "background-color: #ffffff; color: #4a90e2; font-size: 16px;"
        fixed_size = (int(width * 0.08), int(height * 0.04))
        max_length = 6  # Definindo o limite de caracteres

        # Ajustando o espaçamento do layout
        sidebar_layout.setSpacing(5)
        sidebar_layout.addWidget(QWidget(), alignment=Qt.AlignmentFlag.AlignCenter)

        for i in range(1, 7):
            lista = self.client.getdata()
            text = f"{lista[i - 1][1]}"

            label = QLabel(text)
            label.setStyleSheet(label_style)
            label.setFixedSize(*fixed_size)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sidebar_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)

            line_edit = QLineEdit("")
            line_edit.setStyleSheet(line_edit_style)
            line_edit.setFixedSize(*fixed_size)
            line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            line_edit.setMaxLength(max_length)  # Definindo o limite de caracteres
            line_edit.setValidator(QIntValidator())  # Permitindo apenas entrada de números
            sidebar_layout.addWidget(line_edit, alignment=Qt.AlignmentFlag.AlignCenter)
            
            self.line_edits.append(line_edit)  # Adiciona o LineEdit à lista
            sidebar_layout.addWidget(QWidget(), alignment=Qt.AlignmentFlag.AlignCenter) #espaçamento

        sidebar_widget.setLayout(sidebar_layout)
        layout.addWidget(sidebar_widget, 1, 0, 1, 1)
        
        # Área de rolagem para os gráficos e labels
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QGridLayout(scroll_content)
        scroll_layout.setSpacing(20)

        # Listas para armazenar labels e gráficos
        self.labels = []
        self.graphs = []
        
        # Preenchendo a grade com widgets de labels e gráficos
        for row in range(6):
            for col in range(3):
                # Widget para gráfico com canvas do matplotlib
                graph_canvas = FigureCanvas(plt.Figure(figsize=(5, 4)))
                graph_canvas.setFixedSize(int(width * 0.3), int(height * 0.25))
                self.graphs.append(graph_canvas)
                
                # Widget com label para exibir texto
                rect_widget = QWidget()
                rect_widget.setFixedSize(int(width * 0.28), int(height * 0.1))
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
                scroll_layout.addWidget(rect_widget, row, col)
                scroll_layout.addWidget(graph_canvas, row, col)
                graph_canvas.hide()  # Ocultar gráficos inicialmente
                
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1, 1, 1, 1)
        
        # Configuração do timer para atualizar os parametros
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_numbers)
        self.timer.start(self.intervalo)

        
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

    # Método para atualizar os números exibidos
    def update_numbers(self):
        try:
            self.force_variable()
            self.client.read_registers()
            lista = self.client.getdata()
            for i, label in enumerate(self.labels):
                text = f"{lista[i][1]}: {lista[i][0]} {lista[i][2]}"
                label.setText(text)  # Atualiza o texto correspondente
                self.display_graph(self.graphs[i], label.text().split(":")[0])  # Atualizar o gráfico correspondente
            self.error_label.setText("")
        except Exception as e:
            self.handleError(e)
            self.error_label.setText(f"Erro ao atualizar os números: {e}")

    # Método para alternar entre exibição de dados e gráficos
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

    # Método para exibir gráficos
    def display_graph(self, graph_canvas, data_type):
        ax = graph_canvas.figure.subplots()
        fig = graph_canvas.figure
        ax.clear()

        # Apaga a figura anterior
        fig.clear()

        # Cria um novo eixo pra figura
        ax = fig.add_subplot(111)
        
        # Gerar o gráfico
        dados = self.client.historico_leituras
        if data_type in dados:
            x = list(range(len(dados[data_type])))
            y = dados[data_type]
            ax.plot(x, y, marker='o')
            ax.set_title(f"Gráfico de {data_type}")
            ax.set_xlabel("Tempo")
        else:
            self.error_label.setText(f"Dados de {data_type} não encontrados.")

        graph_canvas.draw()

    # Método para forçar a atualização dos valores
    def force_variable(self):
        try:
            lista = self.client.getdata()
            aux = False
            # Atualiza os valores em self.parametros com os valores dos LineEdit
            for i, line_edit in enumerate(self.line_edits):
                if i < len(lista):
                    if line_edit.text() != "":
                        new_value = (int(line_edit.text()) * 10)
                        print("i", i, "New_value", new_value)
                        self.client.write_register(i, new_value)

        except ValueError:
            self.error_label.setText("Erro ao converter valor para float.")

    def close_application(self):
        self.close()

    def handleError(self, error):
        print(f"Ocorreu um erro: {error}")

# Execução da aplicação
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
