"""Scan both sides of an ID card onto one A4 page, as a PDF.

The card may lie anywhere on the scanner glass: a quick scan of the whole glass finds it,
then only that spot is scanned at full resolution, straightened and cut out.
"""

from .detect import CARD_MM, card_from_image, cut_out, find_card_corners, find_cards, straighten
from .i18n import set_language
from .layout import CARD_DPI, IMAGE_SUFFIXES, PAGE_DPI, id_card_page, images_to_pdf, open_image, save_pdf
from .scanner import ScanError, find_scanner, scan, scan_card_side, scan_id_card, scan_pages

__version__ = "0.3.0"

__all__ = [
    "CARD_DPI",
    "CARD_MM",
    "IMAGE_SUFFIXES",
    "PAGE_DPI",
    "ScanError",
    "card_from_image",
    "cut_out",
    "find_card_corners",
    "find_cards",
    "find_scanner",
    "id_card_page",
    "images_to_pdf",
    "open_image",
    "save_pdf",
    "scan",
    "scan_card_side",
    "scan_id_card",
    "scan_pages",
    "set_language",
    "straighten",
]
