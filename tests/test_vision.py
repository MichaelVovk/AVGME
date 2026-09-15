import numpy as np

from avgme.vision import Template, find, find_all, find_first, load_templates
from conftest import paste, sprite


def test_finds_a_single_match_at_the_right_place(background, badge, badge_template):
    paste(background, badge, 700, 400)

    match = find(background, badge_template)

    assert match is not None
    assert (match.x, match.y) == (700, 400)
    assert match.center == (700 + badge.shape[1] // 2, 400 + badge.shape[0] // 2)
    assert match.score > 0.99


def test_finds_every_copy_without_double_counting(background, badge, badge_template):
    spots = [(100, 100), (500, 300), (1200, 700)]
    for x, y in spots:
        paste(background, badge, x, y)

    matches = find_all(background, badge_template)

    assert len(matches) == 3
    assert sorted((m.x, m.y) for m in matches) == sorted(spots)


def test_returns_nothing_when_the_element_is_absent(background, badge_template):
    assert find(background, badge_template) is None
    assert find_all(background, badge_template) == []


def test_threshold_rejects_a_near_miss(background, badge):
    paste(background, badge, 300, 300)
    different = sprite(color=(200, 40, 220))

    strict = Template(name="other", image=different, threshold=0.95)

    assert find(background, strict) is None


def test_find_first_picks_the_best_scoring_template(background, badge):
    paste(background, badge, 250, 250)
    absent = sprite(color=(5, 5, 250))
    templates = {
        "a": Template("a", absent, 0.87),
        "b": Template("b", badge, 0.87),
    }

    match = find_first(background, templates, ["a", "b"])

    assert match is not None
    assert match.template == "b"


def test_oversized_template_is_ignored_rather_than_crashing(badge_template):
    tiny = np.zeros((10, 10, 3), dtype=np.uint8)

    assert find_all(tiny, badge_template) == []


def test_templates_load_keyed_by_subdirectory(tmp_path, badge):
    import cv2

    (tmp_path / "home").mkdir()
    (tmp_path / "common").mkdir()
    cv2.imwrite(str(tmp_path / "home" / "anchor_base.png"), badge)
    cv2.imwrite(str(tmp_path / "common" / "close_x@0.93.png"), badge)

    templates = load_templates(tmp_path, threshold=0.87)

    assert set(templates) == {"home/anchor_base", "common/close_x"}
    assert templates["home/anchor_base"].threshold == 0.87
    assert templates["common/close_x"].threshold == 0.93


def test_missing_template_directory_is_empty_not_an_error(tmp_path):
    assert load_templates(tmp_path / "nope", threshold=0.87) == {}
