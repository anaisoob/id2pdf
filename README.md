# id2pdf

Scan both sides of an ID card onto one A4 page, as a PDF: like a photocopy, at real size.

Put the card anywhere on the scanner glass, also a little askew. id2pdf scans the whole glass
quickly, finds the card, scans only that spot at full resolution, straightens it and cuts it out.
Then the same for the back.

| On the glass | The PDF |
|---|---|
| ![A test card lying askew on the scanner glass](https://raw.githubusercontent.com/anaisoob/id2pdf/main/docs/example_glass.png) | ![Both sides straightened on one A4 page](https://raw.githubusercontent.com/anaisoob/id2pdf/main/docs/example_result.png) |

It works with any card of ID-1 size (85.6 × 54 mm): ID cards, driving licences, health
insurance cards, residence permits. Everything happens on your computer.

## Install

Linux with a scanner that SANE supports (`scanimage -L` lists it):

```
uv tool install id2pdf      # or: pipx install id2pdf
```

From a clone of this repository: `uv tool install .`

## Use

```
id2pdf id_card.pdf                                  # scan the front, then the back
id2pdf id_card.pdf --images front.jpg back.jpg      # from existing scans or photos
id2pdf pages.pdf --pages 3                          # three plain A4 pages instead of a card
id2pdf --diagnose ~/id2pdf-diagnose                 # what is found on the glass, as numbers
```

Options: `--device` picks the scanner (default: the first one in `scanimage -L`), `-f` overwrites
the output without asking.

The card's text should be upright on the glass: a slight turn is straightened, but a card upside
down stays upside down.

Messages are in English or Croatian, following `LANGUAGE` / `LANG`.

## How the card is found

- A quick scan of the whole glass at 100 dpi. The card shows as sharp edges (its outline and
  print) and areas clearly darker than the lid; the lid's own shading is gradual and only
  slightly darker, and dust is too small to make a card shape.
- A plastic card lifts the lid, which casts a shadow up to about 10 mm wide around it. Inside the
  object found, a rectangle of the card's exact size is placed on the sharpest edges: the card's
  edge is a sharp step, the shadow a soft one. Every side has to lie on an edge.
- Only that spot is scanned at 300 dpi, the card is found again there, straightened, cut out, and
  the lid showing at its rounded corners is painted white.
- A network scanner that is still busy from the previous scan is asked again a few times.

If a card is not found, `--diagnose` prints the size and position of every object on the glass
and why it was not taken for a card; the scan itself is saved only locally.

### In photos

With `--images`, the card can also be photographed with a phone, at a slant and on any
background:

- The card's sides are looked for as straight lines through the photo's edges. A line made of
  one long piece counts more than one made of many short pieces, as rows of text are.
- Of the quadrilaterals four such lines make, those with a card's proportions are kept. Seen
  at a slant, a card looks longer or shorter than it is; its real proportions are worked out
  for the lens of a typical phone camera.
- The winner lies on edges all round, separates clearly different colours on every side and
  is full of fine print, as a card is and a wall or a door seen through the same lines is not.
  If the winner is doubtful (a low score, or another place in the photo nearly as good), no
  card is reported rather than a wrong one, and the whole image is used, which is plain to
  see. A scan saved as a file is searched like a scan when this finds nothing.
- The card is then straightened to its real proportions, its rounded corners painted white.

On the ID-card photos of [MIDV-2020](https://arxiv.org/abs/2107.00396), a public dataset of mock
identity documents, 71 % of the cards are found and about 1 % wrongly; on a table, in low
light or with highlights nearly all, on a printed page full of text hardly any. Scans saved
as files are found 94 % of the time, never wrongly. `tools/evaluate_midv.py` measures this.

## Use as a library

```python
from pathlib import Path

import id2pdf

id2pdf.set_language("hr")
device = id2pdf.find_scanner()
page = id2pdf.scan_id_card(device)  # a PIL image of the A4 page
id2pdf.save_pdf([page], Path("id.pdf"), id2pdf.CARD_DPI)
```

## Development

```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
./tools/update_translations.sh                  # after changing messages; needs gettext
uv run tools/test_cards.py                      # docs/test_cards.pdf
uv run tools/evaluate_midv.py FOLDER photo      # card detection on MIDV-2020; see the script
uv run tools/cut_out_cards.py FOLDER            # every image's card into FOLDER/id2pdf
```

The tests run on real scans of the whole glass of an Epson XP-255 (`tests/data`), made with the
printed test cards from `docs/test_cards.pdf`, and on the same scans with a simulated shadow;
scanning goes through a fake `scanimage`. The photos are of mock documents from MIDV-2020
(`tests/data/README.md`). Please never add scans or photos of real cards.

Translations: `src/id2pdf/locale/<language>/LC_MESSAGES/id2pdf.po`.

## Help: send scans from your scanner

id2pdf has been tuned on one scanner so far. Scanners differ in the colour of the lid, its
shading, the shadows along the glass and how much a card lifts the lid, so scans from other
models help most. No real card is needed, and none should ever be sent:

1. Print [docs/test_cards.pdf](https://github.com/anaisoob/id2pdf/blob/main/docs/test_cards.pdf)
   at 100 % (no "fit to page"; the line at the top must be exactly 100 mm) and cut out both
   cards, on thick paper or card if you have it.
2. Scan the whole glass three times at 100 dpi, with the lid closed:

   ```
   scanimage --mode Color --resolution 100 --format=png > empty.png       # nothing on the glass
   scanimage --mode Color --resolution 100 --format=png > card.png        # card A anywhere, a little askew
   scanimage --mode Color --resolution 100 --format=png > two_cards.png   # cards A and B, apart
   ```

3. Optionally, with your real card on the glass, run `id2pdf --diagnose` and copy only the text
   it prints: sizes and positions, nothing from the card. Do not send the scan it saves.
4. Open an issue with the three images, the text from step 3, the scanner's line from
   `scanimage -L` (model and SANE backend) and whether id2pdf found your card.

If id2pdf does not find a card or cuts it wrongly, the same three scans are the best bug report.

## Licence

GPL-3.0-or-later, see [LICENSE](https://github.com/anaisoob/id2pdf/blob/main/LICENSE).
