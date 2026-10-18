"""Translations of the messages (gettext, domain "id2pdf").

The language follows the usual environment variables (LANGUAGE, LC_ALL, LC_MESSAGES,
LANG); a program that uses id2pdf as a library can pick one with set_language().
"""

import gettext
from pathlib import Path

LOCALE_DIR = Path(__file__).parent / "locale"

_translation: gettext.NullTranslations = gettext.translation("id2pdf", LOCALE_DIR, fallback=True)


def set_language(language: str | None) -> None:
    """Use this language ("hr", "en", ...); None goes back to the environment's."""
    global _translation
    languages = [language] if language else None
    _translation = gettext.translation("id2pdf", LOCALE_DIR, languages=languages, fallback=True)


def _(message: str) -> str:
    return _translation.gettext(message)
