"""The rules and constants of the responsive window layout. Qt-free.

Nothing here is derived from the screen: the window has a default and a minimum size, and everything
inside it is sized by stretch factors, size policies and the minimum sizes below.
"""

DEFAULT_WINDOW_SIZE = (1200, 800)
MINIMUM_WINDOW_SIZE = (360, 300)

# The page: margins and spacing around the title, header, sidebar and content
OUTER_MARGIN = 20
OUTER_SPACING = 15

# The card grid: spacing and margins, and one column for every WINDOW_PIXELS_PER_COLUMN of window width, between 1 and 4.
WINDOW_PIXELS_PER_COLUMN = 420
GRID_SPACING = 20
GRID_MARGIN = 4
MIN_COLUMNS = 1
MAX_COLUMNS = 4

# Header and sidebar
SIDEBAR_STRETCH = 1
CONTENT_STRETCH = 8
SIDEBAR_MIN_WIDTH = 170
HEADER_MIN_HEIGHT = 56

# Cards and charts (minimum sizes; they grow with their grid cell)
CARD_MIN_SIZE = (150, 70)
CHART_MIN_SIZE = (150, 150)
CHART_SIZE_HINT = (360, 220)

# Text is sized in points, so it follows the user's font settings instead of a pixel count.
TITLE_POINT_SIZE = 16
CARD_POINT_SIZE = 10
CONTROL_POINT_SIZE = 9


def columns_for_width(window_width):
    return max(MIN_COLUMNS, min(MAX_COLUMNS, window_width // WINDOW_PIXELS_PER_COLUMN))


def header_width_available(window_width):
    """The width the header gets beside the sidebar column, in a window this wide."""
    content_width = window_width - 2 * OUTER_MARGIN - OUTER_SPACING
    sidebar_width = max(SIDEBAR_MIN_WIDTH, content_width * SIDEBAR_STRETCH // (SIDEBAR_STRETCH + CONTENT_STRETCH))
    return content_width - sidebar_width


def header_fits_one_row(window_width, needed_width):
    """Whether the header, which needs `needed_width` to lay all its items out in one row, fits."""
    return header_width_available(window_width) >= needed_width


def row_after(item_count, columns):
    """The index of the row just below the last one that holds items."""
    return -(-item_count // columns)  # the number of rows, rounded up
