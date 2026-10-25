import numpy as np
import pytest
from conftest import SAMPLE_DPI, sample, with_shadow

from id2pdf import detect

# Card A on card.png, measured once by hand: centre in mm and angle of its long side.
CARD_CENTRE_MM = (96.7, 75.3)
CARD_ANGLE = -7.3

# Corners of the cards in the photos from MIDV-2020, as marked there, from the card's top left.
PHOTOS = {
    "photo_table.jpg": [(89, 732), (547, 726), (607, 1030), (57, 1064)],
    "photo_hand.jpg": [(78, 342), (521, 348), (543, 620), (95, 643)],
    "photo_slant.jpg": [(99, 614), (608, 601), (559, 810), (133, 832)],
    "photo_dark.jpg": [(63, 493), (517, 422), (563, 714), (103, 778)],
    # On a printed page and a white keyboard the card is found only by its colour.
    "photo_page.jpg": [(149, 487), (514, 519), (538, 736), (127, 720)],
    "photo_keyboard.jpg": [(60, 744), (627, 746), (650, 1124), (42, 1139)],
}


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


@pytest.mark.parametrize("name", PHOTOS)
def test_a_card_is_found_in_a_photo_with_its_corners_in_order(name):
    corners = detect.find_card_corners(sample(name))
    marked = np.array(PHOTOS[name], np.float32)
    width = np.linalg.norm(marked[1] - marked[0])
    assert np.linalg.norm(corners - marked, axis=1).max() < 0.03 * width


def test_a_photo_without_a_card_gives_no_corners():
    assert detect.find_card_corners(sample("photo_no_card.jpg")) is None
    assert detect.find_card_corners(sample("empty.png")) is None


def test_a_card_seen_at_a_slant_is_straightened_to_a_card():
    image = sample("photo_slant.jpg")
    card = detect.straighten(image, detect.find_card_corners(image))
    assert card.width / card.height == pytest.approx(85.6 / 54, rel=0.01)
    assert card.getpixel((0, 0)) == (255, 255, 255)
    # The same as straightened by the marked corners.
    marked = detect.straighten(image, np.array(PHOTOS["photo_slant.jpg"], np.float32)).resize(card.size)
    difference = np.abs(np.array(card, np.float32) - np.array(marked, np.float32)).mean()
    assert difference < 12


def test_a_scan_opened_as_a_file_is_found_like_a_photo():
    corners = detect.find_card_corners(sample("two_cards.png"))
    sides = np.linalg.norm(corners - np.roll(corners, -1, 0), axis=1)
    assert detect.px_to_mm(sides[0], SAMPLE_DPI) == pytest.approx(85.6, rel=0.04)
    assert detect.px_to_mm(sides[1], SAMPLE_DPI) == pytest.approx(54, rel=0.04)
