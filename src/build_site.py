#!/usr/bin/env python3
"""Generate the website's Markdown pages from the JSON-LD.

Reads:  criteria/, principles/, assessment-objects/, schemas/index.jsonld
Writes: website/criteria/, website/principles/, website/objects/
        (all generated and git-ignored; website/index.md is hand-written)

Usage: python3 src/build_site.py && zensical serve
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "website"
LEVEL = {"must": "MUST", "should": "SHOULD", "must/should": "MUST / SHOULD"}


def load(folder):
    items = {}
    for f in (ROOT / folder).glob("*.jsonld"):
        d = json.loads(f.read_text(encoding="utf-8"))
        items[d["id"]] = d
    return items


def slug(iri):
    return iri.split("/", 1)[1]


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def write(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    criteria = load("criteria")
    principles = load("principles")
    objects = load("assessment-objects")
    schemes = {n["id"]: n for n in json.loads((ROOT / "schemas/index.jsonld").read_text())["@graph"]}
    # Scheme order, not alphabetical: it matches the source spreadsheet.
    p_order = schemes["principles"]["hasTopConcept"]
    o_order = schemes["assessment-objects"]["hasTopConcept"]
    c_order = schemes["scheme"]["hasCriterion"]

    def link(iri, prefix="../"):
        folder = {"criterion": "criteria", "principle": "principles", "object": "objects"}[iri.split("/")[0]]
        item = {**criteria, **principles, **objects}[iri]  # KeyError = dangling reference in the data
        return f"[{item['name']}]({prefix}{folder}/{slug(iri)}.md)"

    for d in ("criteria", "principles", "objects"):
        shutil.rmtree(OUT / d, ignore_errors=True)

    # Criterion pages
    for iri, c in criteria.items():
        lines = [
            f"# {c['name']}",
            "",
            f"**{LEVEL[c['requirementLevel']]}** · Principle: {link(c['principle'])} · "
            f"Assess: {c['assessmentFrequency']}",
            "",
            "## Requirement", "", c["requirement"], "",
            "## How to assess", "", c["howToAssess"], "",
            "## Applies to", "",
            ", ".join(link(o) for o in c["assessmentObject"]) or c["assessmentObjectLabel"], "",
            c["applicability"], "",
            "## Evidence", "",
            *(f"- {e}" for e in c["evidence"]), "",
        ]
        if "goodExample" in c or "poorExample" in c:
            lines += ["## Examples", ""]
            if "goodExample" in c:
                lines += ['!!! success "Good"', "", f"    {c['goodExample']}", ""]
            if "poorExample" in c:
                lines += ['!!! failure "Poor"', "", f"    {c['poorExample']}", ""]
        if c.get("relatedStandard"):
            lines += ["## Related standards", "", *(f"- {s}" for s in c["relatedStandard"]), ""]
        if c.get("sharesEvidenceWith"):
            lines += ["## Shares evidence with", "", *(f"- {link(s)}" for s in c["sharesEvidenceWith"]), ""]
        write(OUT / "criteria" / f"{slug(iri)}.md", lines)

    # Criteria overview: one table, in spreadsheet order (grouped by principle).
    rows = ["| Criterion | Principle | Level | Applies to | Assess |", "|---|---|---|---|---|"]
    for iri in c_order:
        c = criteria[iri]
        rows.append(
            f"| [{c['name']}]({slug(iri)}.md) | {link(c['principle'])} | {LEVEL[c['requirementLevel']]} "
            f"| {cell(c['assessmentObjectLabel'])} | {cell(c['assessmentFrequency'])} |"
        )
    write(OUT / "criteria/index.md", [
        "# Criteria", "",
        f"All {len(criteria)} criteria. Use search (top right) to find a criterion by any word "
        "in its text, or browse by [principle](../principles/index.md) or "
        "[assessment object](../objects/index.md).", "", *rows,
    ])

    # Principle pages
    for iri, p in principles.items():
        lines = [f"# {p['name']}", "", "| Criterion | Level | Requirement |", "|---|---|---|"]
        for ci in p["hasCriterion"]:
            c = criteria[ci]
            lines.append(f"| {link(ci)} | {LEVEL[c['requirementLevel']]} | {cell(c['requirement'])} |")
        write(OUT / "principles" / f"{slug(iri)}.md", lines)
    write(OUT / "principles/index.md", [
        "# Principles", "", "| Principle | Criteria |", "|---|---|",
        *(f"| [{principles[i]['name']}]({slug(i)}.md) | {len(principles[i]['hasCriterion'])} |" for i in p_order),
    ])

    # Assessment object pages
    for iri, o in objects.items():
        lines = [
            f"# {o['name']}", "", o["description"], "",
            f"**Example scope:** {o['exampleScope']}", "",
            "## Assessed by", "", "| Criterion | Principle | Level |", "|---|---|---|",
        ]
        for ci in o["assessedBy"]:
            c = criteria[ci]
            lines.append(f"| {link(ci)} | {link(c['principle'])} | {LEVEL[c['requirementLevel']]} |")
        write(OUT / "objects" / f"{slug(iri)}.md", lines)
    write(OUT / "objects/index.md", [
        "# Assessment objects", "",
        "The things a criterion is checked against.", "",
        "| Object | Description | Criteria |", "|---|---|---|",
        *(f"| [{objects[i]['name']}]({slug(i)}.md) | {cell(objects[i]['description'])} "
          f"| {len(objects[i]['assessedBy'])} |" for i in o_order),
    ])

    print(f"Wrote {len(criteria)} criteria, {len(principles)} principles, {len(objects)} objects to {OUT}")


if __name__ == "__main__":
    main()
