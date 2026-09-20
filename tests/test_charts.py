"""Charts: each one's line is created once and updated, and only charts inside the viewport are drawn."""
import inspect
import math
from pathlib import Path

import pytest

from datalogger_client.core.frame import Frame
from datalogger_client.core.frame_history import FrameHistory
from datalogger_client.core.registry import CHANNELS, channel_named
from datalogger_client.ui import charts as charts_module
from datalogger_client.ui.charts import ChannelChart
from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import FakeTransport
from tests.support.heartbeat import run_for, run_until

WIND = channel_named("velocidade_vento")
UI_SOURCES = sorted((Path(__file__).resolve().parent.parent / "datalogger_client" / "ui").glob("*.py"))


def make_frame(value=1.0, timestamp=3600, missing=()):
    readings = {c.name: value for c in CHANNELS if c.name not in missing}
    return Frame(readings, timestamp, received_at=0.0)


def history_of(*frames):
    history = FrameHistory()
    for frame in frames:
        history.append(frame)
    return history


# --- one chart -------------------------------------------------------------------------------------


def test_a_chart_shows_the_readings_against_the_frame_timestamps(qapp):
    chart = ChannelChart(WIND)
    history = history_of(make_frame(1.0, 3600), make_frame(2.0, 3602), make_frame(3.0, 3604))

    chart.redraw(history)

    assert list(chart.line.get_ydata()) == [1.0, 2.0, 3.0]
    assert [label.get_text() for label in chart.axes.get_xticklabels()] == ["01:00:00", "01:00:02", "01:00:04"]
    assert chart.axes.get_title() == "Gráfico de Vel. vento"
    assert chart.axes.get_xlabel() == "Tempo"


def test_updating_reuses_the_same_axes_and_line_instead_of_rebuilding_them(qapp):
    chart = ChannelChart(WIND)
    figure, axes, line = chart.canvas.figure, chart.axes, chart.line
    history = FrameHistory()

    for value in range(1, 6):
        history.append(make_frame(float(value), 3600 + 2 * value))
        chart.redraw(history)

    assert chart.canvas.figure is figure and chart.axes is axes and chart.line is line
    assert list(figure.axes) == [axes] and list(axes.lines) == [line]
    assert list(line.get_ydata()) == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_a_missing_reading_is_a_gap_in_the_line_never_a_zero(qapp):
    chart = ChannelChart(WIND)
    history = history_of(make_frame(5.0), make_frame(missing={"velocidade_vento"}), make_frame(7.0))

    chart.redraw(history)

    y = list(chart.line.get_ydata())
    assert y[0] == 5.0 and y[2] == 7.0 and math.isnan(y[1])
    assert 0 not in y


def test_the_axes_rescale_to_the_data_on_every_update(qapp):
    chart = ChannelChart(WIND)
    history = FrameHistory()
    history.append(make_frame(10.0))
    chart.redraw(history)
    low_top = chart.axes.get_ylim()[1]

    history.append(make_frame(1000.0))
    chart.redraw(history)

    assert chart.axes.get_ylim()[1] > low_top


def test_an_empty_history_draws_without_error(qapp):
    chart = ChannelChart(WIND)

    chart.redraw(FrameHistory())

    assert list(chart.line.get_ydata()) == []


def test_a_chart_knows_whether_it_has_drawn_the_current_history(qapp):
    chart = ChannelChart(WIND)
    history = history_of(make_frame())
    assert chart.needs_redraw(history)

    chart.redraw(history)
    assert not chart.needs_redraw(history)

    history.append(make_frame())
    assert chart.needs_redraw(history)


def test_the_clear_and_rebuild_drawing_pattern_is_gone():
    redraw_source = inspect.getsource(ChannelChart.redraw)
    for pattern in ("clear(", "subplots(", "add_subplot(", "Figure("):
        assert pattern not in redraw_source  # an update only sets data and rescales
    assert inspect.getsource(charts_module).count("add_subplot(") == 1  # once, when the chart is created
    for source in UI_SOURCES:
        text = source.read_text(encoding="utf-8")
        assert "fig.clear" not in text and "display_graph" not in text and "pyplot" not in text


# --- which charts are drawn -----------------------------------------------------------------------


@pytest.fixture
def window(qapp, monkeypatch):
    drawn = []
    original = ChannelChart.redraw

    def spy(self, history):
        drawn.append(self.channel.name)
        original(self, history)

    monkeypatch.setattr(ChannelChart, "redraw", spy)
    window = MainWindow(FakeTransport({224: 32, 500: 100}), poll_interval_ms=60000, submit_firebase=lambda payload: None)
    window.canvas_draws = []  # every real matplotlib draw, whoever asked for it
    for name, chart in window.charts.items():
        real_draw = chart.canvas.draw
        chart.canvas.draw = lambda name=name, real_draw=real_draw: (window.canvas_draws.append(name), real_draw())[1]
    window.show()
    run_for(300)  # the layout is placed, and the first Frame (from the worker) has arrived
    window.drawn = drawn
    drawn.clear()
    window.canvas_draws.clear()
    yield window
    window.close()


def settle(window):
    """Let the event loop run until every chart inside the viewport has drawn the current history."""
    def all_drawn():
        return not any(
            chart.needs_redraw(window.history) and window.is_in_viewport(chart.canvas)
            for chart in window.charts.values()
        )

    run_for(50)  # Qt places the charts and sizes the scroll area
    assert run_until(all_drawn, timeout_ms=3000)


def show_charts(window):
    """Switch to the chart view; the charts are drawn a few per event-loop pass."""
    window.toggle_view()
    settle(window)


def visible_chart_names(window):
    return {name for name, chart in window.charts.items() if window.is_in_viewport(chart.canvas)}


def test_no_chart_is_drawn_in_the_data_view_when_a_frame_arrives(window):
    window.on_frame(make_frame(2.0))
    window.on_frame(make_frame(3.0))
    run_for(100)

    assert window.drawn == [] and window.canvas_draws == []


def test_the_viewport_shows_some_charts_but_not_all_of_them(window):
    show_charts(window)
    inside = visible_chart_names(window)

    assert 6 <= len(inside) < len(CHANNELS)  # about 6 or more visible, the rest scrolled out


def test_toggling_to_the_chart_view_draws_only_the_charts_in_the_viewport(window):
    window.on_frame(make_frame(2.0))  # something to draw

    show_charts(window)

    assert set(window.drawn) == visible_chart_names(window)
    assert len(window.drawn) == len(set(window.drawn))  # each once


def test_in_the_chart_view_a_new_frame_redraws_only_the_charts_inside_the_viewport(window):
    show_charts(window)
    window.drawn.clear()

    window.on_frame(make_frame(2.0))
    settle(window)

    assert set(window.drawn) == visible_chart_names(window)
    assert len(window.drawn) == len(set(window.drawn))  # each once
    assert set(window.drawn) < {channel.name for channel in CHANNELS}  # strictly fewer than all


def test_no_canvas_outside_the_viewport_ever_draws_itself(window):
    """Matplotlib's Qt canvas draws itself when first shown; that must not happen for charts nobody can see."""
    show_charts(window)
    window.on_frame(make_frame(2.0))
    settle(window)
    run_for(200)  # any draw a canvas scheduled for itself would have happened by now

    assert set(window.canvas_draws) == visible_chart_names(window)
    assert len(window.canvas_draws) == len(window.drawn)  # every real draw was one of ours


def test_toggling_back_to_the_data_view_draws_nothing_and_hidden_charts_stay_undrawn(window):
    show_charts(window)
    window.drawn.clear()

    window.toggle_view()  # back to the data view
    window.on_frame(make_frame(2.0))

    assert window.drawn == []


def test_a_chart_scrolled_into_view_is_drawn_and_the_ones_already_current_are_not(window):
    show_charts(window)
    window.on_frame(make_frame(2.0))
    settle(window)  # every chart in view has drawn this Frame
    first_view = visible_chart_names(window)
    window.drawn.clear()

    bar = window.scroll_area.verticalScrollBar()
    bar.setValue(bar.maximum())
    settle(window)

    newly_visible = visible_chart_names(window) - first_view
    assert newly_visible  # scrolling did bring charts into view
    assert set(window.drawn) == newly_visible  # only those; the still-visible ones were current
    window.drawn.clear()

    bar.setValue(bar.minimum())  # back up: the first charts were current and no Frame arrived meanwhile
    settle(window)
    assert window.drawn == []


def test_charts_that_were_out_of_view_when_a_frame_arrived_are_drawn_with_current_data_on_scroll(window):
    show_charts(window)
    window.on_frame(make_frame(2.0))
    window.on_frame(make_frame(3.0))  # arrives while the bottom charts are out of view
    bar = window.scroll_area.verticalScrollBar()

    bar.setValue(bar.maximum())
    settle(window)

    bottom_chart = window.charts[CHANNELS[-1].name]
    assert list(bottom_chart.line.get_ydata())[-2:] == [2.0, 3.0]  # drawn from the latest history
    assert not bottom_chart.needs_redraw(window.history)
