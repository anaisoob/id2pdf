"""Write docs/test_cards.pdf: two cards of ID card size without any personal data.

Print it at 100 % and cut the cards out to try id2pdf, or to make sample scans for the
tests, without scanning a real ID card. Card B is very pale, the hardest case.

    uv run tools/test_cards.py
"""

from pathlib import Path

import pymupdf

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "test_cards.pdf"


def mm(value: float) -> float:
    return value / 25.4 * 72


def card(page: pymupdf.Page, x: float, y: float, fill: tuple[float, float, float], label: str) -> None:
    page.draw_rect(
        pymupdf.Rect(mm(x), mm(y), mm(x + 85.6), mm(y + 54)),
        color=(0.45, 0.45, 0.45),
        fill=fill,
        width=0.4,
        radius=3.18 / 54,
    )
    page.draw_rect(pymupdf.Rect(mm(x + 5), mm(y + 9), mm(x + 28), mm(y + 39)), color=None, fill=(0.55, 0.47, 0.42))
    for i in range(6):
        width = 46 if i % 2 else 34
        page.draw_rect(
            pymupdf.Rect(mm(x + 33), mm(y + 11 + 5.5 * i), mm(x + 33 + width), mm(y + 12.6 + 5.5 * i)),
            color=None,
            fill=(0.25, 0.25, 0.32),
        )
    page.insert_text((mm(x + 5), mm(y + 49)), f"TEST CARD {label}", fontsize=7, fontname="notos", color=(0.3, 0.3, 0.3))
    page.insert_text(
        (mm(x), mm(y - 2)), f"{label}: cut along the grey edge (85.6 x 54 mm)", fontsize=8, fontname="notos"
    )


def main() -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=mm(210), height=mm(297))
    page.insert_font(fontname="notos", fontbuffer=pymupdf.Font("notos").buffer)
    page.insert_text((mm(20), mm(20)), "id2pdf test cards", fontsize=14, fontname="notos")
    page.insert_text(
        (mm(20), mm(28)),
        'Print at 100 % (no "fit to page"). The line below must be exactly 100 mm.',
        fontsize=9,
        fontname="notos",
    )
    page.draw_line((mm(20), mm(33)), (mm(120), mm(33)), width=0.8)
    page.insert_text((mm(122), mm(34)), "100 mm", fontsize=8, fontname="notos")
    card(page, 20, 50, (0.93, 0.91, 0.86), "A")
    card(page, 20, 125, (0.97, 0.965, 0.95), "B (very pale)")
    doc.save(OUTPUT)
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
