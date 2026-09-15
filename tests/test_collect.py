import numpy as np
import pytest

from avgme.bot import Bot
from avgme.state import at_home, recover_to_home
from avgme.tasks.collect import CollectTask
from avgme.vision import Template
from conftest import sprite
from fake_adb import Element, FakeAdb

ANCHOR = sprite(size=40, color=(120, 60, 200))
BADGE = sprite(size=24, color=(40, 200, 90))
CLOSE = sprite(size=20, color=(20, 20, 220))

CONFIG = {
    "humanize": {"tap_box_ratio": 0.6, "tap_delay": [0.0, 0.0], "interval_jitter": 0.0},
    "recovery": {"max_attempts": 4, "settle_seconds": 0.0},
}


def build(elements, background):
    adb = FakeAdb(background=background, elements=list(elements))
    templates = {
        "home/anchor_base": Template("home/anchor_base", ANCHOR, 0.9),
        "home/collect_food": Template("home/collect_food", BADGE, 0.9),
        "common/close_x": Template("common/close_x", CLOSE, 0.9),
    }
    return adb, Bot(adb, templates, CONFIG, debug_dir=None)


def anchor(x=40, y=40):
    return Element("home/anchor_base", ANCHOR, x, y)


@pytest.fixture(autouse=True)
def no_sleeping(monkeypatch):
    monkeypatch.setattr("avgme.bot.sleep", lambda *a, **k: None)
    monkeypatch.setattr("time.sleep", lambda *a, **k: None)


def test_collects_every_badge_on_screen(background):
    badges = [Element("badge", BADGE, x, 300) for x in (200, 400, 600, 800)]
    adb, bot = build([anchor(), *badges], background)

    result = CollectTask({"max_taps_per_cycle": 25}, CONFIG["humanize"]).run(bot)

    assert result.ok
    assert result.actions == 4
    assert result.detail == "collected 4"
    # Every badge is gone, the anchor was never touched.
    assert [e.name for e in adb.elements] == ["home/anchor_base"]


def test_does_nothing_when_no_badges_are_ready(background):
    adb, bot = build([anchor()], background)

    result = CollectTask({"max_taps_per_cycle": 25}, CONFIG["humanize"]).run(bot)

    assert result.ok
    assert result.actions == 0
    assert result.detail == "nothing ready"
    assert adb.taps == []


def test_taps_land_inside_the_badge(background):
    badge = Element("badge", BADGE, 500, 500)
    adb, bot = build([anchor(), badge], background)

    CollectTask({"max_taps_per_cycle": 25}, CONFIG["humanize"]).run(bot)

    x, y = adb.taps[0]
    assert 500 <= x < 524 and 500 <= y < 524


def test_stops_when_a_popup_swallows_the_home_screen(background):
    """Collecting can trigger a level-up dialog. The task must notice it left
    home and stop, rather than tapping blind into the dialog."""
    badges = [Element("badge", BADGE, x, 300) for x in (200, 400, 600)]
    home = anchor()
    adb, bot = build([home, *badges], background)

    def popup_on_first_collect(fake, hit):
        fake.elements.remove(hit)
        fake.elements.remove(home)  # dialog covers the base screen

    adb.on_tap = popup_on_first_collect

    result = CollectTask({"max_taps_per_cycle": 25}, CONFIG["humanize"]).run(bot)

    assert result.actions == 1
    assert len(adb.taps) == 1


def test_tap_cap_stops_a_template_that_never_clears(background, tmp_path):
    """A badge template matching permanent scenery would otherwise tap forever."""
    stuck = Element("badge", BADGE, 700, 300)
    adb, bot = build([anchor(), stuck], background)
    adb.on_tap = lambda fake, hit: None  # tapping never removes it
    bot.debug_dir = tmp_path

    result = CollectTask({"max_taps_per_cycle": 5}, CONFIG["humanize"]).run(bot)

    assert result.actions == 5
    assert len(adb.taps) == 5


def test_recovery_closes_a_popup_and_returns_home(background):
    close = Element("common/close_x", CLOSE, 900, 100)
    home = anchor()
    adb, bot = build([close], background)  # home is hidden behind the popup

    def reveal_home(fake, hit):
        fake.elements.remove(hit)
        fake.elements.append(home)

    adb.on_tap = reveal_home

    assert not at_home(bot)
    assert recover_to_home(bot) is True
    assert at_home(bot)


def test_recovery_falls_back_to_back_button(background):
    adb, bot = build([], background)  # no home, no close button
    home = anchor()

    def back_goes_home():
        adb.elements.append(home)

    original_back = adb.back

    def tracked_back():
        original_back()
        back_goes_home()

    adb.back = tracked_back

    assert recover_to_home(bot) is True
    assert adb.back_presses == 1


def test_recovery_gives_up_rather_than_flailing(background, tmp_path):
    adb, bot = build([], background)  # nothing will ever bring home back
    bot.debug_dir = tmp_path

    assert recover_to_home(bot) is False
    assert adb.back_presses == CONFIG["recovery"]["max_attempts"]
    assert list(tmp_path.glob("*recovery-failed.png"))


def test_dry_run_records_taps_without_sending_any(background):
    badges = [Element("badge", BADGE, x, 300) for x in (200, 400)]
    adb, bot = build([anchor(), *badges], background)
    bot.dry_run = True

    match = bot.find_prefix("home/collect", fresh=True)[0]
    bot.tap(match)

    assert adb.taps == []
    assert len(bot.take_dry_run_matches()) == 1
