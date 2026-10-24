# Changelog

## 0.2.0

- Cards are found in phone photos too, also at a slant and on a busy background, and
  straightened to their real proportions: `find_card_corners()` and `straighten()`.
  `card_from_image()` uses them when the resolution is not known.
- `--images` says when it finds no card in an image instead of silently using the whole image.
- `tools/evaluate_midv.py` measures card detection on the public MIDV-2020 dataset.

## 0.1.0

- First version: both sides of an ID-1 card on one A4 page, the card anywhere on the glass,
  found also inside the shadow a thick card casts, straightened and cut out.
- `--images` for existing scans or photos, `--pages N` for plain A4 pages, `--diagnose` to see
  what is found on the glass.
- Messages in English and Croatian.
