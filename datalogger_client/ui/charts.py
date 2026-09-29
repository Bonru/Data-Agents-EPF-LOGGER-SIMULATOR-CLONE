from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QSizePolicy

from .layout import CHART_MIN_SIZE, CHART_SIZE_HINT

MAX_TICKS = 4
PIXELS_PER_TICK = 80  # a narrow chart gets fewer time labels, so they do not overlap
NO_VERSION = -1  # nothing drawn yet


class ExplicitlyDrawnCanvas(FigureCanvas):
    """A canvas that draws only when told to.

    Matplotlib's Qt canvas schedules a draw of its own (`draw_idle`) whenever it is resized, which
    includes the first time it is shown. With many charts in a scroll area that would draw every
    one of them, out of view ones included, in a single burst that freezes the UI.
    """

    def __init__(self, figure):
        super().__init__(figure)
        self.setMinimumSize(*CHART_MIN_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)  # grows with its grid column

    def sizeHint(self):
        return QSize(*CHART_SIZE_HINT)

    def minimumSizeHint(self):
        return QSize(*CHART_MIN_SIZE)

    def draw_idle(self, *args, **kwargs):
        pass

    def paintEvent(self, event):
        # Until a chart has been drawn (or after it was resized, until it is drawn again) there is
        # no image to show: paint white instead of leaving the area unpainted (black).
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        painter.end()
        super().paintEvent(event)


class ChannelChart:
    """One Channel's chart. The figure, axes and line are created once; an update only sets the
    line's data, rescales and draws (no clearing and rebuilding of the figure)."""

    def __init__(self, channel):
        self.channel = channel
        self.canvas = ExplicitlyDrawnCanvas(Figure(figsize=(5, 4)))
        self.axes = self.canvas.figure.add_subplot(111)
        (self.line,) = self.axes.plot([], [], marker="o")
        # Fixed margins (as fractions of the figure) leave room for the labels even in a small chart;
        # matplotlib's automatic layouts fit better but cost ~3x as much to draw.
        self.canvas.figure.subplots_adjust(left=0.25, right=0.96, bottom=0.31, top=0.80)
        self.axes.set_title(f"Gráfico de {channel.label}", fontsize="small", wrap=True)  # wraps in a narrow chart
        self.axes.set_xlabel("Tempo", fontsize="small")
        self.axes.tick_params(labelsize="small")
        self.drawn_version = NO_VERSION

    def needs_redraw(self, history):
        return self.drawn_version != history.version

    def invalidate(self):
        """Forget what was drawn, e.g. because the chart was resized and must be drawn again."""
        self.drawn_version = NO_VERSION

    def redraw(self, history):
        """Draw the history now. A Frame with no Reading for the Channel leaves a break in the line."""
        labels = history.time_labels()
        missing = float("nan")
        values = [missing if reading is None else reading for reading in history.readings(self.channel)]
        self.line.set_data(range(len(values)), values)
        ticks = max(2, min(MAX_TICKS, self.canvas.width() // PIXELS_PER_TICK))
        step = max(1, -(-len(labels) // ticks))  # rounded up: at most `ticks` labels
        positions = range(0, len(labels), step)
        self.axes.set_xticks(list(positions))
        self.axes.set_xticklabels([labels[position] for position in positions])
        self.axes.relim()
        self.axes.autoscale_view()
        self.canvas.draw()
        self.drawn_version = history.version
