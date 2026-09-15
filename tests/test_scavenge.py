import pytest

from avgme.bot import Bot
from avgme.tasks.scavenge import ScavengeTask
from avgme.vision import Template
from conftest import sprite
from fake_adb import Element, FakeAdb

HOME = sprite(size=40, color=(120, 60, 200))
ENTRY = sprite(size=32, color=(210, 170, 30))
SCREEN = sprite(size=36, color=(60, 160, 210))
CLAIM = sprite(size=28, color=(40, 200, 90))
DISPATCH = sprite(size=28, color=(200, 90, 40))
CONFIRM = sprite(size=30, color=(240, 240, 60))

CONFIG = {
    "humanize": {"tap_box_ratio": 0.6, "tap_delay": [0.0, 0.0], "interval_jitter": 0.0},
    "recovery": {"max_attempts": 4, "settle_seconds": 0.0},
}

TEMPLATES = {
    "home/anchor_base": Template("home/anchor_base", HOME, 0.9),
    "home/scavenge_entry": Template("home/scavenge_entry", ENTRY, 0.9),
    "scavenge/anchor": Template("scavenge/anchor", SCREEN, 0.9),
    "scavenge/claim": Template("scavenge/claim", CLAIM, 0.9),
    "scavenge/dispatch": Template("scavenge/dispatch", DISPATCH, 0.9),
    "scavenge/confirm": Template("scavenge/confirm", CONFIRM, 0.9),
}


@pytest.fixture(autouse=True)
def no_sleeping(monkeypatch):
    monkeypatch.setattr("avgme.bot.sleep", lambda *a, **k: None)
    monkeypatch.setattr("time.sleep", lambda *a, **k: None)


class Game:
    """Enough of the scavenge UI to drive the task: a home screen with an entry
    button, and a menu whose slots are claimable then dispatchable."""

    def __init__(self, background, claimable=0, idle=0, confirm_step=True):
        self.home = [Element("home/anchor_base", HOME, 40, 40),
                     Element("home/scavenge_entry", ENTRY, 300, 800)]
        self.confirm_step = confirm_step
        self.claimed = 0
        self.dispatched = 0
        self.menu = [Element("scavenge/anchor", SCREEN, 60, 60)]
        for i in range(claimable):
            self.menu.append(Element("scavenge/claim", CLAIM, 400, 200 + i * 100))
        for i in range(idle):
            self.menu.append(Element("scavenge/dispatch", DISPATCH, 400, 500 + i * 100))

        self.adb = FakeAdb(background=background, elements=list(self.home))
        self.adb.on_tap = self._handle
        self.bot = Bot(self.adb, TEMPLATES, CONFIG, debug_dir=None)

    def _show(self, elements):
        self.adb.elements = list(elements)

    def _handle(self, fake, hit):
        if hit.name == "home/scavenge_entry":
            self._show(self.menu)
        elif hit.name == "scavenge/claim":
            self.claimed += 1
            self.menu.remove(hit)
            self._show(self.menu)
        elif hit.name == "scavenge/dispatch":
            self.dispatched += 1
            self.menu.remove(hit)
            if self.confirm_step:
                self._show([Element("scavenge/confirm", CONFIRM, 700, 450)])
            else:
                self._show(self.menu)
        elif hit.name == "scavenge/confirm":
            self._show(self.menu)


def run(game):
    return ScavengeTask({"max_slots": 6}, CONFIG["humanize"]).run(game.bot)


def test_claims_finished_runs_and_refills_idle_slots(background):
    game = Game(background, claimable=2, idle=3)

    result = run(game)

    assert result.ok
    assert game.claimed == 2
    assert game.dispatched == 3
    assert result.detail == "claimed 2, dispatched 3"
    assert result.actions == 5


def test_handles_a_menu_with_nothing_to_do(background):
    game = Game(background)

    result = run(game)

    assert result.ok
    assert result.detail == "nothing to do"
    assert result.actions == 0


def test_works_when_the_game_skips_the_confirm_dialog(background):
    game = Game(background, idle=2, confirm_step=False)

    result = run(game)

    assert result.ok
    assert game.dispatched == 2


def test_fails_cleanly_when_the_entry_button_is_missing(background, tmp_path):
    game = Game(background)
    game.adb.elements = [Element("home/anchor_base", HOME, 40, 40)]  # no entry button
    game.bot.debug_dir = tmp_path

    result = run(game)

    assert result.ok is False
    assert "could not open" in result.detail
    assert list(tmp_path.glob("*scavenge-entry-missing.png"))


def test_returns_to_the_home_screen_when_done(background):
    game = Game(background, claimable=1)
    # Back from the menu lands on home.
    game.adb.back = lambda: game._show(game.home)

    run(game)

    assert game.bot.find("home/anchor_base", fresh=True) is not None
