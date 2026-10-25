import ast
import gettext
import string

import pytest

from id2pdf.i18n import LOCALE_DIR

LANGUAGES = sorted(path.name for path in LOCALE_DIR.iterdir() if path.is_dir())


def template_messages() -> list[str]:
    messages, parts = [], None
    for line in (LOCALE_DIR / "id2pdf.pot").read_text(encoding="utf-8").splitlines():
        if line.startswith("msgid "):
            parts = [ast.literal_eval(line[6:])]
        elif line.startswith('"') and parts is not None:
            parts.append(ast.literal_eval(line))
        elif line.startswith("msgstr") and parts is not None:
            messages.append("".join(parts))
            parts = None
    return [message for message in messages if message]


def fields(message: str) -> set[str]:
    return {field for _, field, _, _ in string.Formatter().parse(message) if field is not None}


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_message_is_translated_with_the_same_fields(language):
    # Reads the compiled .mo, so a translation that was not compiled fails too.
    translation = gettext.translation("id2pdf", LOCALE_DIR, languages=[language])
    catalog = translation._catalog  # gettext has no public way to tell untranslated from unchanged
    for message in template_messages():
        assert catalog.get(message), f"{language}: {message!r} is not translated"
        assert fields(catalog[message]) == fields(message), f"{language}: {message!r}"
