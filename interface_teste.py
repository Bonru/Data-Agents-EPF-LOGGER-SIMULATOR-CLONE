from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QVBoxLayout, QPushButton, QScrollArea, QLineEdit, QSizePolicy
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, QTimer, QProcess
from PyQt6.QtGui import QPalette
import sys, os, json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtGui import QIntValidator

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
        admin_label.setStyleSheet("background-color: #4a90e2; color: #ffffff; border-radius: 10px; padding: 10px;")
        font = QFont()
        font.setPixelSize(40)
        admin_label.setFont(font)
        admin_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(admin_label, 0, 0, 1, 1)
        
        # Barra superior com botão "toggle"
        header_widget = QWidget()
        header_widget.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        
        # Botão toggle para alternar entre dados e gráficos
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

        # Botão para fechar a aplicação
        self.close_button = QPushButton("Fechar Aplicação")
        self.close_button.setFixedSize(150, 40)
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
        self.close_button.clicked.connect(self.close_application)  # Conecta o botão ao método de fechar aplicação

        # Layout do cabeçalho
        header_layout = QGridLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 20, 0)

        # Adiciona espaços vazios nas primeiras colunas
        for i in range(5):
            header_layout.addWidget(QWidget(), 0, i)

        # Adiciona os botões nas últimas duas colunas
        header_layout.addWidget(self.config_button, 0, 5, alignment=Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.close_button, 0, 6, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(header_widget, 0, 1, 1, 1)
        
        # Barra lateral esquerda com 5 linhas
        sidebar_widget = QWidget()
        sidebar_widget.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        sidebar_layout = QVBoxLayout()
        self.line_edits = []  # Lista para armazenar os elementos LineEdit

        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        
        # Adicionando titulo na barra lateral
        label = QLabel(f"Inserção manual")
        label.setStyleSheet("background-color: #ffffff; color: #4a90e2; font-size: 18px; border-radius: 10px; padding: 10px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Definindo estilos e tamanhos padronizados
        label_style = "background-color: #ffffff; color: #4a90e2; font-size: 18px; border-radius: 10px; padding: 5px;"
        line_edit_style = "background-color: #ffffff; color: #4a90e2; font-size: 16px;"
        max_length = 6  # Definindo o limite de caracteres

        # Ajustando o espaçamento do layout
        sidebar_layout.setSpacing(5)  # Define o espaçamento vertical entre os widgets
        sidebar_layout.addWidget(QWidget(), alignment=Qt.AlignmentFlag.AlignCenter) #espaçamento

        for i in range(1, 7):
            try:
                file_path = os.path.join(os.path.dirname(__file__), "lista.json")
                if os.path.exists(file_path):
                    with open(file_path, "r") as file:
                        lista = json.load(file)
                        if i < len(lista) + 1:
                            text = f"{lista[i - 1][1]}"
                        else:
                            text = "N/A"
                else:
                    text = "N/A"
            except json.JSONDecodeError:
                text = "Erro"

            label = QLabel(text)
            label.setStyleSheet(label_style)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sidebar_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)

            line_edit = QLineEdit("")
            line_edit.setStyleSheet(line_edit_style)
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
        self.buttons = []

        # Preenchendo a área de rolagem com widgets de labels e gráficos
        for i in range(6):  # Número de conjuntos de gráficos e labels
            # Widget para gráfico com canvas do matplotlib
            graph_canvas = FigureCanvas(plt.Figure(figsize=(5, 2)))
            ax = graph_canvas.figure.add_subplot(111)
            ax.plot([1, 2, 3], [1, 4, 9], label="Exemplo")
            ax.legend()
            graph_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            graph_canvas.setFixedHeight(400)
            graph_canvas.setVisible(False)  # Inicialmente invisível
            self.graphs.append(graph_canvas)

            # Widget com label para exibir texto
            rect_widget = QWidget()
            rect_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            rect_widget.setMaximumHeight(120)
            rect_widget.setStyleSheet("background-color: #f0f0f0; border: 1px solid #d0d0d0; border-radius: 10px;")

            label = QLabel("Texto Inicial")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #333333;")
            font = QFont()
            font.setPixelSize(22)
            label.setFont(font)

            self.labels.append(label)

            # Layout para o label e botão
            rect_layout = QVBoxLayout(rect_widget)
            rect_layout.setContentsMargins(0, 0, 0, 0)
            rect_layout.addWidget(label)

            # Adicionar label e gráfico ao layout de rolagem
            row = i // 2
            col = i % 2
            scroll_layout.addWidget(rect_widget, row * 2, col)
            scroll_layout.addWidget(graph_canvas, row * 2 + 1, col)

        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1, 1, 1, 1)
        
        # Configuração do timer para atualizar números
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.force_variable)
        self.timer.timeout.connect(self.update_numbers)
        self.timer.timeout.connect(self.timeout)
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

        # Iniciar o script Pymodbus_Server.py
        self.process = QProcess(self)
        self.process.start("python3", [os.path.join(os.path.dirname(__file__), "Pymodbus_Server.py")])

        # Iniciar o script pymodbus_cliente.py
        self.process2 = QProcess(self)
        self.process2.start("python3", [os.path.join(os.path.dirname(__file__), "Pymodbus_cliente.py")])

    def timeout(self):
            print("timeout")

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

        # Apaga a figura anterior
        fig.clear()

        # Cria um novo eixo para a figura
        ax = fig.add_subplot(111)
        
        file_path = os.path.join(os.path.dirname(__file__), "historico_leituras.json")
        
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                dados = json.load(file)
                
                if data_type in dados:
                    x = dados["Timestamp"]
                    y = dados[data_type]
                    ax.plot(x, y, marker='o')
                    ax.set_title(f"Gráfico de {data_type}")
                    ax.set_xlabel("Horário")
                    
                    # Definir ticks do eixo x para mostrar apenas 5 valores igualmente espaçados
                    num_ticks = 4
                    if len(x) > num_ticks:
                        tick_positions = [x[i] for i in range(0, len(x), len(x) // num_ticks)]
                        ax.set_xticks(tick_positions)
                        ax.set_xticklabels([x[i] for i in range(0, len(x), len(x) // num_ticks)])
                    else:
                        ax.set_xticks(x)
                        ax.set_xticklabels(x)
                else:
                    self.error_label.setText(f"Dados de {data_type} não encontrados no arquivo JSON.")
        else:
            self.error_label.setText("Arquivo 'historico_leituras.json' não encontrado.")

        graph_canvas.draw()

    def force_variable(self):
        try:
            file_path = os.path.join(os.path.dirname(__file__), "lista.json")
            historico_path = os.path.join(os.path.dirname(__file__), "historico_leituras.json")
            
            if os.path.exists(file_path):
                with open(file_path, "r") as file:
                    lista = json.load(file)
                
                # Atualiza os valores no arquivo lista.json com os valores dos LineEdit
                for i, line_edit in enumerate(self.line_edits):
                    if i < len(lista):
                        if line_edit.text() != "":
                            lista[i][0] = int(line_edit.text())
                
                with open(file_path, "w") as file:
                    json.dump(lista, file)
                
                self.error_label.setText("")  # Limpar mensagem de erro
            else:
                self.error_label.setText("Arquivo 'lista.json' não encontrado.")
            
            if os.path.exists(historico_path):
                with open(historico_path, "r") as file:
                    historico = json.load(file)
                
                # Atualiza os valores no arquivo historico_leituras.json com os valores dos LineEdit
                for i, line_edit in enumerate(self.line_edits):
                    if i < len(lista):
                        if line_edit.text() != "":
                            data_type = lista[i][1]
                            if data_type in historico:
                                historico[data_type][-1] = int(line_edit.text())
                
                with open(historico_path, "w") as file:
                    json.dump(historico, file)
            
            else:
                self.error_label.setText("Arquivo 'historico_leituras.json' não encontrado.")
        
        except json.JSONDecodeError:
            self.error_label.setText("Erro ao decodificar JSON de 'lista.json' ou 'historico_leituras.json'")
        except ValueError:
            self.error_label.setText("Erro ao converter valor para float.")

    def close_application(self):
        self.close()

    def toggle_graph(self, index):
        # Alternar a visibilidade do gráfico correspondente ao botão
        graph = self.graphs[index]
        graph.setVisible(not graph.isVisible())
        # Atualizar o texto do botão
        if graph.isVisible():
            self.buttons[index].setText("Ocultar Gráfico")
        else:
            self.buttons[index].setText("Exibir Gráfico")

# Execução da aplicação
if __name__ == "__main__":

    #Limpar dados ao iniciar

    # Arquivo a ser apagado ao iniciar
    file_to_delete = "historico_leituras.json"

    # Apagar o arquivo, se existir
    if os.path.exists(file_to_delete):
        try:
            os.remove(file_to_delete)
            print(f"Arquivo '{file_to_delete}' apagado com sucesso.")
        except Exception as e:
            print(f"Erro ao tentar apagar o arquivo '{file_to_delete}': {e}")
    else:
        print(f"Arquivo '{file_to_delete}' não encontrado.")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
