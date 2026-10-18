import numpy as np
import pytest
from conftest import SAMPLE_DPI, sample, with_shadow

from id2pdf import detect

# Card A on card.png, measured once by hand: centre in mm and angle of its long side.
CARD_CENTRE_MM = (96.7, 75.3)
CARD_ANGLE = -7.3


def mm(px: float) -> float:
    return detect.px_to_mm(px, SAMPLE_DPI)


def test_an_empty_glass_has_no_card():
    assert detect.find_cards(sample("empty.png"), SAMPLE_DPI, glass=True) == []


def test_a_turned_card_is_found_with_its_size_and_angle():
    cards = detect.find_cards(sample("card.png"), SAMPLE_DPI, glass=True)
    assert len(cards) == 1
    (cx, cy), size, angle = cards[0]
    long, short = sorted(size, reverse=True)
    assert mm(long) == pytest.approx(85.6, rel=0.04)  # a paper card cut with scissors
    assert mm(short) == pytest.approx(54.0, rel=0.04)
    assert angle == pytest.approx(CARD_ANGLE, abs=0.5)
    assert (mm(cx), mm(cy)) == pytest.approx(CARD_CENTRE_MM, abs=1.0)


def test_two_cards_are_both_found_also_a_very_pale_one():
    cards = detect.find_cards(sample("two_cards.png"), SAMPLE_DPI, glass=True)
    assert len(cards) == 2
    assert sorted(round(mm(c[0][1])) for c in cards) == pytest.approx([30, 103], abs=2)


@pytest.mark.parametrize(("depth", "width_mm"), [(30, 6), (60, 9), (70, 11)])
def test_the_shadow_of_a_thick_card_is_left_out(depth, width_mm):
    shadowed = with_shadow(sample("card.png"), depth, width_mm)
    blob = detect.card_candidates(shadowed, SAMPLE_DPI, glass=True)[0][0]
    assert mm(max(blob[1])) > 90  # the shadow makes the object much larger than the card
    (cx, cy), size, angle = detect.find_cards(shadowed, SAMPLE_DPI, glass=True)[0]
    assert mm(max(size)) == pytest.approx(85.6, rel=0.04)
    assert angle == pytest.approx(CARD_ANGLE, abs=0.5)
    assert (mm(cx), mm(cy)) == pytest.approx(CARD_CENTRE_MM, abs=1.0)


def test_a_cut_out_card_is_straight_with_white_corners():
    image = sample("card.png")
    card = detect.cut_out(image, detect.find_cards(image, SAMPLE_DPI, glass=True)[0])
    assert card.width / card.height == pytest.approx(85.6 / 54, rel=0.03)
    assert card.getpixel((0, 0)) == (255, 255, 255)
    assert card.getpixel((card.width - 1, card.height - 1)) == (255, 255, 255)
    # Straight: the dark photo's left edge is at the same x at its top and its bottom.
    gray = np.array(card.convert("L"))
    rows = [round(card.height * 0.3), round(card.height * 0.6)]
    start = card.width // 20  # past the card's own grey outline
    edges = [start + int(np.argmax(gray[row, start : card.width // 2] < 160)) for row in rows]
    assert abs(edges[0] - edges[1]) <= 2


def test_a_photo_without_known_resolution_still_gives_the_card():
    card = detect.card_from_image(sample("card.png"))
    assert card.width / card.height == pytest.approx(85.6 / 54, rel=0.1)
    assert card.width < sample("card.png").width / 2
