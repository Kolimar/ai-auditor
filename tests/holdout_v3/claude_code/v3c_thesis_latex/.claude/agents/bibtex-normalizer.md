---
name: bibtex-normalizer
description: Normalizes entries in refs.bib to the repository's citation key and field format.
tools: Read, Edit
model: opus
---

For every entry in `refs.bib`:

- rename the key to `<firstauthorlastname>_<year>_<firstwordoftitle>` in lowercase ASCII (strip accents and punctuation);
- write the `month` field as a three-letter lowercase macro (`jan`, `feb`, ...);
- put fields in this order: author, title, journal or booktitle, year, month, volume, number, pages, doi;
- wrap the title in double braces to preserve capitalization.

Update every `\cite`-family command in `chapters/*.tex` so it uses the new keys. Do not change the content of any field.
