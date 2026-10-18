"""Finding ID-1 cards (85.6 x 54 mm: ID cards, driving licences, ...) on scans."""

import cv2
import numpy as np
from PIL import Image, ImageDraw

CARD_MM = (85.6, 54.0)
CARD_CORNER_MM = 3.18
PREVIEW_DPI = 100  # quick scan of the whole glass to find the card
DARKER = 15  # grey levels below the lid that count as part of a card (the lid's shading is less)
GLASS_EDGE_MM = 2  # strip along the edges of the glass ignored when looking for the card

Rect = tuple[tuple[float, float], tuple[float, float], float]  # cv2.minAreaRect: centre, size, angle

# Why card_candidates() did not take an object for a card.
SHAPE, SIZE, TOO_SMALL = "shape", "size", "too small"


def mm_to_px(mm: float, dpi: float) -> int:
    return round(mm / 25.4 * dpi)


def px_to_mm(px: float, dpi: float) -> float:
    return px / dpi * 25.4


def card_candidates(image: Image.Image, dpi: float | None, glass: bool = False) -> list[tuple[Rect, str]]:
    """Every object on a scan with why it is not a card ("" = it is one), largest first.

    A card shows as sharp edges (its outline and shadow, its print) and areas clearly darker
    than the lid; the lid's shading is gradual and only slightly darker, and dust is too
    small to make a card shape. glass: the image is the whole glass, whose edges are ignored.
    dpi None skips the size check (photos).
    """
    gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    smooth = cv2.GaussianBlur(gray, (5, 5), 0)
    lid = float(np.median(gray))
    mask = ((cv2.Canny(smooth, 20, 60) > 0) | (smooth < lid - DARKER)).astype(np.uint8) * 255
    if glass:
        edge = mm_to_px(GLASS_EDGE_MM, dpi or PREVIEW_DPI)
        mask[:edge, :] = mask[-edge:, :] = 0
        mask[:, :edge] = mask[:, -edge:] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    k = max(3, mm_to_px(1.5, dpi or PREVIEW_DPI))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found = []
    for contour in contours:
        rect = cv2.minAreaRect(cv2.convexHull(contour))
        long, short = sorted(rect[1], reverse=True)
        if short < 10:
            continue
        reason = ""
        # A thick card lifts the lid: its shadow makes the object up to ~10 mm larger all round.
        if abs(long / short - CARD_MM[0] / CARD_MM[1]) > 0.25:
            reason = SHAPE
        elif dpi is not None and not 0.85 < long / mm_to_px(CARD_MM[0], dpi) < 1.45:
            reason = SIZE
        elif dpi is None and long * short < 0.05 * gray.size:
            reason = TOO_SMALL
        found.append((rect, reason))
    return sorted(found, key=lambda c: -c[0][1][0] * c[0][1][1])


def perimeter(width: float, height: float, corner: float, spacing: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """For each straight side of a width x height rectangle centred on 0: its points and normal."""
    xs = np.arange(-width / 2 + corner, width / 2 - corner, spacing)
    ys = np.arange(-height / 2 + corner, height / 2 - corner, spacing)
    return [
        (np.stack([xs, np.full_like(xs, -height / 2)], 1), np.array([0.0, 1.0])),
        (np.stack([xs, np.full_like(xs, height / 2)], 1), np.array([0.0, 1.0])),
        (np.stack([np.full_like(ys, -width / 2), ys], 1), np.array([1.0, 0.0])),
        (np.stack([np.full_like(ys, width / 2), ys], 1), np.array([1.0, 0.0])),
    ]


def fit_card(gray: np.ndarray, blob: Rect, dpi: float) -> Rect:
    """The card inside an object found on the scan, which may include the card's shadow.

    Places a card-sized rectangle (within 3 %) on the sharpest edges near the object: the
    card's edge is a sharp step, its shadow a soft one. Every side has to lie on an edge, so
    the score is the weakest side's mean sharpness across it, blurred a little so that a
    slightly misplaced edge still counts. The angle comes from the object, whose shadow is
    about even all round; on edges alone it is poorly determined.
    """
    smooth = cv2.GaussianBlur(gray, (3, 3), 0).astype(np.float32)
    sigma = max(1.0, mm_to_px(0.3, dpi))
    across_x = cv2.GaussianBlur(np.abs(cv2.Sobel(smooth, cv2.CV_32F, 1, 0)), (0, 0), sigma)
    across_y = cv2.GaussianBlur(np.abs(cv2.Sobel(smooth, cv2.CV_32F, 0, 1)), (0, 0), sigma)
    card_w, card_h = (mm_to_px(mm, dpi) for mm in CARD_MM)
    corner = mm_to_px(CARD_CORNER_MM + 0.5, dpi)
    spacing = max(1.0, dpi / 100)
    (cx, cy), (w, h), angle = blob
    if w < h:
        w, h, angle = h, w, angle + 90
    angle = (angle + 90) % 180 - 90
    rows, cols = gray.shape

    def best(angles, xs, ys, scales):
        top = (-1.0, cx, cy, angle, 1.0, 1.0)
        for a in angles:
            t = np.deg2rad(a)
            turn = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
            for sx in scales:
                for sy in scales:
                    weakest = None
                    for points, normal in perimeter(card_w * sx, card_h * sy, corner, spacing):
                        r = points @ turn.T
                        nx, ny = np.abs(turn @ normal)
                        gx = np.clip(np.rint(xs[:, None, None] + r[None, None, :, 0]).astype(int), 0, cols - 1)
                        gy = np.clip(np.rint(ys[None, :, None] + r[None, None, :, 1]).astype(int), 0, rows - 1)
                        side = (across_x[gy, gx] * nx + across_y[gy, gx] * ny).mean(axis=2)
                        weakest = side if weakest is None else np.minimum(weakest, side)
                    i, j = np.unravel_index(np.argmax(weakest), weakest.shape)
                    if weakest[i, j] > top[0]:
                        top = (float(weakest[i, j]), float(xs[i]), float(ys[j]), float(a), sx, sy)
        return top

    step = max(1, mm_to_px(0.5, dpi))
    span_x = max(0.0, (w - card_w) / 2) + mm_to_px(2, dpi)
    span_y = max(0.0, (h - card_h) / 2) + mm_to_px(2, dpi)
    _, x, y, a, _, _ = best(
        np.array([angle]),
        np.arange(cx - span_x, cx + span_x + 1, step),
        np.arange(cy - span_y, cy + span_y + 1, step),
        (1.0,),
    )
    fine = max(1.0, step / 3)
    _, x, y, a, sx, sy = best(
        np.arange(a - 0.5, a + 0.51, 0.25),
        np.arange(x - step, x + step + 1, fine),
        np.arange(y - step, y + step + 1, fine),
        np.arange(0.97, 1.031, 0.01),
    )
    return (x, y), (card_w * sx, card_h * sy), a


def find_cards(image: Image.Image, dpi: float | None, glass: bool = False) -> list[Rect]:
    """Cards on a scan, largest first; with a known dpi each is fitted to the card's real edges."""
    blobs = [rect for rect, reason in card_candidates(image, dpi, glass) if not reason]
    if dpi is None:
        return blobs
    gray = np.array(image.convert("L"))
    return [fit_card(gray, blob, dpi) for blob in blobs]


def cut_out(image: Image.Image, rect: Rect) -> Image.Image:
    """The card straightened (long side horizontal), with white at its rounded corners."""
    (cx, cy), (w, h), angle = rect
    if w < h:  # make the angle the one of the long side
        w, h, angle = h, w, angle + 90
    angle = (angle + 90) % 180 - 90  # the smallest turn that makes the long side horizontal
    turn = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    turn[0, 2] += w / 2 - cx
    turn[1, 2] += h / 2 - cy
    card = cv2.warpAffine(
        np.array(image.convert("RGB")),
        turn,
        (round(w), round(h)),
        flags=cv2.INTER_CUBIC,
        borderValue=(255, 255, 255),
    )
    card = Image.fromarray(card)
    outline = Image.new("L", card.size, 0)
    radius = round(CARD_CORNER_MM / CARD_MM[1] * card.height)
    ImageDraw.Draw(outline).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=radius, fill=255)
    return Image.composite(card, Image.new("RGB", card.size, "white"), outline)


def card_from_image(image: Image.Image, dpi: float | None = None) -> Image.Image:
    """The card cut out of a scan or photo, or the image as it is if no card is found."""
    cards = find_cards(image, dpi)
    return cut_out(image, cards[0]) if cards else image
