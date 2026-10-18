"""Putting cards and pages into a PDF."""

from pathlib import Path

from PIL import Image, ImageOps

from .detect import CARD_MM, mm_to_px

CARD_DPI = 300
PAGE_DPI = 200  # enough for documents, keeps a page around 1 MB
A4_MM = (210, 297)
GAP_MM = 15
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def card_size(image: Image.Image) -> Image.Image:
    """Scale to the real card size (landscape) so the printout is 1:1."""
    if image.height > image.width:
        image = image.rotate(90, expand=True)
    return ImageOps.contain(image, (mm_to_px(CARD_MM[0], CARD_DPI), mm_to_px(CARD_MM[1], CARD_DPI)))


def id_card_page(front: Image.Image, back: Image.Image) -> Image.Image:
    """Both sides on one A4 page, at real size like a photocopy."""
    front, back = card_size(front), card_size(back)
    page = Image.new("RGB", (mm_to_px(A4_MM[0], CARD_DPI), mm_to_px(A4_MM[1], CARD_DPI)), "white")
    gap = mm_to_px(GAP_MM, CARD_DPI)
    top = (page.height - front.height - gap - back.height) // 3  # a bit above the middle
    for image, y in ((front, top), (back, top + front.height + gap)):
        page.paste(image, ((page.width - image.width) // 2, y))
    return page


def save_pdf(images: list[Image.Image], output: Path, dpi: int = PAGE_DPI) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    first, *rest = images
    first.save(output, "PDF", resolution=dpi, save_all=True, append_images=rest, quality=85)


def open_image(path: Path) -> Image.Image:
    """An image file, turned the way the camera's EXIF data says."""
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def images_to_pdf(paths: list[Path], output: Path) -> None:
    """Photos or scans from elsewhere into one PDF, one image per page."""
    images = [open_image(p) for p in paths]
    longest = max(max(i.size) for i in images)
    save_pdf(images, output, dpi=max(72, round(longest / (A4_MM[1] / 25.4))))
