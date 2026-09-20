from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QVBoxLayout, QLineEdit, QScrollArea
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPalette
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtGui import QIntValidator

from ..io_layer.channels import CHANNELS, OVERRIDABLE_CHANNELS
from ..io_layer.transport import ModbusTcpTransport
from ..io_layer.worker import ModbusWorker
from .adapter import CompatibilityAdapter, submit_to_firebase
from .cards import ChannelCards

WORKER_STOP_WAIT_MS = 3000


class MainWindow(QMainWindow):
    # The UI reaches the worker only through these signals.
    write_requested = pyqtSignal(int, int)
    stop_requested = pyqtSignal()

    def __init__(self, transport=None, poll_interval_ms=2000, submit_firebase=submit_to_firebase):
        super().__init__()
        self.charts_visible = False
        self._shut_down = False
        self.worker_abandoned = False  # True if the worker did not stop in time

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
        fixed_size = (int(width * 0.08), int(height * 0.03))
        max_length = 6  # Definindo o limite de caracteres

        # Ajustando o espaçamento do layout
        sidebar_layout.setSpacing(9)
        sidebar_layout.addWidget(QWidget(), alignment=Qt.AlignmentFlag.AlignCenter)

        # Adicionando um QScrollArea para a barra lateral
        scroll_area_sidebar = QScrollArea()
        scroll_area_sidebar.setWidgetResizable(True)
        scroll_area_sidebar.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        scroll_content_sidebar = QWidget()
        scroll_content_sidebar.setLayout(sidebar_layout)

        for channel in OVERRIDABLE_CHANNELS:
            label = QLabel(channel.label)
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

        scroll_area_sidebar.setWidget(scroll_content_sidebar)
        layout.addWidget(scroll_area_sidebar, 1, 0, 1, 1)

        # Área de rolagem para os gráficos e cartões
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QGridLayout(scroll_content)
        scroll_layout.setSpacing(20)

        self.channel_cards = ChannelCards((int(width * 0.28), int(height * 0.1)))
        self.cards = self.channel_cards.cards
        self.graphs = []

        # Preenchendo a grade com os cartões e os gráficos
        for index, card in enumerate(self.cards):
            row, col = divmod(index, 3)
            # Widget para gráfico com canvas do matplotlib
            graph_canvas = FigureCanvas(plt.Figure(figsize=(5, 4)))
            graph_canvas.setFixedSize(int(width * 0.3), int(height * 0.25))
            self.graphs.append(graph_canvas)

            # Adicionar widgets ao grid
            scroll_layout.addWidget(card, row, col)
            scroll_layout.addWidget(graph_canvas, row, col)
            graph_canvas.hide()  # Ocultar gráficos inicialmente

        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1, 1, 1, 1)

        # Fundo claro
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#f8f8f8"))
        self.setPalette(palette)

        # Label para mensagens de erro
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label, 2, 1, 1, 1)

        self.adapter = CompatibilityAdapter(self.line_edits, self.write_requested.emit, submit_firebase)

        # O worker é dono de toda a I/O Modbus e do timer de Poll, em sua própria thread
        self._worker = ModbusWorker(transport or ModbusTcpTransport(), poll_interval_ms)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.snapshot_ready.connect(self.on_snapshot, Qt.ConnectionType.QueuedConnection)
        self.write_requested.connect(self._worker.write_register, Qt.ConnectionType.QueuedConnection)
        self.stop_requested.connect(self._worker.stop, Qt.ConnectionType.QueuedConnection)
        # Direct: the QThread lives on the UI thread, which is blocked in shutdown() while waiting.
        self._worker.stopped.connect(self._thread.quit, Qt.ConnectionType.DirectConnection)
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        self._thread.start()

    @pyqtSlot(object)
    def on_snapshot(self, snapshot):
        self.channel_cards.show_snapshot(snapshot)
        self.adapter.consume(snapshot)
        if self.charts_visible:
            self.redraw_charts()
        self.error_label.setText("")

    def redraw_charts(self):
        for graph_canvas, channel in zip(self.graphs, CHANNELS):
            self.display_graph(graph_canvas, channel.label)

    # Método para alternar entre exibição de dados e gráficos
    def toggle_view(self):
        self.charts_visible = not self.charts_visible
        if self.charts_visible:
            # Oculta os cartões e exibe gráficos
            self.config_button.setText("Exibir Dados")
            for card, graph_canvas, channel in zip(self.cards, self.graphs, CHANNELS):
                card.hide()
                self.display_graph(graph_canvas, channel.label)
                graph_canvas.show()
        else:
            # Oculta gráficos e exibe cartões
            self.config_button.setText("Exibir Gráfico")
            for card, graph_canvas in zip(self.cards, self.graphs):
                graph_canvas.hide()
                card.show()

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
        dados = self.adapter.chart_history
        if data_type in dados:
            x = dados["Timestamp"]
            y = dados[data_type]
            ax.plot(x, y, marker='o')
            ax.set_title(f"Gráfico de {data_type}")
            ax.set_xlabel("Tempo")

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
            self.error_label.setText(f"Dados de {data_type} não encontrados.")

        graph_canvas.draw()

    def close_application(self):
        self.close()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    def shutdown(self):
        """Ask the worker to stop, then wait a bounded time for its thread."""
        if self._shut_down:
            return
        self._shut_down = True
        self.stop_requested.emit()
        # Lets a Poll blocked on a hung Simulator bail out between reads.
        self._thread.requestInterruption()
        if not self._thread.wait(WORKER_STOP_WAIT_MS):
            # Stuck in a call that ignores timeouts. Killing the thread is unsafe, so
            # it is abandoned; run_event_loop() then skips teardown so the process can end.
            print("Worker não parou a tempo; abandonando a thread")
            self.worker_abandoned = True
