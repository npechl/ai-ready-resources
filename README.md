# ai-ready-resources

The EMBL-EBI AI-readiness assessment criteria as machine-readable JSON-LD, plus a static
website for browsing them.

## Layout

| Path | What it is |
|---|---|
| `data/assessment-list.txt` | Source criteria list (tab-separated export of the spreadsheet) |
| `data/assessment-objects.txt` | Source list of assessment objects (tab-separated, UTF-8) |
| `criteria/`, `principles/`, `assessment-objects/` | Generated JSON-LD, one file per entity |
| `schemas/` | Generated JSON-LD context and index |
| `website/index.md` | Hand-written home page; everything else in `website/` is generated |
| `zensical.toml` | Website config ([Zensical](https://zensical.org)) |
| `src/build_jsonld.py` | Source lists → JSON-LD |
| `src/build_site.py` | JSON-LD → website Markdown pages |

## Build

Requires Python 3 and Zensical (`pip install zensical`).

```sh
python3 src/build_jsonld.py   # data/*.txt -> JSON-LD (criteria/, principles/, assessment-objects/, schemas/)
python3 src/build_site.py     # JSON-LD -> website/ Markdown pages
zensical serve                # local preview at http://localhost:8000
zensical build                # static site in site/ (deploy that folder, e.g. to GitHub Pages)
```

The JSON-LD identifiers use a placeholder namespace (`https://example.org/embl-ebi/ai-readiness/`);
change `BASE` in `src/build_jsonld.py` once a persistent one exists.
