from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPalette
import sys, os, json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Configuração da janela principal
        self.setWindowTitle("Interface Datalogger")
        self.setGeometry(100, 100, 1440, 810)  # Reduzindo o tamanho da janela para 80%
        
        # Widget principal e layout
        central_widget = QWidget()
        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Margens internas
        layout.setSpacing(15)  # Espaçamento entre elementos
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
        self.config_button.setStyleSheet("background-color: #ffffff; color: #4a90e2; font-size: 14px; border: none;")
        self.config_button.clicked.connect(self.toggle_view)  # Conectar ao método para alternar exibição
        header_layout = QGridLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 20, 0)
        header_layout.addWidget(self.config_button, 0, 0, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(header_widget, 0, 1, 1, 1)
        
        # Barra lateral esquerda
        sidebar_widget = QWidget()
        sidebar_widget.setFixedSize(160, 710)
        sidebar_widget.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        layout.addWidget(sidebar_widget, 1, 0, 1, 1)
        
        # Inicializar lista para armazenar os labels
        self.labels = []

        # Layout da grade para os labels
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(20)  # Aumentar o espaçamento entre labels
        
        for row in range(3):
            for col in range(2):
                # Retângulo com label
                rect_widget = QWidget()
                rect_widget.setFixedSize(500, 120)
                rect_widget.setStyleSheet("""
                    background-color: #f0f0f0;
                    border: 1px solid #d0d0d0;
                    border-radius: 8px;
                """)
                
                # Label para exibir o texto
                label = QLabel("Texto Inicial")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setStyleSheet("color: #333333;")  # Cor do texto suave
                font = QFont()
                font.setPixelSize(18)  # Ajuste do tamanho da fonte para visualização no QLabel
                label.setFont(font)
                
                # Adicionar o label à lista
                self.labels.append(label)
                
                # Configurar layout do retângulo e adicionar o label
                rect_layout = QGridLayout(rect_widget)
                rect_layout.setContentsMargins(0, 0, 0, 0)
                rect_layout.addWidget(label, 0, 0)
                
                self.grid_layout.addWidget(rect_widget, row, col)
        
        self.grid_widget.setLayout(self.grid_layout)
        layout.addWidget(self.grid_widget, 1, 1, 1, 1)
        
        # Configuração do timer para atualizar números
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_numbers)
        self.timer.start(2000)
        
        # Widget de gráfico (inicialmente oculto)
        self.graph_widget = FigureCanvas(plt.Figure(figsize=(5, 4)))
        layout.addWidget(self.graph_widget, 1, 1, 1, 1)
        self.graph_widget.hide()

        # Ajuste do fundo branco
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#f8f8f8"))  # Fundo claro, menos agressivo
        self.setPalette(palette)
        
        # Chama a função de atualização de números para carregar dados no início
        self.update_numbers()

    def update_numbers(self):
        """Carrega dados de um arquivo JSON e atualiza os labels com as informações."""
        try:
            # Definir o caminho do arquivo JSON
            file_path = os.path.join(os.path.dirname(__file__), "lista.json")
            
            # Verificar se o arquivo existe
            if os.path.exists(file_path):
                with open(file_path, "r") as file:
                    lista = json.load(file)
                    
                    # Atualizar o texto dos labels de acordo com os dados do JSON
                    for i, label in enumerate(self.labels):
                        if i < len(lista):
                            text = f"{lista[i][1]}: {lista[i][0]} {lista[i][2]}"
                            label.setText(text)
            else:
                print("Arquivo 'lista.json' não encontrado.")
        
        except json.JSONDecodeError:
            print("Erro ao decodificar JSON de 'lista.json'")
            
    def toggle_view(self):
        """Alterna entre a visualização de dados e o gráfico."""
        if self.grid_widget.isVisible():
            # Oculta os dados e exibe o gráfico
            self.grid_widget.hide()
            self.config_button.setText("Exibir Dados")
            self.display_graph()
            self.graph_widget.show()
        else:
            # Oculta o gráfico e exibe os dados
            self.graph_widget.hide()
            self.config_button.setText("Exibir Gráfico")
            self.grid_widget.show()

    def display_graph(self):
        """Atualiza o gráfico com dados de exemplo (substituir pelos dados reais)."""
        # Obter o eixo da figura e limpar para atualização
        ax = self.graph_widget.figure.subplots()
        ax.clear()
        
        # Dados de exemplo para o gráfico
        x = [1, 2, 3, 4]
        y = [10, 20, 15, 25]
        
        # Plotar o gráfico
        ax.plot(x, y, marker='o')
        ax.set_title("Gráfico de Exemplo")
        ax.set_xlabel("Tempo")
        ax.set_ylabel("Valor")
        
        # Atualizar o widget do gráfico
        self.graph_widget.draw()

# Execução da aplicação
if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
