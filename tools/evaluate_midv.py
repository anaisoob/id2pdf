"""How well cards are found in MIDV-2020, a public dataset of mock identity documents.

MIDV-2020 (ftp://smartengines.com/midv-2020, CC BY-SA 2.5) has photos and scans of ID cards
with their corners marked by hand. Download dataset/photo.tar and dataset/scan_rotated.tar,
unpack them into one folder, then:

    uv run tools/evaluate_midv.py FOLDER photo         # photos, as Choose image... gets them
    uv run tools/evaluate_midv.py FOLDER scan          # scans, as the scanner gets them
    uv run tools/evaluate_midv.py FOLDER scan --file   # scans opened as files

A card counts as found when its outline covers the marked one by 90 % (intersection over union).
"""

import argparse
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

import id2pdf
from id2pdf import detect, scanner

ID1_CARDS = ["alb_id", "esp_id", "est_id", "fin_id", "svk_id"]  # the passports are larger
SCAN_DPI = 300
CONDITIONS = {  # by photo number, both phones (MIDV-2020 readme)
    "projective": range(0, 20),
    "text docs": range(20, 30),
    "keyboard": range(30, 40),
    "outdoors": range(40, 50),
    "table": range(50, 60),
    "highlight": range(60, 70),
    "low light": range(70, 90),
    "cloth": range(90, 100),
}


def marked(folder: Path):
    """(image path, marked corners) for every ID-1 card."""
    for code in ID1_CARDS:
        meta = json.loads((folder / "annotations" / f"{code}.json").read_text())["_via_img_metadata"]
        for item in meta.values():
            for region in item["regions"]:
                if region["region_attributes"].get("field_name") == "doc_quad":
                    shape = region["shape_attributes"]
                    corners = np.array(list(zip(shape["all_points_x"], shape["all_points_y"], strict=True)), np.float32)
                    yield folder / "images" / code / item["filename"], corners


def overlap(a: np.ndarray, b: np.ndarray, size: tuple[int, int]) -> float:
    """Intersection over union of two outlines."""
    scale = 1000 / max(size)
    canvas = np.zeros((round(size[1] * scale) + 1, round(size[0] * scale) + 1), np.uint8)
    ma, mb = canvas.copy(), canvas.copy()
    cv2.fillPoly(ma, [np.int32(a * scale)], 1)
    cv2.fillPoly(mb, [np.int32(b * scale)], 1)
    union = (ma | mb).sum()
    return float((ma & mb).sum() / union) if union else 0.0


def scanned_corners(glass) -> np.ndarray | None:
    """Like scanner.scan_card_side: a preview of the whole glass, then the card at full resolution."""
    factor = SCAN_DPI / detect.PREVIEW_DPI
    preview = glass.resize((round(glass.width / factor), round(glass.height / factor)))
    cards = detect.find_cards(preview, detect.PREVIEW_DPI, glass=True)
    if not cards:
        return None
    corners = cv2.boxPoints(cards[0]) * factor
    margin = detect.mm_to_px(scanner.CARD_MARGIN_MM, SCAN_DPI)
    left, top = (max(0, int(v - margin)) for v in corners.min(0))
    right, bottom = (int(v + margin) for v in corners.max(0))
    detail = glass.crop((left, top, min(glass.width, right), min(glass.height, bottom)))
    found = detect.find_cards(detail, SCAN_DPI)
    return cv2.boxPoints(found[0]) + (left, top) if found else corners


def measure(job: tuple[Path, np.ndarray, bool]) -> tuple[Path, float]:
    path, corners, as_scan = job
    image = id2pdf.open_image(path)  # the photos need their EXIF rotation, like the marks
    found = scanned_corners(image) if as_scan else id2pdf.find_card_corners(image)
    return path, overlap(found, corners, image.size) if found is not None else 0.0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("folder", type=Path, help="where photo.tar and scan_rotated.tar are unpacked")
    p.add_argument("kind", choices=["photo", "scan"])
    p.add_argument("--file", action="store_true", help="open scans as image files instead of scanning")
    args = p.parse_args()
    folder = args.folder / ("photo" if args.kind == "photo" else "scan_rotated")
    jobs = [(path, corners, args.kind == "scan" and not args.file) for path, corners in marked(folder)]
    with ProcessPoolExecutor() as pool:
        results = list(pool.map(measure, jobs, chunksize=4))

    def grade(iou: float) -> str:
        return "found" if iou >= 0.9 else "roughly" if iou >= 0.75 else "wrong" if iou > 0 else "not found"

    counts = Counter(grade(iou) for _, iou in results)
    print(f"{len(results)} cards: " + ", ".join(f"{g} {counts[g]}" for g in ("found", "roughly", "wrong", "not found")))
    if args.kind == "photo":
        for name, numbers in CONDITIONS.items():
            subset = [iou for path, iou in results if int(path.stem) in numbers]
            print(f"  {name:11} found {sum(iou >= 0.9 for iou in subset):3} of {len(subset)}")


if __name__ == "__main__":
    main()
