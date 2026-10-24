import pymupdf
import pytest
from conftest import DATA, sample, with_shadow

from id2pdf import cli, i18n


def pdf_pages_mm(path) -> list[tuple[int, int]]:
    with pymupdf.open(path) as doc:
        return [(round(p.rect.width / 72 * 25.4), round(p.rect.height / 72 * 25.4)) for p in doc]


def test_scanning_both_sides_gives_one_a4_page(tmp_path, fake_scanner, capsys):
    fake = fake_scanner(sample("card.png"), with_shadow(sample("card.png"), 60, 9))
    cli.main([str(tmp_path / "id.pdf")])
    assert pdf_pages_mm(tmp_path / "id.pdf") == [(210, 297)]
    previews = [c for c in fake.calls if "-l" not in c]
    details = [c for c in fake.calls if "-l" in c]
    assert len(previews) == 2 and len(details) == 2
    assert all(c[c.index("--resolution") + 1] == "300" for c in details)
    assert "Saved:" in capsys.readouterr().out


def test_a_busy_scanner_is_asked_again(tmp_path, fake_scanner, capsys):
    fake_scanner(sample("card.png"), sample("card.png"), fail_once=True)
    cli.main([str(tmp_path / "id.pdf")])
    assert "still busy" in capsys.readouterr().out
    assert (tmp_path / "id.pdf").exists()


def test_an_empty_glass_asks_to_place_the_card_again(tmp_path, fake_scanner, monkeypatch):
    fake = fake_scanner(sample("empty.png"), sample("card.png"), sample("card.png"))
    prompts = []
    monkeypatch.setattr("builtins.input", lambda prompt="": prompts.append(prompt) or "")
    cli.main([str(tmp_path / "id.pdf")])
    assert sum("No card found" in p for p in prompts) == 1
    assert fake.previews == 3
    assert (tmp_path / "id.pdf").exists()


def test_pages_are_scanned_one_after_another(tmp_path, fake_scanner):
    fake = fake_scanner(sample("empty.png"))
    cli.main([str(tmp_path / "pages.pdf"), "--pages", "2"])
    assert len(pdf_pages_mm(tmp_path / "pages.pdf")) == 2
    assert all(c[c.index("-x") + 1] == "210.0" for c in fake.calls)


def test_existing_images_need_no_scanner(tmp_path):
    cli.main([str(tmp_path / "id.pdf"), "--images", str(DATA / "card.png"), str(DATA / "two_cards.png")])
    assert pdf_pages_mm(tmp_path / "id.pdf") == [(210, 297)]


def test_an_image_without_a_card_is_reported(tmp_path, capsys):
    photos = [str(DATA / "photo_table.jpg"), str(DATA / "photo_no_card.jpg")]
    cli.main([str(tmp_path / "id.pdf"), "--images", *photos])
    out = capsys.readouterr().out
    assert "No card found in" in out and "photo_no_card.jpg" in out and "photo_table.jpg" not in out
    assert (tmp_path / "id.pdf").exists()


def test_diagnose_prints_what_it_found(tmp_path, fake_scanner, capsys):
    fake_scanner(with_shadow(sample("card.png"), 70, 11))
    cli.main(["--diagnose", str(tmp_path / "diag")])
    out = capsys.readouterr().out
    assert "Objects found: 1" in out
    assert "CARD, without its shadow" in out
    assert (tmp_path / "diag" / "glass.png").exists()


def test_an_existing_output_is_kept_unless_confirmed(tmp_path, monkeypatch):
    output = tmp_path / "id.pdf"
    output.write_text("keep me")
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    with pytest.raises(SystemExit):
        cli.main([str(output), "--images", str(DATA / "card.png"), str(DATA / "card.png")])
    assert output.read_text() == "keep me"


def test_messages_are_translated_to_croatian(tmp_path, capsys):
    i18n.set_language("hr")
    cli.main([str(tmp_path / "id.pdf"), "--images", str(DATA / "card.png"), str(DATA / "card.png")])
    assert "Spremljeno:" in capsys.readouterr().out
