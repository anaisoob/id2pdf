#!/bin/sh
# Extract the messages, merge them into the translations and compile them.
# Needs gettext (xgettext, msgmerge, msgfmt).
set -eu
cd "$(dirname "$0")/.."
locale=src/id2pdf/locale
xgettext --language=Python --keyword=_ --from-code=UTF-8 --package-name=id2pdf \
    --output="$locale/id2pdf.pot" src/id2pdf/*.py
for po in "$locale"/*/LC_MESSAGES/id2pdf.po; do
    msgmerge --quiet --update --backup=none "$po" "$locale/id2pdf.pot"
    msgfmt --check --output-file="${po%.po}.mo" "$po"
done
