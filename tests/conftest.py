"""Sample scans and a fake scanimage.

tests/data holds real 100 dpi scans of the whole glass of an Epson XP-255, made with the
printed test cards (docs/test_cards.pdf): empty.png, card.png (card A, turned about 7°)
and two_cards.png (A, and the very pale B upside down).
"""

import io
import subprocess
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image

from id2pdf import detect, i18n, scanner

DATA = Path(__file__).parent / "data"
SAMPLE_DPI = 100


def sample(name: str) -> Image.Image:
    return Image.open(DATA / name).convert("RGB")


def with_shadow(image: Image.Image, depth: float, width_mm: float) -> Image.Image:
    """The scan with a shadow around the card, as a thick plastic card casts under the lid."""
    rect = detect.find_cards(image, SAMPLE_DPI, glass=True)[0]
    card = np.zeros((image.height, image.width), np.uint8)
    cv2.fillPoly(card, [np.intp(cv2.boxPoints(rect))], 255)
    distance = cv2.distanceTransform(255 - card, cv2.DIST_L2, 5) / SAMPLE_DPI * 25.4
    shade = np.where(card == 0, depth * np.clip(1 - distance / width_mm, 0, 1) ** 1.5, 0)
    pixels = np.array(image).astype(np.float32) - shade[..., None]
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))


@pytest.fixture(autouse=True)
def english():
    i18n.set_language("en")
    yield
    i18n.set_language(None)


class FakeScanner:
    """Answers scanimage calls from sample scans of the whole glass, one per card side.

    A scan of an area is cut out of the sample and scaled up to the requested resolution.
    fail_once: the first scan of an area fails like a busy network scanner.
    """

    def __init__(self, glasses: list[Image.Image], fail_once: bool = False):
        self.glasses = glasses
        self.fail_once = fail_once
        self.calls: list[list[str]] = []
        self.previews = 0

    def run(self, command, capture_output=False, text=False, check=False):
        if command[:2] == ["scanimage", "-L"]:
            out = (
                "device `v4l:/dev/video0' is a Noname Chicony USB2.0 Camera: Chicony  virtual device\n"
                "device `epson2:net:192.168.178.32' is a Epson PID 113D flatbed scanner\n"
            )
            return SimpleNamespace(returncode=0, stdout=out, stderr="")
        self.calls.append(command)
        dpi = int(command[command.index("--resolution") + 1])
        if "-l" not in command:
            glass = self.glasses[min(self.previews, len(self.glasses) - 1)]
            self.previews += 1
            return self.png(
                glass.resize((round(glass.width * dpi / SAMPLE_DPI), round(glass.height * dpi / SAMPLE_DPI)))
            )
        if self.fail_once:
            self.fail_once = False
            return SimpleNamespace(
                returncode=9, stdout=b"", stderr=b"scanimage: open of device x failed: Error during device I/O"
            )
        glass = self.glasses[min(self.previews - 1, len(self.glasses) - 1)]
        left, top, width, height = (float(command[command.index(flag) + 1]) for flag in ("-l", "-t", "-x", "-y"))
        px = lambda mm: round(mm / 25.4 * SAMPLE_DPI)  # noqa: E731
        area = glass.crop((px(left), px(top), px(left + width), px(top + height)))
        return self.png(area.resize((area.width * dpi // SAMPLE_DPI, area.height * dpi // SAMPLE_DPI), Image.LANCZOS))

    @staticmethod
    def png(image: Image.Image) -> SimpleNamespace:
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        return SimpleNamespace(returncode=0, stdout=buffer.getvalue(), stderr=b"")


@pytest.fixture
def fake_scanner(monkeypatch):
    def install(*glasses: Image.Image, fail_once: bool = False) -> FakeScanner:
        fake = FakeScanner(list(glasses), fail_once)
        monkeypatch.setattr(subprocess, "run", fake.run)
        monkeypatch.setattr(scanner.time, "sleep", lambda seconds: None)
        monkeypatch.setattr("builtins.input", lambda prompt="": "")
        return fake

    return install
