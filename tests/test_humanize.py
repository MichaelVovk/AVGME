import time

from avgme.humanize import MIN_DELAY, Session, gaussian_delay, jitter_interval, jitter_point
from avgme.vision import Match


def test_tap_points_stay_inside_the_element_but_vary():
    match = Match("btn", x=100, y=200, w=80, h=40, score=0.99)

    points = {jitter_point(match, 0.6) for _ in range(200)}

    assert len(points) > 20, "taps should not all land on the same pixel"
    for x, y in points:
        assert 100 <= x < 180 and 200 <= y < 240


def test_tap_point_respects_a_zero_ratio():
    match = Match("btn", x=10, y=10, w=4, h=4, score=1.0)

    for _ in range(20):
        x, y = jitter_point(match, 0.0)
        assert 10 <= x < 14 and 10 <= y < 14


def test_delays_are_never_instant():
    assert all(gaussian_delay(0.0, 0.0) >= MIN_DELAY for _ in range(50))
    assert all(gaussian_delay(0.5, 5.0) >= MIN_DELAY for _ in range(200))


def test_intervals_scatter_within_the_configured_spread():
    values = [jitter_interval(600, 0.15) for _ in range(300)]

    assert all(510 <= v <= 690 for v in values)
    assert len(set(values)) > 100


def test_a_disabled_session_is_always_active():
    session = Session(enabled=False, active_minutes=(1, 1), idle_minutes=(1, 1))

    assert session.is_active()
    assert session.seconds_until_active() == 0.0


def test_session_flips_from_active_to_idle_when_the_phase_expires(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    session = Session(enabled=True, active_minutes=(10, 10), idle_minutes=(5, 5))

    assert session.is_active()

    now[0] += 10 * 60 + 1
    assert session.is_active() is False
    assert 0 < session.seconds_until_active() <= 5 * 60

    now[0] += 5 * 60 + 1
    assert session.is_active() is True
