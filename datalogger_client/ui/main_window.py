from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QVBoxLayout, QLineEdit, QScrollArea
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import QPoint, QRect, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPalette

from ..core.connection_state import ConnectionState
from ..core.frame_history import FrameHistory
from ..core.registry import CHANNELS
from ..io_layer import firebase_sender
from ..io_layer.firebase_sender import FirebaseSender
from ..io_layer.transport import ModbusTcpTransport
from ..io_layer.worker import ModbusWorker
from .cards import ChannelCards
from .charts import ChannelChart
from .override_field import OverrideField
from .status import FirebaseStatus, StatusArea

WORKER_STOP_WAIT_MS = 3000


class MainWindow(QMainWindow):
    # The UI reaches the worker only through these signals.
    write_requested = pyqtSignal(int, int)
    override_set_requested = pyqtSignal(str, float)  # Channel name, value
    override_clear_requested = pyqtSignal(str)
    stop_requested = pyqtSignal()

    def __init__(self, transport=None, poll_interval_ms=500, firebase=None, connection=None, backoff=None,
                 firebase_enabled=None):
        """firebase is the FirebaseSender to use (default: a new one). firebase_enabled=False turns the
        upload off; None follows the FIREBASE_ENABLED configuration (or is on if a sender is given)."""
        super().__init__()
        self.charts_visible = False
        self._shut_down = False
        self._charts_placed = False  # Qt has laid out the charts since the view was toggled
        self._draw_pass_pending = False  # a chart-drawing pass is already scheduled
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
        # Área de status (estado da conexão) antes dos botões
        self.status_area = StatusArea()
        header_layout.addWidget(self.status_area, 0, 10, alignment=Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.config_button, 0, 11, alignment=Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.close_button, 0, 12, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(header_widget, 0, 1, 1, 1)

        # Barra lateral esquerda com 5 linhas
        sidebar_widget = QWidget()
        sidebar_widget.setFixedSize(int(width * 0.11), int(height * 0.9))
        sidebar_widget.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        sidebar_layout = QVBoxLayout()
        self.override_fields = {}  # Channel name -> its sidebar input

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

        for channel in (channel for channel in CHANNELS if channel.overridable):
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
            sidebar_layout.addWidget(line_edit, alignment=Qt.AlignmentFlag.AlignCenter)

            # Mensagem embaixo do campo (erro de validação ou "override ativo")
            message_label = QLabel()
            message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            message_label.setWordWrap(True)
            sidebar_layout.addWidget(message_label, alignment=Qt.AlignmentFlag.AlignCenter)

            field = OverrideField(channel, line_edit, message_label, line_edit_style)
            field.set_requested.connect(self.override_set_requested)
            field.clear_requested.connect(self.override_clear_requested)
            self.override_fields[channel.name] = field
            sidebar_layout.addWidget(QWidget(), alignment=Qt.AlignmentFlag.AlignCenter) #espaçamento

        scroll_area_sidebar.setWidget(scroll_content_sidebar)
        layout.addWidget(scroll_area_sidebar, 1, 0, 1, 1)

        # Área de rolagem para os gráficos e cartões
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QGridLayout(scroll_content)
        scroll_layout.setSpacing(20)

        self.channel_cards = ChannelCards((int(width * 0.28), int(height * 0.1)))
        self.cards = self.channel_cards.cards  # Channel name -> card
        self.charts = {}  # Channel name -> its chart

        # Preenchendo a grade com os cartões e os gráficos
        for index, channel in enumerate(CHANNELS):
            row, col = divmod(index, 3)
            # Gráfico do matplotlib: a figura e a linha são criadas uma única vez
            chart = ChannelChart(channel)
            chart.canvas.setFixedSize(int(width * 0.3), int(height * 0.25))
            self.charts[channel.name] = chart

            # Adicionar widgets ao grid
            scroll_layout.addWidget(self.cards[channel.name], row, col)
            scroll_layout.addWidget(chart.canvas, row, col)
            chart.canvas.hide()  # Ocultar gráficos inicialmente

        # O cartão do Timestamp do Frame ocupa a próxima célula (não tem gráfico)
        row, col = divmod(len(CHANNELS), 3)
        scroll_layout.addWidget(self.channel_cards.timestamp_card, row, col)

        scroll_content.setLayout(scroll_layout)
        self.scroll_area.setWidget(scroll_content)
        layout.addWidget(self.scroll_area, 1, 1, 1, 1)
        # Um gráfico que entra na área visível ao rolar é desenhado
        self.scroll_area.verticalScrollBar().valueChanged.connect(lambda _value: self.draw_visible_charts())
        self.scroll_area.horizontalScrollBar().valueChanged.connect(lambda _value: self.draw_visible_charts())

        # Fundo claro
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#f8f8f8"))
        self.setPalette(palette)

        # Label para mensagens de erro
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label, 2, 1, 1, 1)

        self.history = FrameHistory()  # os últimos Frames, para os gráficos
        self.on_connection_state(ConnectionState.DISCONNECTED)  # until the first Frame arrives

        # O worker é dono de toda a I/O Modbus e do timer de Poll, em sua própria thread
        self._worker = ModbusWorker(transport or ModbusTcpTransport(), poll_interval_ms, connection, backoff)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.frame_ready.connect(self.on_frame, Qt.ConnectionType.QueuedConnection)
        self._worker.connection_state_changed.connect(self.on_connection_state, Qt.ConnectionType.QueuedConnection)
        self._worker.overrides_changed.connect(self.on_overrides_changed, Qt.ConnectionType.QueuedConnection)
        self._start_firebase_sender(firebase, firebase_enabled)
        self.write_requested.connect(self._worker.write_register, Qt.ConnectionType.QueuedConnection)
        self.override_set_requested.connect(self._worker.set_override, Qt.ConnectionType.QueuedConnection)
        self.override_clear_requested.connect(self._worker.clear_override, Qt.ConnectionType.QueuedConnection)
        self.stop_requested.connect(self._worker.stop, Qt.ConnectionType.QueuedConnection)
        # Direct: the QThread lives on the UI thread, which is blocked in shutdown() while waiting.
        self._worker.stopped.connect(self._thread.quit, Qt.ConnectionType.DirectConnection)
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        self._thread.start()

    @pyqtSlot(object)
    def on_frame(self, frame):
        self.channel_cards.show_frame(frame)
        self.history.append(frame)
        self.draw_visible_charts()
        self.error_label.setText("")

    def _start_firebase_sender(self, firebase, firebase_enabled):
        """The sender gets each Frame straight from the worker (queued) and runs on its own thread."""
        if firebase_enabled is None:  # follow the configuration, unless a sender was given
            firebase_enabled = firebase is not None or firebase_sender.FIREBASE_ENABLED
        if firebase_enabled and firebase is None:
            firebase = FirebaseSender()
        self._firebase = firebase if firebase_enabled else None
        self._firebase_thread = None
        if self._firebase is None:
            self.status_area.show_firebase_status(FirebaseStatus.DISABLED)
            return
        self._firebase_thread = QThread()
        self._firebase.moveToThread(self._firebase_thread)
        self._worker.frame_ready.connect(self._firebase.submit, Qt.ConnectionType.QueuedConnection)
        self._firebase.upload_finished.connect(self.on_firebase_upload, Qt.ConnectionType.QueuedConnection)
        self._firebase_thread.start()

    @pyqtSlot(bool)
    def on_firebase_upload(self, succeeded):
        self.status_area.show_firebase_status(FirebaseStatus.OK if succeeded else FirebaseStatus.FAILING)

    @property
    def needs_forced_exit(self):
        """True if a thread is still running that must not be waited for: the worker, if it could not
        be stopped, or the Firebase sender mid-upload. Qt aborts the process if a running QThread is
        destroyed, so run_event_loop() then skips the normal teardown (a precaution: on the development
        machine, Windows with PyQt6 6.4.2, a hung upload did not abort the process either way)."""
        return self.worker_abandoned or (self._firebase_thread is not None and self._firebase_thread.isRunning())

    @pyqtSlot(object)
    def on_overrides_changed(self, channel_names):
        for name, field in self.override_fields.items():
            field.show_active(name in channel_names)
        self.channel_cards.show_overrides(channel_names)

    @pyqtSlot(object)
    def on_connection_state(self, state):
        self.status_area.show_connection_state(state)
        self.channel_cards.set_dimmed(state != ConnectionState.CONNECTED)

    def draw_visible_charts(self):
        """Have the charts that are inside the scroll viewport and out of date drawn.

        Nothing is drawn in the data view. In the chart view this runs when a Frame arrives, when a
        chart is scrolled into view and when the view is toggled; charts outside the viewport wait.
        One chart is drawn per event-loop pass (each takes ~10-15 ms), so drawing many of them
        never blocks the UI for long. Only one chain of passes runs at a time: a request made while
        one is pending is picked up by it, because every pass looks at what is stale at that moment.
        """
        if not self._draw_pass_pending:
            self._draw_next_chart()

    def _draw_next_chart(self):
        self._draw_pass_pending = False
        if self._shut_down or not self.charts_visible or not self._charts_placed:
            return
        stale = [
            chart for chart in self.charts.values()
            if chart.needs_redraw(self.history) and self.is_in_viewport(chart.canvas)
        ]
        if stale:
            stale[0].redraw(self.history)
        if len(stale) > 1:
            self._draw_pass_pending = True
            QTimer.singleShot(0, self._draw_next_chart)

    def _charts_are_placed(self):
        """Qt has laid the charts out (it does so on the event-loop pass after the toggle)."""
        self._charts_placed = True
        self.draw_visible_charts()

    def is_in_viewport(self, widget):
        """Whether any part of the widget (inside the scroll area's content) can be seen."""
        viewport = self.scroll_area.viewport()
        return QRect(widget.mapTo(viewport, QPoint(0, 0)), widget.size()).intersects(viewport.rect())

    # Método para alternar entre exibição de dados e gráficos
    def toggle_view(self):
        self.charts_visible = not self.charts_visible
        if self.charts_visible:
            # Oculta os cartões e exibe gráficos
            self.config_button.setText("Exibir Dados")
            self.channel_cards.timestamp_card.hide()
            for channel in CHANNELS:
                self.cards[channel.name].hide()
                self.charts[channel.name].canvas.show()
            # Qt places the charts (and sizes the scroll area) on the next event-loop pass; ask
            # which are inside the viewport only after that, so it is answered from where they really are.
            self._charts_placed = False
            QTimer.singleShot(0, self._charts_are_placed)
        else:
            # Oculta gráficos e exibe cartões
            self._charts_placed = False
            self.config_button.setText("Exibir Gráfico")
            for channel in CHANNELS:
                self.charts[channel.name].canvas.hide()
                self.cards[channel.name].show()
            self.channel_cards.timestamp_card.show()

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
        if self._firebase_thread is not None:
            # Never waited for: an upload in flight, even a hung one, must not delay closing.
            self._firebase_thread.quit()
        self.stop_requested.emit()
        # Lets a Poll blocked on a hung Simulator bail out between reads.
        self._thread.requestInterruption()
        if not self._thread.wait(WORKER_STOP_WAIT_MS):
            # Stuck in a call that ignores timeouts. Killing the thread is unsafe, so
            # it is abandoned; run_event_loop() then skips teardown so the process can end.
            print("Worker não parou a tempo; abandonando a thread")
            self.worker_abandoned = True
