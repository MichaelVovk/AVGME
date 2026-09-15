import numpy as np
import pytest

from avgme.vision import Template


def solid(width, height, color):
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:, :] = color
    return canvas


def sprite(size=24, color=(40, 200, 90)):
    """A distinctive little icon with internal structure.

    Flat colour blocks match everywhere; real UI elements have edges, so the
    test fixtures need them too or TM_CCOEFF_NORMED behaves nothing like it
    does against the game.
    """
    img = solid(size, size, color)
    img[4:8, 4:20] = (255, 255, 255)
    img[10:20, 6:10] = (10, 10, 10)
    img[12:16, 12:22] = (250, 40, 40)
    return img


def paste(screen, patch, x, y):
    h, w = patch.shape[:2]
    screen[y : y + h, x : x + w] = patch
    return screen


@pytest.fixture
def background():
    # Noisy, so nothing matches by accident.
    rng = np.random.default_rng(1234)
    return rng.integers(0, 255, size=(900, 1600, 3), dtype=np.uint8)


@pytest.fixture
def badge():
    return sprite()


@pytest.fixture
def badge_template(badge):
    return Template(name="home/collect_food", image=badge, threshold=0.87)
