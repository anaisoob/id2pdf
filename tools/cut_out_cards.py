"""Cut the card out of every image in a folder, to look through the results.

For each image, FOLDER/id2pdf/ gets NAME.jpg, the card straightened, or NAME-no-card.jpg,
the image itself, when no card is found:

    uv run tools/cut_out_cards.py FOLDER
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import id2pdf

PREVIEW = 1000  # longest side of a saved image without a card


def cut_out(args: tuple[Path, Path]) -> bool:
    path, out = args
    image = id2pdf.open_image(path)
    corners = id2pdf.find_card_corners(image)
    if corners is None:
        image.thumbnail((PREVIEW, PREVIEW))
        image.save(out / f"{path.stem}-no-card.jpg", quality=85)
        return False
    id2pdf.straighten(image, corners).save(out / f"{path.stem}.jpg", quality=90)
    return True


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("folder", type=Path)
    args = p.parse_args()
    out = args.folder / "id2pdf"
    out.mkdir(exist_ok=True)
    images = sorted(f for f in args.folder.iterdir() if f.suffix.lower() in id2pdf.IMAGE_SUFFIXES)
    with ProcessPoolExecutor() as pool:
        found = list(pool.map(cut_out, [(path, out) for path in images]))
    print(f"{sum(found)} of {len(images)} images with a card, results in {out}")


if __name__ == "__main__":
    main()
