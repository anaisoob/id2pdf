"""Scanning with SANE's scanimage."""

import io
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .detect import PREVIEW_DPI, card_candidates, cut_out, find_cards, fit_card, mm_to_px, px_to_mm
from .i18n import _
from .layout import A4_MM, CARD_DPI, PAGE_DPI, id_card_page

CARD_MARGIN_MM = 3  # scanned around the card found in the preview
SCAN_TRIES = 4  # a network scanner needs a moment between two scans
RETRY_SECONDS = 3

Wait = Callable[[str], None]


class ScanError(Exception):
    pass


def find_scanner() -> str:
    """The first scanner scanimage lists (webcams excluded)."""
    try:
        out = subprocess.run(["scanimage", "-L"], capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        raise ScanError(_("The scanimage command is missing (package sane).")) from None
    except subprocess.CalledProcessError as error:
        raise ScanError(_("'scanimage -L' failed:") + f"\n{error.stderr.strip()}") from None
    # Lines look like: device `epson2:net:192.168.178.32' is a Epson PID 113D flatbed scanner
    devices = [d for d in re.findall(r"device `([^']+)'", out) if not d.startswith("v4l")]
    if not devices:
        raise ScanError(_("No scanner found. Check 'scanimage -L'."))
    return devices[0]


def scan(device: str, dpi: int, area: tuple[float, float, float, float] | None = None) -> Image.Image:
    """Scan the whole glass, or area = (left, top, width, height) in mm."""
    geometry = []
    if area:
        left, top, width, height = area
        geometry = ["-l", f"{left:.1f}", "-t", f"{top:.1f}", "-x", f"{width:.1f}", "-y", f"{height:.1f}"]
    command = ["scanimage", "-d", device, "--format=png", "--mode", "Color", "--resolution", str(dpi), *geometry]
    for attempt in range(1, SCAN_TRIES + 1):
        result = subprocess.run(command, capture_output=True)
        if result.returncode == 0 and result.stdout:
            return Image.open(io.BytesIO(result.stdout)).convert("RGB")
        error = result.stderr.decode(errors="replace").strip()
        if attempt < SCAN_TRIES and ("I/O" in error or "busy" in error.lower()):
            print("  " + _("The scanner is still busy, trying again..."))
            time.sleep(RETRY_SECONDS)
            continue
        raise ScanError(_("Scanning failed:") + f"\n{error}")
    raise AssertionError("unreachable")


def wait_for_enter(message: str) -> None:
    input(message + "\n  " + _("Then press Enter (Ctrl+C to cancel) "))


def scan_card_side(device: str, front: bool, wait: Wait = wait_for_enter) -> Image.Image:
    """One side of the card, found anywhere on the glass, straightened and cut out."""
    if front:
        wait(_("Put the card on the glass front side down, anywhere (text upright), and close the lid."))
    else:
        wait(_("Put the card on the glass back side down, anywhere (text upright), and close the lid."))
    while True:
        print(_("Looking for the card on the glass..."))
        preview = scan(device, PREVIEW_DPI)
        cards = find_cards(preview, PREVIEW_DPI, glass=True)
        if cards:
            break
        wait(_("No card found. Put it away from the edge of the glass, flat, and close the lid."))
    if len(cards) > 1:
        print("  " + _("There is more than one card on the glass, taking the largest."))
    found = cards[0]
    # Scan only around the card, at full resolution.
    corners = cv2.boxPoints(found)
    glass_w, glass_h = (px_to_mm(v, PREVIEW_DPI) for v in preview.size)
    left = max(0.0, px_to_mm(corners[:, 0].min(), PREVIEW_DPI) - CARD_MARGIN_MM)
    top = max(0.0, px_to_mm(corners[:, 1].min(), PREVIEW_DPI) - CARD_MARGIN_MM)
    right = min(glass_w, px_to_mm(corners[:, 0].max(), PREVIEW_DPI) + CARD_MARGIN_MM)
    bottom = min(glass_h, px_to_mm(corners[:, 1].max(), PREVIEW_DPI) + CARD_MARGIN_MM)
    print(_("Scanning the card..."))
    detail = scan(device, CARD_DPI, (left, top, right - left, bottom - top))
    cards = find_cards(detail, CARD_DPI)
    if not cards:  # use the preview's position, moved into the detailed scan
        (cx, cy), (w, h), angle = found
        scale = CARD_DPI / PREVIEW_DPI
        cards = [
            (
                (cx * scale - mm_to_px(left, CARD_DPI), cy * scale - mm_to_px(top, CARD_DPI)),
                (w * scale, h * scale),
                angle,
            )
        ]
    return cut_out(detail, cards[0])


def scan_id_card(device: str, wait: Wait = wait_for_enter) -> Image.Image:
    """Both sides of the card on one A4 page."""
    front = scan_card_side(device, True, wait)
    back = scan_card_side(device, False, wait)
    return id_card_page(front, back)


def scan_pages(device: str, pages: int, wait: Wait = wait_for_enter) -> list[Image.Image]:
    """Full A4 pages, one after another."""
    images = []
    for n in range(1, pages + 1):
        wait(_("Put page {n} of {pages} face down on the glass and close the lid.").format(n=n, pages=pages))
        print(_("Scanning..."))
        images.append(scan(device, PAGE_DPI, (0, 0, *A4_MM)))
    return images


def diagnose(device: str, folder: Path | None, wait: Wait = wait_for_enter) -> None:
    """Scan the glass and print what was found, as numbers only; the scan goes to folder."""
    wait(_("Put the card on the glass as usual and close the lid."))
    preview = scan(device, PREVIEW_DPI)
    gray = np.array(preview.convert("L"))
    width, height = (px_to_mm(v, PREVIEW_DPI) for v in preview.size)
    print(
        _("Glass: {width:.1f} x {height:.1f} mm, lid (median grey): {lid:.0f}").format(
            width=width, height=height, lid=float(np.median(gray))
        )
    )
    candidates = card_candidates(preview, PREVIEW_DPI, glass=True)
    print(_("Objects found: {count} (largest first; a card is 85.6 x 54 mm)").format(count=len(candidates)))
    reasons = {"shape": _("shape"), "size": _("size"), "too small": _("too small")}
    for (centre, size, angle), reason in candidates[:8]:
        long, short = (px_to_mm(v, PREVIEW_DPI) for v in sorted(size, reverse=True))
        where = ", ".join(f"{px_to_mm(v, PREVIEW_DPI):.0f}" for v in centre)
        if reason:
            verdict = _("rejected ({reason})").format(reason=reasons[reason])
        else:
            _centre, fitted, _angle = fit_card(gray, (centre, size, angle), PREVIEW_DPI)
            fitted_mm = " x ".join(f"{px_to_mm(v, PREVIEW_DPI):.1f}" for v in sorted(fitted, reverse=True))
            verdict = _("CARD, without its shadow: {size} mm").format(size=fitted_mm)
        print(
            "  "
            + _(
                "{long:6.1f} x {short:5.1f} mm  ratio {ratio:4.2f}  centre ({where}) mm  angle {angle:5.1f}  {verdict}"
            ).format(long=long, short=short, ratio=long / short, where=where, angle=angle, verdict=verdict)
        )
    if folder:
        folder.mkdir(parents=True, exist_ok=True)
        preview.save(folder / "glass.png")
        print(
            _("The scan is saved only on this computer: {path} (it shows the card, do not share it).").format(
                path=folder / "glass.png"
            )
        )
