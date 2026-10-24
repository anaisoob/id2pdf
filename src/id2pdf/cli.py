"""The id2pdf command."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .detect import find_card_corners, straighten
from .i18n import _
from .layout import CARD_DPI, id_card_page, open_image, save_pdf
from .scanner import ScanError, diagnose, find_scanner, scan_id_card, scan_pages


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="id2pdf",
        description=_(
            "Scan both sides of an ID card onto one A4 page, as a PDF. The card may lie "
            "anywhere on the scanner glass; it is found, straightened and cut out."
        ),
    )
    p.add_argument("output", type=Path, nargs="?", help=_("the PDF to write (with --diagnose: a folder for the scan)"))
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--images",
        nargs=2,
        type=Path,
        metavar=("FRONT", "BACK"),
        help=_("use existing scans or photos of the two sides instead of scanning"),
    )
    mode.add_argument("--pages", type=int, metavar="N", help=_("scan N plain A4 pages instead of a card"))
    mode.add_argument(
        "--diagnose", action="store_true", help=_("scan the glass and print what is found (numbers only)")
    )
    p.add_argument("--device", help=_("SANE device (default: the first scanner in 'scanimage -L')"))
    p.add_argument("-f", "--force", action="store_true", help=_("overwrite the output without asking"))
    p.add_argument("--version", action="version", version=f"id2pdf {__version__}")
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    if not args.output and not args.diagnose:
        parser().error(_("the output PDF is required"))
    if args.output and args.output.exists() and not args.diagnose and not args.force:
        answer = input(_("{path} already exists. Overwrite? [y/N] ").format(path=args.output)).strip().lower()
        if answer not in (_("y"), "y"):
            sys.exit(_("Nothing was changed."))
    try:
        if args.images:
            sides = []
            for path in args.images:
                image = open_image(path)
                corners = find_card_corners(image)
                if corners is None:
                    print(_("No card found in {path}, the whole image is used.").format(path=path))
                sides.append(image if corners is None else straighten(image, corners))
            save_pdf([id_card_page(*sides)], args.output, CARD_DPI)
        else:
            device = args.device or find_scanner()
            print(_("Scanner: {device}").format(device=device))
            if args.diagnose:
                diagnose(device, args.output)
                return
            if args.pages:
                save_pdf(scan_pages(device, args.pages), args.output)
            else:
                save_pdf([scan_id_card(device)], args.output, CARD_DPI)
    except ScanError as error:
        sys.exit(str(error))
    except (EOFError, KeyboardInterrupt):
        sys.exit("\n" + _("Cancelled, nothing was saved."))
    print(_("Saved: {path}").format(path=args.output))


if __name__ == "__main__":
    main()
