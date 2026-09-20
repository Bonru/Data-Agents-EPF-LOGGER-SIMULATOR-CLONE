from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

NUMBER_OF_TICKS = 4
NO_VERSION = -1  # nothing drawn yet


class ExplicitlyDrawnCanvas(FigureCanvas):
    """A canvas that draws only when told to.

    Matplotlib's Qt canvas schedules a draw of its own (`draw_idle`) whenever it is resized, which
    includes the first time it is shown. With many charts in a scroll area that would draw every
    one of them, out of view ones included, in a single burst that freezes the UI.
    """

    def draw_idle(self, *args, **kwargs):
        pass


class ChannelChart:
    """One Channel's chart. The figure, axes and line are created once; an update only sets the
    line's data, rescales and draws (no clearing and rebuilding of the figure)."""

    def __init__(self, channel):
        self.channel = channel
        self.canvas = ExplicitlyDrawnCanvas(Figure(figsize=(5, 4)))
        self.axes = self.canvas.figure.add_subplot(111)
        (self.line,) = self.axes.plot([], [], marker="o")
        self.axes.set_title(f"Gráfico de {channel.label}")
        self.axes.set_xlabel("Tempo")
        self.drawn_version = NO_VERSION

    def needs_redraw(self, history):
        return self.drawn_version != history.version

    def redraw(self, history):
        """Draw the history now. A Frame with no Reading for the Channel leaves a break in the line."""
        labels = history.time_labels()
        missing = float("nan")
        values = [missing if reading is None else reading for reading in history.readings(self.channel)]
        self.line.set_data(range(len(values)), values)
        step = max(1, len(labels) // NUMBER_OF_TICKS)
        positions = range(0, len(labels), step)
        self.axes.set_xticks(list(positions))
        self.axes.set_xticklabels([labels[position] for position in positions])
        self.axes.relim()
        self.axes.autoscale_view()
        self.canvas.draw()
        self.drawn_version = history.version
