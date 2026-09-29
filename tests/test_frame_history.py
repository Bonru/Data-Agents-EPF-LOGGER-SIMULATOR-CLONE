"""The chart history model: the last 30 Frames. Pure Python: no Qt anywhere in these tests."""
import time

from datalogger_client.core.frame import Frame
from datalogger_client.core.frame_history import FRAME_HISTORY_LENGTH, FrameHistory, seconds_to_hms
from datalogger_client.core.registry import channel_named

WIND = channel_named("velocidade_vento")
HUMIDITY = channel_named("umidade_ar")


def frame(wind=None, humidity=None, timestamp=3725, received_at=0.0):
    readings = {}
    if wind is not None:
        readings["velocidade_vento"] = wind
    if humidity is not None:
        readings["umidade_ar"] = humidity
    return Frame(readings, timestamp, received_at)


def local_hms(year_month_day_hour_min_sec):
    return time.mktime((*year_month_day_hour_min_sec, 0, 0, -1))


def test_it_keeps_the_last_30_frames():
    history = FrameHistory()

    for i in range(45):
        history.append(frame(wind=float(i)))

    assert FRAME_HISTORY_LENGTH == 30
    assert len(history) == 30
    assert history.readings(WIND) == [float(i) for i in range(15, 45)]


def test_frames_are_ordered_oldest_first():
    history = FrameHistory()

    history.append(frame(wind=1.0, timestamp=100))
    history.append(frame(wind=2.0, timestamp=102))
    history.append(frame(wind=3.0, timestamp=104))

    assert history.readings(WIND) == [1.0, 2.0, 3.0]
    assert history.time_labels() == ["00:01:40", "00:01:42", "00:01:44"]


def test_it_starts_empty():
    history = FrameHistory()

    assert len(history) == 0
    assert history.readings(WIND) == []
    assert history.time_labels() == []


def test_a_channel_with_no_reading_in_a_frame_is_skipped_never_zero():
    history = FrameHistory()
    history.append(frame(wind=1.0, humidity=40.0))
    history.append(frame(wind=2.0))  # humidity could not be read
    history.append(frame(wind=3.0, humidity=42.0))

    assert history.readings(HUMIDITY) == [40.0, None, 42.0]  # None marks the hole; never 0
    assert 0 not in history.readings(HUMIDITY)
    assert history.readings(WIND) == [1.0, 2.0, 3.0]


def test_a_real_zero_reading_is_kept():
    history = FrameHistory()
    history.append(frame(wind=0.0))

    assert history.readings(WIND) == [0.0]


def test_the_time_axis_is_the_frame_timestamp_as_hh_mm_ss():
    history = FrameHistory()

    history.append(frame(timestamp=3725))
    history.append(frame(timestamp=86399))

    assert history.time_labels() == ["01:02:05", "23:59:59"]


def test_without_a_timestamp_the_time_axis_falls_back_to_the_receive_time():
    history = FrameHistory()

    history.append(frame(timestamp=None, received_at=local_hms((2025, 1, 1, 13, 14, 15))))

    assert history.time_labels() == ["13:14:15"]


def test_the_timestamp_wins_over_the_receive_time_when_both_exist():
    history = FrameHistory()

    history.append(frame(timestamp=3725, received_at=local_hms((2025, 1, 1, 13, 14, 15))))

    assert history.time_labels() == ["01:02:05"]


def test_the_version_changes_with_every_frame_so_charts_can_tell_what_they_drew():
    history = FrameHistory()
    before = history.version

    history.append(frame(wind=1.0))
    after_one = history.version
    history.append(frame(wind=2.0))

    assert before != after_one != history.version


def test_seconds_to_hms():
    assert seconds_to_hms(0) == "00:00:00"
    assert seconds_to_hms(3725) == "01:02:05"
