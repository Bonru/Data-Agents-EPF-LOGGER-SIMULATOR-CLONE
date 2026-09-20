"""The window layout at different sizes: the card grid reflows, nothing overlaps or is clipped, and the
sizes come from layout rules rather than from the screen."""
import re
from itertools import combinations
from pathlib import Path

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QAbstractScrollArea, QApplication, QLabel, QLineEdit, QPushButton, QWidget

from datalogger_client.core.registry import CHANNELS
from datalogger_client.ui.layout import MINIMUM_WINDOW_SIZE, columns_for_width
from datalogger_client.ui.main_window import MainWindow
from tests.support.fake_transport import FakeTransport
from tests.support.heartbeat import Heartbeat, run_for, run_until

WIDTHS = [400, 800, 1200, 1920]
HEIGHT = 900
VIEWS = ["data", "chart"]
REPO_ROOT = Path(__file__).resolve().parent.parent
UI_SOURCES = sorted((REPO_ROOT / "datalogger_client" / "ui").glob("*.py"))
SCREENSHOT_DIR = REPO_ROOT / ".scratch" / "screenshots"  # not committed (see .gitignore)


@pytest.fixture
def window(qapp):
    window = MainWindow(FakeTransport({224: 32, 500: 100}), poll_interval_ms=200)
    window.show()
    run_for(200)
    yield window
    window.close()


STYLES = ["Fusion", "Windows", "windowsvista"]  # they differ in scroll bar and frame sizes


@pytest.fixture(params=STYLES)
def styled_window(qapp, request):
    """The same window under each Qt style: a layout that fits by a pixel in one style overflows in another."""
    QApplication.setStyle(request.param)
    window = MainWindow(FakeTransport({224: 32, 500: 100}), poll_interval_ms=200)
    window.show()
    run_for(200)
    yield window
    window.close()
    QApplication.setStyle("Fusion")


def show_view(window, view):
    if (view == "chart") != window.charts_visible:
        window.toggle_view()
        run_for(150)


def resize_to(window, width, height=HEIGHT):
    window.resize(width, height)
    run_for(150)  # the layout and the deferred chart draws settle
    assert (window.width(), window.height()) == (width, height), "the window could not take that size"


def grid_items(window, view):
    """The widgets that fill the card grid in this view: the cards, or the charts."""
    if view == "chart":
        return [window.charts[channel.name].canvas for channel in CHANNELS]
    return [*(window.cards[channel.name] for channel in CHANNELS), window.channel_cards.timestamp_card]


def stale_visible_charts(window):
    """Charts in view that have not yet drawn the current history (only relevant in the chart view)."""
    if not window.charts_visible:
        return []
    return [c for c in window.charts.values() if c.needs_redraw(window.history) and window.is_in_viewport(c.canvas)]


def in_content(window, widget):
    """The widget's rectangle in the coordinates of the scroll area's content."""
    content = window.scroll_area.widget()
    return QRect(widget.mapTo(content, QPoint(0, 0)), widget.size())


def clipped(window):
    """Visible widgets that do not fit: outside their parent, or narrower than their own content needs."""
    problems = []
    for widget in window.findChildren(QWidget):
        parent = widget.parentWidget()
        if widget.isHidden() or parent is None or isinstance(parent, QAbstractScrollArea):
            continue  # a scroll area's viewport and bars are Qt's; what is inside the viewport is checked below
        if isinstance(parent.parentWidget(), QAbstractScrollArea) and parent.parentWidget().viewport() is parent:
            continue  # the content widget of a scroll area may be larger than its viewport: it scrolls
        if not parent.rect().contains(widget.geometry()):
            problems.append(f"{widget.metaObject().className()} {widget.geometry()} is outside its parent {parent.rect()}")
        if isinstance(widget, (QLabel, QPushButton, QLineEdit)) and widget.width() < widget.minimumSizeHint().width():
            problems.append(f"{widget.metaObject().className()} '{getattr(widget, 'text', lambda: '')()}' is {widget.width()} px wide, needs {widget.minimumSizeHint().width()}")
        if isinstance(widget, QLabel) and widget.wordWrap() and widget.height() < widget.heightForWidth(widget.width()):
            problems.append(f"QLabel '{widget.text()}' is {widget.height()} px tall, its wrapped text needs {widget.heightForWidth(widget.width())}")
    return problems


# --- the card grid reflows ---------------------------------------------------------------------------


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("width", WIDTHS)
def test_the_grid_has_the_number_of_columns_the_formula_gives(window, width, view):
    show_view(window, view)
    resize_to(window, width)

    items = grid_items(window, view)
    columns = columns_for_width(width)
    assert window.grid_columns == columns
    assert len({in_content(window, item).x() for item in items}) == columns  # really laid out in that many columns
    assert all(not item.isHidden() for item in items)


def test_the_grid_recomputes_on_every_resize_and_back(window):
    for width in [1920, 400, 1200, 800, 1680, 839, 840]:
        resize_to(window, width)
        assert window.grid_columns == columns_for_width(width)
        assert len({in_content(window, card).x() for card in grid_items(window, "data")}) == columns_for_width(width)


def test_every_channel_keeps_its_own_cell_after_reflowing(window):
    resize_to(window, 400)
    resize_to(window, 1920)

    positions = {(rect.x(), rect.y()) for rect in (in_content(window, window.cards[c.name]) for c in CHANNELS)}
    assert len(positions) == len(CHANNELS)  # no two cards in the same place


# --- nothing overlaps or is clipped ------------------------------------------------------------------


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("width", WIDTHS)
def test_no_two_cards_overlap(window, width, view):
    show_view(window, view)
    resize_to(window, width)

    rectangles = [in_content(window, item) for item in grid_items(window, view)]
    overlapping = [(a, b) for a, b in combinations(rectangles, 2) if a.intersects(b)]
    assert overlapping == []


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("width", WIDTHS)
def test_no_widget_is_clipped_by_its_parent_without_a_scroll_bar_to_reach_it(styled_window, width, view):
    window = styled_window
    show_view(window, view)
    resize_to(window, width)

    content = window.scroll_area.widget()
    assert all(content.rect().contains(in_content(window, item)) for item in grid_items(window, view))  # scrolls to
    sidebar_content = window.sidebar_area.widget()
    assert all(sidebar_content.rect().contains(field.line_edit.geometry()) for field in window.override_fields.values())
    assert clipped(window) == []


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("width", WIDTHS)
def test_neither_the_main_area_nor_the_sidebar_needs_a_horizontal_scroll_bar(styled_window, width, view):
    window = styled_window
    show_view(window, view)
    resize_to(window, width)

    assert window.scroll_area.horizontalScrollBar().maximum() == 0
    assert window.sidebar_area.horizontalScrollBar().maximum() == 0


@pytest.mark.parametrize("view", VIEWS)
def test_the_layout_fits_at_the_smallest_size_the_window_allows(styled_window, view):
    """The declared minimum window size must not be smaller than what the layout needs."""
    window = styled_window
    show_view(window, view)
    minimum_width, minimum_height = MINIMUM_WINDOW_SIZE

    window.resize(100, 100)  # ask for less than the minimum
    run_for(150)

    assert (window.width(), window.height()) == (minimum_width, minimum_height)
    assert window.scroll_area.horizontalScrollBar().maximum() == 0
    assert window.sidebar_area.horizontalScrollBar().maximum() == 0
    assert clipped(window) == []


@pytest.mark.parametrize("height", [500, 700, 1200])
def test_nothing_is_clipped_at_other_window_heights(styled_window, height):
    window = styled_window
    for width in WIDTHS:
        resize_to(window, width, height)
        assert clipped(window) == []
        assert window.scroll_area.horizontalScrollBar().maximum() == 0


@pytest.mark.parametrize("width", WIDTHS)
def test_the_content_can_be_scrolled_to_vertically(window, width):
    resize_to(window, width)

    content = window.scroll_area.widget()
    assert window.scroll_area.verticalScrollBar().maximum() >= 0
    assert content.height() >= max(in_content(window, card).bottom() for card in grid_items(window, "data"))


# --- the header reflows in narrow windows ------------------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
def test_the_header_still_holds_everything_in_either_arrangement(window, width):
    resize_to(window, width)

    header = window.header_widget
    for widget in (window.status_area, window.config_button, window.close_button):
        assert not widget.isHidden()
        assert header.rect().contains(widget.geometry())
    assert header.width() >= header.minimumSizeHint().width()  # what it needs, in the arrangement it has


def test_the_header_is_one_row_in_a_wide_window_and_stacked_in_a_narrow_one(window):
    def rectangles():
        parts = (window.status_area, window.config_button, window.close_button)
        return [QRect(part.mapTo(window, QPoint(0, 0)), part.size()) for part in parts]

    resize_to(window, 1920)
    wide, wide_is_compact = rectangles(), window.header_compact
    resize_to(window, 400)
    narrow, narrow_is_compact = rectangles(), window.header_compact

    assert not wide_is_compact and narrow_is_compact
    # one row: every item overlaps the others vertically (they sit side by side)
    assert all(a.top() <= b.bottom() and b.top() <= a.bottom() for a, b in combinations(wide, 2))
    # stacked: each item is entirely above the next
    assert narrow[0].bottom() < narrow[1].top() and narrow[1].bottom() < narrow[2].top()
    assert window.header_widget.width() > window.sidebar_area.width()  # and the header now spans the page


def test_the_header_rearranges_as_the_window_grows_and_shrinks(window):
    states = []
    for width in [400, 1920, 400, 1200, 800, 1920]:
        resize_to(window, width)
        states.append(window.header_compact)

    assert states[0] and not states[1] and states[2]  # it follows the width in both directions
    assert states[-1] is False


# --- the look is kept -------------------------------------------------------------------------------


def pixel(widget, x, y):
    image = widget.grab().toImage()
    color = image.pixelColor(x, y)
    return (color.red(), color.green(), color.blue())


@pytest.mark.parametrize("width", [400, 1920])
def test_the_header_and_sidebar_keep_the_blue_background_and_the_window_its_light_one(window, width):
    resize_to(window, width)

    blue = QColor("#4a90e2")
    assert "#4a90e2" in window.header_widget.styleSheet()
    assert "#4a90e2" in window.sidebar_area.styleSheet()
    assert window.header_widget.grab().toImage().pixelColor(window.header_widget.width() // 2, 3).name() == blue.name()
    assert window.sidebar_area.grab().toImage().pixelColor(window.sidebar_area.width() // 2, 3).name() == blue.name()
    assert window.palette().window().color().name() == QColor("#f8f8f8").name()
    assert window.windowTitle() == "Interface Datalogger"


# --- responsiveness while resizing --------------------------------------------------------------------


@pytest.mark.parametrize("view", VIEWS)
def test_the_ui_does_not_stall_while_the_window_is_resized_through_the_widths(window, view):
    show_view(window, view)
    heartbeat = Heartbeat(interval_ms=20)
    heartbeat.start()

    for width in WIDTHS + list(reversed(WIDTHS)):
        window.resize(width, HEIGHT)
        run_for(150)

    heartbeat.stop()
    assert heartbeat.max_gap_ms <= 100


# --- screenshots for a person to look at --------------------------------------------------------------


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("width", WIDTHS)
def test_a_screenshot_is_saved_at_each_width_and_view(window, width, view):
    show_view(window, view)
    resize_to(window, width)
    assert run_until(lambda: not stale_visible_charts(window), timeout_ms=3000)  # the charts are drawn one per pass
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{view}-{width}.png"

    saved = window.grab().save(str(path))

    assert saved and path.stat().st_size > 0


# --- no sizes from the screen or in pixels -------------------------------------------------------------

FORBIDDEN = {
    "a fixed size": r"\bset(Fixed|Maximum)(Size|Width|Height)\b",
    "a hand-set geometry": r"\bsetGeometry\b|\.resize\(\s*int\(",
    "the screen geometry": r"primaryScreen|availableGeometry|screenGeometry|\.screens?\(\)",
    "a pixel font size": r"font-size:\s*(\{[^}]*\}|[\d.]+)\s*px|setPixelSize",
}


def find_violations(source):
    return [(what, match.group(0)) for what, pattern in FORBIDDEN.items() for match in re.finditer(pattern, source)]


@pytest.mark.parametrize("source", UI_SOURCES, ids=[path.name for path in UI_SOURCES])
def test_the_ui_layer_has_no_fixed_sizes_screen_derived_sizes_or_pixel_fonts(source):
    assert find_violations(source.read_text(encoding="utf-8")) == []


def test_the_source_check_really_catches_each_kind_of_violation():
    assert find_violations("widget.setFixedSize(10, 10)")
    assert find_violations("self.setFixedWidth(100)") and find_violations("x.setFixedHeight(5)")
    assert find_violations("g = QApplication.primaryScreen().geometry()")
    assert find_violations("label.setStyleSheet('font-size: 18px;')")
    assert find_violations("font.setPixelSize(32)")
    assert find_violations("w.setMaximumWidth(200)") and find_violations("w.setMaximumSize(1, 1)")
    assert find_violations("self.setGeometry(0, 0, 10, 10)") and find_violations("self.resize(int(w * 0.8), 5)")
    assert find_violations("f'font-size: {size}px;'")  # a pixel size hidden in an f-string
    assert find_violations("self.resize(*DEFAULT_WINDOW_SIZE)") == []  # a size from constants is fine
    assert find_violations("font-size: 10pt; padding: 6px") == []  # points, and other pixel values, are fine
    assert UI_SOURCES  # and it looks at something
