"""The rules of the responsive layout. Pure Python: no Qt anywhere in these tests."""
import pytest

from datalogger_client.ui.layout import (
    CONTENT_STRETCH,
    DEFAULT_WINDOW_SIZE,
    HEADER_FIT_SLACK,
    MAX_COLUMNS,
    MIN_COLUMNS,
    MINIMUM_WINDOW_SIZE,
    OUTER_MARGIN,
    OUTER_SPACING,
    SIDEBAR_MIN_WIDTH,
    SIDEBAR_STRETCH,
    columns_for_width,
    header_fits_one_row,
    header_width_available,
    rows_needed,
)


@pytest.mark.parametrize("width, columns", [
    (400, 1), (800, 1), (839, 1), (840, 2), (1200, 2), (1259, 2), (1260, 3), (1679, 3), (1680, 4), (1920, 4),
])
def test_the_column_count_is_the_window_width_over_420_clamped_to_1_and_4(width, columns):
    assert columns_for_width(width) == columns


def test_the_column_count_is_clamped_at_both_ends():
    assert columns_for_width(0) == MIN_COLUMNS == 1
    assert columns_for_width(50) == 1
    assert columns_for_width(10_000) == MAX_COLUMNS == 4


def test_the_thresholds_are_where_the_ticket_says():
    assert [w for w in range(300, 2000) if columns_for_width(w) != columns_for_width(w - 1)] == [840, 1260, 1680]


def test_the_default_window_is_a_size_not_derived_from_the_screen():
    assert DEFAULT_WINDOW_SIZE == (1200, 800)
    assert columns_for_width(DEFAULT_WINDOW_SIZE[0]) == 2
    assert MINIMUM_WINDOW_SIZE[0] <= 400  # the smallest width the layout is tested at


def test_the_header_gets_what_is_left_beside_the_sidebar_column():
    width = 1200
    content = width - 2 * OUTER_MARGIN - OUTER_SPACING
    sidebar = max(SIDEBAR_MIN_WIDTH, content * SIDEBAR_STRETCH // (SIDEBAR_STRETCH + CONTENT_STRETCH))

    assert header_width_available(width) == content - sidebar


def test_in_a_wide_window_the_sidebar_takes_its_stretch_share_and_in_a_narrow_one_its_minimum():
    wide, narrow = 3000, 400

    around = 2 * OUTER_MARGIN + OUTER_SPACING
    assert header_width_available(wide) == (wide - around) - (wide - around) // 9
    assert header_width_available(narrow) == (narrow - around) - SIDEBAR_MIN_WIDTH


def test_the_header_fits_one_row_only_when_the_space_beside_the_sidebar_is_enough():
    needed = 500
    fits_from = next(w for w in range(300, 3000) if header_fits_one_row(w, needed))

    assert header_width_available(fits_from) >= needed + HEADER_FIT_SLACK > header_width_available(fits_from - 1)
    assert all(header_fits_one_row(w, needed) for w in range(fits_from, 3000))  # and it stays fitting


def test_the_slack_makes_a_borderline_header_stack_rather_than_overflow():
    width = 1200
    borderline = header_width_available(width)  # exactly what the estimate says is available

    assert not header_fits_one_row(width, borderline)
    assert header_fits_one_row(width, borderline - HEADER_FIT_SLACK)


def test_a_bigger_font_needs_a_wider_window_for_one_row():
    assert header_fits_one_row(1200, 400) and not header_fits_one_row(1200, 1100)


def test_row_after_the_last_row_that_holds_items():
    assert rows_needed(21, 1) == 21
    assert rows_needed(21, 2) == 11
    assert rows_needed(21, 3) == 7
    assert rows_needed(21, 4) == 6
