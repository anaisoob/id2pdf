"""Finding ID-1 cards (85.6 x 54 mm: ID cards, driving licences, ...) on scans and photos."""

import itertools

import cv2
import numpy as np
from PIL import Image, ImageDraw

CARD_MM = (85.6, 54.0)
CARD_CORNER_MM = 3.18
PREVIEW_DPI = 100  # quick scan of the whole glass to find the card
DARKER = 15  # grey levels below the lid that count as part of a card (the lid's shading is less)
GLASS_EDGE_MM = 2  # strip along the edges of the glass ignored when looking for the card

# Photos and images of unknown resolution. The numbers were tuned on the photos of ID cards in
# MIDV-2020 (tools/evaluate_midv.py), where seven in ten cards are found and under 1 % wrongly.
PHOTO_WIDTH = 800  # the photo is searched at this size
PHOTO_LINES = 40  # straight lines tried as the card's sides
PHOTO_SHORTLIST = 60  # outlines whose colours are compared, the best placed on edges first
# A doubtful card is reported as none: the whole photo is used then, which is plain to see,
# while a wrong cut-out may pass unnoticed.
PHOTO_MIN_SCORE = 20  # below this, the best outline is doubtful
PHOTO_MARGIN = 1.6  # and also unless it scores this much more than any other place in the photo
PHOTO_ENDS = 0.2  # and unless all its sides but one reach their corners on edges at least this much
PHOTO_PRINT = 0.10  # share of fine edges inside a card from which it counts as fully printed
LENS = 0.8  # a phone camera's focal length, in widths of the photo

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


def _edges(small: np.ndarray) -> np.ndarray:
    """The clearer edges of a photo: in any colour channel, and among the strongest in the photo."""
    blur = cv2.GaussianBlur(small, (0, 0), 2)
    lab = cv2.cvtColor(blur, cv2.COLOR_RGB2LAB)
    channels = cv2.split(lab)
    gx = sum(np.abs(cv2.Sobel(c, cv2.CV_32F, 1, 0)) for c in channels)
    gy = sum(np.abs(cv2.Sobel(c, cv2.CV_32F, 0, 1)) for c in channels)
    strength = np.hypot(gx, gy)
    edges = np.zeros(blur.shape[:2], np.uint8)
    for c in channels:
        edges |= cv2.Canny(c, 20, 50)
    edges[strength < 0.5 * np.percentile(strength, 92)] = 0
    return edges


def _lines(edges: np.ndarray) -> list[tuple[float, float]]:
    """Straight lines (normal angle, distance from the origin) through the edges.

    Longest unbroken piece first: a row of text makes a long line of short pieces, a card's
    side one long piece.
    """
    segments = cv2.HoughLinesP(edges, 1, np.pi / 360, threshold=30, minLineLength=30, maxLineGap=4)
    if segments is None:
        return []
    found = []  # [angle, distance, longest piece]
    for x1, y1, x2, y2 in segments.reshape(-1, 4).astype(float):
        angle = np.arctan2(x2 - x1, -(y2 - y1)) % np.pi
        distance = x1 * np.cos(angle) + y1 * np.sin(angle)
        length = np.hypot(x2 - x1, y2 - y1)
        for line in found:
            if abs(line[0] - angle) < np.deg2rad(2.5) and abs(line[1] - distance) < 6:
                line[2] = max(line[2], length)
                break
        else:
            found.append([angle, distance, length])
    found.sort(key=lambda line: -line[2])
    return [(angle, distance) for angle, distance, _ in found[:PHOTO_LINES]]


def _crossing(a: tuple[float, float], b: tuple[float, float]) -> np.ndarray | None:
    m = np.array([[np.cos(a[0]), np.sin(a[0])], [np.cos(b[0]), np.sin(b[0])]])
    if abs(np.linalg.det(m)) < 1e-6:
        return None
    return np.linalg.solve(m, [a[1], b[1]])


def _turn(a: float, b: float) -> float:
    """The angle between two lines' directions, 0 to 90 degrees, in radians."""
    d = abs(a - b) % np.pi
    return min(d, np.pi - d)


def _ratio(quad: np.ndarray, size: tuple[int, int]) -> float:
    """Width / height (first side / second side) of the rectangle a photo shows as quad.

    Perspective makes a card seen at a slant look longer or shorter than it is. With the focal
    length of a typical phone camera assumed, Zhang & He, "Whiteboard scanning and image
    enhancement" (2007), gives the real ratio back.
    """
    w, h = size
    f = LENS * max(w, h)
    m1, m2, m4, m3 = np.hstack([quad - (w / 2, h / 2), np.ones((4, 1))])  # corners in order round
    k2 = np.dot(np.cross(m1, m4), m3) / np.dot(np.cross(m2, m4), m3)
    k3 = np.dot(np.cross(m1, m4), m2) / np.dot(np.cross(m3, m4), m2)
    n2, n3 = k2 * m2 - m1, k3 * m3 - m1
    width, height = ((n[0] ** 2 + n[1] ** 2) / f**2 + n[2] ** 2 for n in (n2, n3))
    return float(np.sqrt(width / height)) if width > 0 and height > 0 else 0.0


def _outlines(lines: list[tuple[float, float]], size: tuple[int, int]):
    """Every quadrilateral of four lines that could be a card seen by a camera."""
    w, h = size
    pairs = [(a, b) for a, b in itertools.combinations(lines, 2) if _turn(a[0], b[0]) < np.deg2rad(30)]
    for (a, b), (c, d) in itertools.combinations(pairs, 2):
        if _turn(a[0], c[0]) < np.deg2rad(45):
            continue
        corners = [_crossing(a, c), _crossing(c, b), _crossing(b, d), _crossing(d, a)]
        if any(corner is None for corner in corners):
            continue
        quad = np.array(corners, np.float32)
        if not ((-0.02 * w <= quad[:, 0]) & (quad[:, 0] <= 1.02 * w)).all():
            continue
        if not ((-0.02 * h <= quad[:, 1]) & (quad[:, 1] <= 1.02 * h)).all():
            continue
        if len(cv2.convexHull(quad)) != 4 or cv2.contourArea(quad) < 0.02 * w * h:
            continue
        ratio = _ratio(quad, size)
        ratio = max(ratio, 1 / ratio) if ratio else 0.0
        if 1.3 < ratio < 2.0:
            yield quad, ratio


def _sides(quad: np.ndarray, step: float):
    """Points along each side, without its ends, and the side's normal pointing inside."""
    centre = quad.mean(0)
    for p, q in zip(quad, np.roll(quad, -1, 0), strict=True):
        along = (q - p) / np.linalg.norm(q - p)
        normal = np.array([-along[1], along[0]])
        if np.dot(centre - (p + q) / 2, normal) < 0:
            normal = -normal
        t = np.linspace(0.1, 0.9, max(4, int(np.linalg.norm(q - p) / step)))[:, None]
        yield p + (q - p) * t, normal


def _at(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    xs = np.clip(np.rint(points[:, 0]).astype(int), 0, w - 1)
    ys = np.clip(np.rint(points[:, 1]).astype(int), 0, h - 1)
    return image[ys, xs]


def _ends(quad: np.ndarray, near: np.ndarray) -> float:
    """How well the second weakest of the sides' eight ends lies on edges.

    A side's line runs on past the card, so an outline made partly of the card and partly of
    something else has corners where nothing ends. One end may be hidden under a finger.
    """
    ends = []
    for p, q in zip(quad, np.roll(quad, -1, 0), strict=True):
        for start, end in ((0.06, 0.18), (0.82, 0.94)):  # past the rounded corner
            t = np.linspace(start, end, max(4, int(np.linalg.norm(q - p) * (end - start) / 2)))[:, None]
            ends.append(_at(near, p + (q - p) * t).mean())
    return sorted(ends)[1]


def _overlap(a: np.ndarray, b: np.ndarray) -> float:
    """Intersection over union of two convex quadrilaterals."""
    common, _ = cv2.intersectConvexConvex(a, b)
    return common / (cv2.contourArea(a) + cv2.contourArea(b) - common)


def _looks_scanned(image: Image.Image) -> bool:
    """A light, even border, as a scanner's lid gives and a photo seldom does."""
    gray = np.array(image.convert("L"))
    border = np.concatenate([gray[:20].ravel(), gray[-20:].ravel(), gray[:, :20].ravel(), gray[:, -20:].ravel()])
    return np.median(border) > 200 and np.percentile(border, 90) - np.percentile(border, 10) < 25


def _in_order(quad: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """The corners clockwise from the card's top left, its long side the one nearest to level."""
    centre = quad.mean(0)
    quad = quad[np.argsort(np.arctan2(quad[:, 1] - centre[1], quad[:, 0] - centre[0]))]
    if _ratio(quad, size) < 1:  # the first side is a short one
        quad = np.roll(quad, -1, 0)
    top = quad[1] - quad[0]
    return quad if top[0] >= 0 else np.roll(quad, -2, 0)


def find_card_corners(image: Image.Image) -> np.ndarray | None:
    """The four corners of the card in a photo, or in a scan of unknown resolution.

    The card can lie at a slant to the camera. Its sides are straight lines through the photo's
    edges; of all the quadrilaterals they make that have a card's shape, the one whose every
    side lies on an edge and separates clearly different colours wins; a card is full of fine
    print, a wall or a door seen through the same lines is not. A light, even image
    (a scan) whose card is not found that way is searched like a scan. None if there is no card,
    or the best candidate is doubtful: a low score, another place in the photo nearly as good, or
    corners where no edges end.
    Corners clockwise from the card's top left.
    """
    scale = PHOTO_WIDTH / max(image.size)
    small = np.array(image.convert("RGB").resize((round(image.width * scale), round(image.height * scale))))
    size = (small.shape[1], small.shape[0])
    edges = _edges(small)
    near = cv2.distanceTransform(255 - edges, cv2.DIST_L2, 3) <= 2
    fine = cv2.Canny(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY), 50, 150) > 0
    lab = cv2.cvtColor(cv2.GaussianBlur(small, (0, 0), 2.5), cv2.COLOR_RGB2LAB).astype(np.float32)
    # Placing the outline on edges is cheap, comparing the colours on both sides of it is not.
    candidates = []
    for quad, ratio in _outlines(_lines(edges), size):
        on_edges = min(_at(near, points).mean() for points, _ in _sides(quad, 3))
        candidates.append((on_edges, quad, ratio))
    candidates.sort(key=lambda c: -c[0])
    scored = []
    offset = 0.012 * max(size)
    for on_edges, quad, ratio in candidates[:PHOTO_SHORTLIST]:
        contrast = min(
            np.median(np.linalg.norm(_at(lab, points + normal * offset) - _at(lab, points - normal * offset), axis=1))
            for points, normal in _sides(quad, 4)
        )
        inside = np.zeros(fine.shape, np.uint8)
        cv2.fillPoly(inside, [np.int32(quad.mean(0) + (quad - quad.mean(0)) * 0.85)], 1)
        printed = min(1.0, fine[inside > 0].mean() / PHOTO_PRINT)
        area = cv2.contourArea(quad) / (size[0] * size[1])
        score = (
            contrast
            * (0.5 + on_edges)
            * printed
            * area**0.25
            * np.exp(-((np.log(ratio / (CARD_MM[0] / CARD_MM[1])) / 0.15) ** 2))
        )
        scored.append((score, quad))
    scored.sort(key=lambda c: -c[0])
    if scored and scored[0][0] >= PHOTO_MIN_SCORE:
        score, best = scored[0]
        # A rival also when it lies inside: a card held up before a door can make a larger
        # outline around itself, which looks just like a card around its own photo.
        rival = next((other for other, quad in scored[1:] if _overlap(best, quad) < 0.5), 0.0)
        if score >= PHOTO_MARGIN * rival and _ends(best, near) > PHOTO_ENDS:
            return _in_order(best / scale, image.size)
    if _looks_scanned(image):
        cards = find_cards(image, None)
        if cards:
            return _in_order(cv2.boxPoints(cards[0]), image.size)
    return None


def _white_corners(card: Image.Image) -> Image.Image:
    """The card with white at its rounded corners, where the background showed."""
    outline = Image.new("L", card.size, 0)
    radius = round(CARD_CORNER_MM / CARD_MM[1] * card.height)
    ImageDraw.Draw(outline).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=radius, fill=255)
    return Image.composite(card, Image.new("RGB", card.size, "white"), outline)


def straighten(image: Image.Image, corners: np.ndarray) -> Image.Image:
    """The card inside corners (from find_card_corners) seen straight on, at a card's proportions."""
    sides = np.linalg.norm(corners - np.roll(corners, -1, 0), axis=1)
    width = round(max(sides[0], sides[2]))
    height = round(width * CARD_MM[1] / CARD_MM[0])
    target = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    card = cv2.warpPerspective(
        np.array(image.convert("RGB")),
        cv2.getPerspectiveTransform(np.float32(corners), target),
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderValue=(255, 255, 255),
    )
    return _white_corners(Image.fromarray(card))


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
    return _white_corners(Image.fromarray(card))


def card_from_image(image: Image.Image, dpi: float | None = None) -> Image.Image:
    """The card cut out of a scan or photo, or the image as it is if no card is found.

    Without dpi the image may be a photo, the card seen at a slant.
    """
    if dpi is None:
        corners = find_card_corners(image)
        return straighten(image, corners) if corners is not None else image
    cards = find_cards(image, dpi)
    return cut_out(image, cards[0]) if cards else image
