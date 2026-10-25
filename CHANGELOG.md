# Changelog

## Unreleased

- When no card is found in a photo, it is looked for again by its colour: a coloured card on a
  printed page or a white keyboard, whose edges are lost among the print's. On the MIDV-2020
  photos 79 % of the cards are found instead of 69 %, still under 1 % wrongly; no card found
  before is lost.

## 0.2.1

- Messages in German, French, Italian and Spanish too.

## 0.2.0

- Cards are found in phone photos too, also at a slant and on a busy background, and
  straightened to their real proportions: `find_card_corners()` and `straighten()`.
  `card_from_image()` uses them when the resolution is not known.
- A doubtful card in a photo is reported as none rather than cut out wrongly: on MIDV-2020,
  seven in ten cards are found and under 1 % wrongly.
- `--images` says when it finds no card in an image instead of silently using the whole image.
- `tools/evaluate_midv.py` measures card detection on the public MIDV-2020 dataset.
- `tools/cut_out_cards.py` cuts the card out of every image in a folder, to look through.

## 0.1.0

- First version: both sides of an ID-1 card on one A4 page, the card anywhere on the glass,
  found also inside the shadow a thick card casts, straightened and cut out.
- `--images` for existing scans or photos, `--pages N` for plain A4 pages, `--diagnose` to see
  what is found on the glass.
- Messages in English and Croatian.
