# ai-ready-resources

The EMBL-EBI AI-readiness assessment criteria as machine-readable JSON-LD, plus a static
website for browsing them.

## Build

Requires Python 3 and Zensical (`pip install zensical`).

```sh
# python3 src/build_jsonld.py   # data/*.txt to JSON-LD (criteria/, principles/, assessment-objects/, schemas/)
# python3 src/build_site.py     # JSON-LD to website/ Markdown pages
zensical serve                # local preview at http://localhost:8000
zensical build                # static site in site/ (deploy that folder, e.g. to GitHub Pages)
```

The JSON-LD identifiers use a placeholder namespace (`https://example.org/embl-ebi/ai-readiness/`);
change `BASE` in `src/build_jsonld.py` once a persistent one exists.
