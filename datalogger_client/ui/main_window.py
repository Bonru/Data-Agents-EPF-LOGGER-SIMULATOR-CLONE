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
from .layout import (
    CONTENT_STRETCH, CONTROL_POINT_SIZE, DEFAULT_WINDOW_SIZE, HEADER_MIN_HEIGHT, MAX_COLUMNS, MINIMUM_WINDOW_SIZE,
    GRID_MARGIN, GRID_SPACING, OUTER_MARGIN, OUTER_SPACING, SIDEBAR_MIN_WIDTH, SIDEBAR_STRETCH, TITLE_POINT_SIZE, columns_for_width,
    header_fits_one_row, row_after,
)
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
        self.resize(*DEFAULT_WINDOW_SIZE)
        self.setMinimumSize(*MINIMUM_WINDOW_SIZE)  # explicit, so the window can shrink to where the layout goes compact
        self.grid_columns = 0  # columns of the card grid; set by _reflow()
        self.header_compact = None  # whether the page is stacked for a narrow window; set by _reflow()

        # Widget principal e layout: a coluna lateral e a área de conteúdo dividem a largura por fatores de esticamento
        central_widget = QWidget()
        self._page = QGridLayout()
        self._page.setContentsMargins(OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN)
        self._page.setSpacing(OUTER_SPACING)
        self._page.setColumnMinimumWidth(0, SIDEBAR_MIN_WIDTH)
        self._page.setColumnStretch(0, SIDEBAR_STRETCH)
        self._page.setColumnStretch(1, CONTENT_STRETCH)
        central_widget.setLayout(self._page)
        self.setCentralWidget(central_widget)

        self._title = self._build_title()
        self._build_header()
        self._build_sidebar()
        self._build_content()

        # Fundo claro
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#f8f8f8"))
        self.setPalette(palette)

        # Label para mensagens de erro
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")

        self._arrange_page(compact=False)
        self._reflow(self.width())

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

    # --- construção da interface: nenhum tamanho vem da tela; tudo é dado por layouts, políticas e mínimos ---

    def _build_title(self):
        """Retângulo azul superior esquerdo com título."""
        title = QLabel("Interface")
        title.setStyleSheet("background-color: #4a90e2; color: #ffffff; border-radius: 10px; padding: 10px;")
        font = QFont()
        font.setPointSize(TITLE_POINT_SIZE)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setMinimumHeight(HEADER_MIN_HEIGHT)
        return title

    def _build_header(self):
        """Barra superior azul: área de status e botões. Em janelas estreitas os itens são empilhados."""
        self.header_widget = QWidget()
        self.header_widget.setMinimumHeight(HEADER_MIN_HEIGHT)
        self.header_widget.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        self.status_area = StatusArea()
        self.config_button = self._header_button("Exibir Gráfico", self.toggle_view)
        self.close_button = self._header_button("Fechar Aplicação", self.close_application)
        self._header_layout = QGridLayout(self.header_widget)
        self._header_layout.setContentsMargins(10, 6, 10, 6)
        self._header_layout.setSpacing(10)
        self._arrange_header(compact=False)
        self.header_regular_min_width = self.header_widget.minimumSizeHint().width()  # what one row needs
        return self.header_widget

    @staticmethod
    def _header_button(text, on_click):
        button = QPushButton(text)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: #ffffff;
                color: #4a90e2;
                font-size: {CONTROL_POINT_SIZE}pt;
                padding: 6px 12px;
                border: none;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: #e0e0e0;
            }}
        """)
        button.clicked.connect(on_click)
        return button

    def _arrange_header(self, compact):
        header = self._header_layout
        for widget in (self.status_area, self.config_button, self.close_button):
            header.removeWidget(widget)
        for column in range(4):
            header.setColumnStretch(column, 0)
        self.status_area.set_compact(compact)
        if compact:  # everything stacked in one column
            header.addWidget(self.status_area, 0, 0)
            header.addWidget(self.config_button, 1, 0)
            header.addWidget(self.close_button, 2, 0)
            header.setColumnStretch(0, 1)
        else:
            header.addWidget(self.status_area, 0, 0)
            header.addWidget(self.config_button, 0, 2)
            header.addWidget(self.close_button, 0, 3)
            header.setColumnStretch(1, 1)  # o espaço entre a área de status e os botões
        self.header_compact = compact

    def _arrange_page(self, compact):
        """The title, header, sidebar and content: side by side normally, and in a narrow window with
        the title and the header across the whole width, above the sidebar and the content."""
        page = self._page
        for widget in (self._title, self.header_widget, self.sidebar_area, self.scroll_area, self.error_label):
            page.removeWidget(widget)
        for row in range(4):
            page.setRowStretch(row, 0)
        if compact:
            page.addWidget(self._title, 0, 0, 1, 2)
            page.addWidget(self.header_widget, 1, 0, 1, 2)
            page.addWidget(self.sidebar_area, 2, 0)
            page.addWidget(self.scroll_area, 2, 1)
            page.addWidget(self.error_label, 3, 1)
            page.setRowStretch(2, 1)  # a barra lateral e os cartões ficam com a altura
        else:
            page.addWidget(self._title, 0, 0)
            page.addWidget(self.header_widget, 0, 1)
            page.addWidget(self.sidebar_area, 1, 0)
            page.addWidget(self.scroll_area, 1, 1)
            page.addWidget(self.error_label, 2, 1)
            page.setRowStretch(1, 1)
        self._arrange_header(compact)

    def _build_sidebar(self):
        """Barra lateral azul de inserção manual: um campo por Channel, numa área de rolagem."""
        label_style = f"background-color: #ffffff; color: #4a90e2; font-size: {CONTROL_POINT_SIZE}pt;"
        line_edit_style = f"background-color: #ffffff; color: #4a90e2; font-size: {CONTROL_POINT_SIZE}pt;"
        max_length = 6  # limite de caracteres
        self.override_fields = {}  # Channel name -> its sidebar input

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(9)

        title = QLabel("Inserção manual")
        title.setStyleSheet(label_style)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(QWidget())  # espaçamento

        for channel in (channel for channel in CHANNELS if channel.overridable):
            label = QLabel(channel.label)
            label.setStyleSheet(label_style)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            sidebar_layout.addWidget(label)

            line_edit = QLineEdit("")
            line_edit.setStyleSheet(line_edit_style)
            line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            line_edit.setMaxLength(max_length)
            sidebar_layout.addWidget(line_edit)

            # Mensagem embaixo do campo (erro de validação ou "override ativo")
            message_label = QLabel()
            message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            message_label.setWordWrap(True)
            sidebar_layout.addWidget(message_label)

            field = OverrideField(channel, line_edit, message_label, line_edit_style)
            field.set_requested.connect(self.override_set_requested)
            field.clear_requested.connect(self.override_clear_requested)
            self.override_fields[channel.name] = field
            sidebar_layout.addWidget(QWidget())  # espaçamento
        sidebar_layout.addStretch(1)

        content = QWidget()
        content.setLayout(sidebar_layout)
        self.sidebar_area = QScrollArea()
        self.sidebar_area.setWidgetResizable(True)
        self.sidebar_area.setMinimumWidth(SIDEBAR_MIN_WIDTH)
        self.sidebar_area.setStyleSheet("background-color: #4a90e2; border-radius: 10px;")
        self.sidebar_area.setWidget(content)
        return self.sidebar_area

    def _build_content(self):
        """Área de rolagem com a grade de cartões e gráficos; o número de colunas muda com a largura."""
        self.channel_cards = ChannelCards()
        self.cards = self.channel_cards.cards  # Channel name -> card
        self.charts = {}  # Channel name -> its chart
        for channel in CHANNELS:
            self.charts[channel.name] = ChannelChart(channel)  # a figura e a linha são criadas uma única vez
            self.charts[channel.name].canvas.hide()  # ocultar gráficos inicialmente

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self._grid = QGridLayout(scroll_content)
        self._grid.setSpacing(GRID_SPACING)
        self._grid.setContentsMargins(GRID_MARGIN, GRID_MARGIN, GRID_MARGIN, GRID_MARGIN)
        self.scroll_area.setWidget(scroll_content)
        # Um gráfico que entra na área visível ao rolar é desenhado
        self.scroll_area.verticalScrollBar().valueChanged.connect(lambda _value: self.draw_visible_charts())
        self.scroll_area.horizontalScrollBar().valueChanged.connect(lambda _value: self.draw_visible_charts())
        return self.scroll_area

    def _place_grid_items(self, columns):
        """Put every card (and its chart, in the same cell) in the grid with this many columns."""
        grid = self._grid
        while grid.count():
            grid.takeAt(0)  # the widgets stay; only their places in the grid are forgotten
        for index, channel in enumerate(CHANNELS):
            row, column = divmod(index, columns)
            grid.addWidget(self.cards[channel.name], row, column)
            grid.addWidget(self.charts[channel.name].canvas, row, column)
        # O cartão do Timestamp do Frame ocupa a próxima célula (não tem gráfico)
        row, column = divmod(len(CHANNELS), columns)
        grid.addWidget(self.channel_cards.timestamp_card, row, column)
        for column in range(MAX_COLUMNS):
            grid.setColumnStretch(column, 1 if column < columns else 0)
        for row in range(len(CHANNELS) + 2):
            grid.setRowStretch(row, 0)
        grid.setRowStretch(row_after(len(CHANNELS) + 1, columns), 1)  # a folga vertical fica abaixo dos cartões

    def _reflow(self, window_width):
        """Recompute what depends on the window width; called on every resize."""
        columns = columns_for_width(window_width)
        if columns != self.grid_columns:
            self.grid_columns = columns
            self._place_grid_items(columns)
        compact = not header_fits_one_row(window_width, self.header_regular_min_width)
        if compact != self.header_compact:
            self._arrange_page(compact)
        self._redraw_charts_after_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow(event.size().width())

    def _redraw_charts_after_layout(self):
        """The charts changed size (or place): draw them again, once Qt has laid them out."""
        for chart in self.charts.values():
            chart.invalidate()
        if self.charts_visible:
            self._charts_placed = False
            QTimer.singleShot(0, self._charts_are_placed)

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
