#!/usr/bin/env python3
"""Generate JSON-LD for the AI-readiness assessment criteria and assessment objects.

Reads:  data/assessment-list.txt, data/assessment-objects.txt  (tab-separated, UTF-8)
Writes: criteria/<criterion>.jsonld                  one file per criterion
        assessment-objects/<object>.jsonld           one file per assessment object
        principles/<principle>.jsonld                one file per principle
        schemas/context.jsonld                       shared JSON-LD context
        schemas/index.jsonld                         criteria, principles and objects schemes

Usage: python3 src/build_jsonld.py
"""
import csv
import json
import re
import sys
from pathlib import Path

# Placeholder namespace: replace with the real persistent base IRI once one exists.
BASE = "https://example.org/embl-ebi/ai-readiness/"

ROOT = Path(__file__).resolve().parent.parent
CRITERIA_SRC = ROOT / "data" / "assessment-list.txt"
OBJECTS_SRC = ROOT / "data" / "assessment-objects.txt"
CRITERIA_DIR = ROOT / "criteria"
OBJECTS_DIR = ROOT / "assessment-objects"
PRINCIPLES_DIR = ROOT / "principles"
SCHEMAS_DIR = ROOT / "schemas"

# Known typos in the source, fixed on output.
STANDARD_FIXES = {"OpenAI specification": "OpenAPI Specification"}

# Maps each part of the criteria list's "Assessment object" column (split on "/" and ";")
# to a term in data/assessment-objects.txt. None = deliberately not linked to a term.
# Any part not listed here stops the build, so new wording can't slip through unmapped.
OBJECT_ALIASES = {
    "API": "API",
    "API payloads": "API payload",
    "Annotations": "Label / annotation",
    "Archive": "Storage",
    "Assertions": "Assertion",
    "Concepts": "Vocabulary / ontology",
    "Criterion": None,  # the criterion itself; not an object of the resource
    "Cross-references": "Cross-reference",
    "Data lifecycle": "Data lifecycle",
    "Dataset": "Dataset",
    "Declared AI use case": "Declared AI use case",
    "Dependencies": "Runtime / dependencies",
    "Derived fields": "Field",
    "Derived values": "Derived value",
    "Documentation": "Documentation set",
    "Documentation set": "Documentation set",
    "Entities": "Entity",
    "Export": "Export",
    "Exports": "Export",
    "Fields": "Field",
    "Files": "File",
    "Identifiers": "Identifier",
    "Interface": "Interface / access route",
    "Labels": "Label / annotation",
    "Mappings": "Mapping",
    "Measurements": "Measurement",
    "Ontologies": "Vocabulary / ontology",
    "Output": "Output",
    "Pipeline": "Pipeline / workflow",
    "Records": "Record",
    "Relationships": "Entity",
    "Release": "Release",
    "Resource": "Resource",
    "Runtime": "Runtime / dependencies",
    "Schema": "Schema",
    "Service": "Service",
    "Storage": "Storage",
    "Support": "Support",
    "Values": "Measurement",
    "Vocabularies": "Vocabulary / ontology",
}

# Note: JSON-LD ignores @base inside a remote context, so each document sets it inline.
CONTEXT = {
    "@context": {
        "@version": 1.1,
        "air": BASE + "vocab#",
        "dqv": "http://www.w3.org/ns/dqv#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "dcterms": "http://purl.org/dc/terms/",
        "AssessmentCriterion": "air:AssessmentCriterion",
        "AssessmentObject": "air:AssessmentObject",
        "Principle": "air:Principle",
        "id": "@id",
        "type": "@type",
        "identifier": "dcterms:identifier",
        "name": "skos:prefLabel",
        "description": "skos:definition",
        "inScheme": {"@id": "skos:inScheme", "@type": "@id"},
        "principle": {"@id": "dqv:inDimension", "@type": "@id"},
        "requirement": "skos:definition",
        "requirementLevel": {"@id": "air:requirementLevel", "@type": "@vocab", "@container": "@set"},
        "must": "air:Must",
        "should": "air:Should",
        "howToAssess": "air:howToAssess",
        "assessmentObject": {"@id": "air:assessmentObject", "@type": "@id", "@container": "@set"},
        "assessedBy": {"@reverse": "air:assessmentObject", "@type": "@id", "@container": "@set"},
        "assessmentObjectLabel": "air:assessmentObjectLabel",
        "exampleScope": "air:exampleScope",
        "applicability": "air:applicability",
        "evidence": {"@id": "air:evidence", "@container": "@set"},
        "sharesEvidenceWith": {"@id": "air:sharesEvidenceWith", "@type": "@id", "@container": "@set"},
        "assessmentFrequency": "air:assessmentFrequency",
        "relatedStandard": {"@id": "air:relatedStandard", "@container": "@set"},
        "goodExample": "air:goodExample",
        "poorExample": "air:poorExample",
        "hasCriterion": {"@id": "air:hasCriterion", "@type": "@id", "@container": "@set"},
        "hasTopConcept": {"@id": "skos:hasTopConcept", "@type": "@id", "@container": "@set"},
    }
}

CRITERIA_SCHEME = "scheme"
OBJECTS_SCHEME = "assessment-objects"
PRINCIPLES_SCHEME = "principles"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def split_list(s, sep):
    return [x.strip().rstrip(".") for x in re.split(sep, s) if x.strip()]


def read_tsv(path):
    rows = [r for r in csv.reader(path.open(encoding="utf-8", newline=""), delimiter="\t") if any(c.strip() for c in r)]
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def context_ref(rel):
    return [rel, {"@base": BASE}]


def write_json(path, doc):
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def requirement_level(text):
    # Ignore descriptive "should" ("how the value should be read", "should not be used for").
    t = re.sub(r"should (not )?be (read|used)", "", text.lower())
    must, should = bool(re.search(r"\bmust\b", t)), bool(re.search(r"\bshould\b", t))
    return ["must"] * must + ["should"] * should


def split_examples(text):
    """Source packs a good example then a poor one into one cell. Split at the last sentence break."""
    text = text.strip()
    if not text:
        return None, None
    text = re.sub(r"\s+-\s+(?=[A-Z])", " ", text)        # " - A free-text ..."
    text = re.sub(r"\.(?=[A-Z])", ". ", text)             # "version.Checks"
    breaks = [m.end() for m in re.finditer(r"(?<!e\.g)\.\s+(?=[A-Z\"])", text)]
    if not breaks:
        return text, None
    i = breaks[-1]
    return text[:i].strip(), text[i:].strip()


def object_ids(label, objects, criterion):
    ids = []
    for part in split_list(label, r"[/;]"):
        part = part[:1].upper() + part[1:]
        if part not in OBJECT_ALIASES:
            sys.exit(f"{criterion}: assessment object {part!r} has no entry in OBJECT_ALIASES")
        term = OBJECT_ALIASES[part]
        if term is None:
            continue
        if term not in objects:
            sys.exit(f"OBJECT_ALIASES maps {part!r} to {term!r}, which is not in {OBJECTS_SRC.name}")
        oid = objects[term]["id"]
        if oid not in ids:
            ids.append(oid)
    return ids


def main():
    objects = {
        o["Assessment object"].strip(): {
            "id": "object/" + slug(o["Assessment object"]),
            "type": ["AssessmentObject", "skos:Concept"],
            "identifier": slug(o["Assessment object"]),
            "name": o["Assessment object"].strip(),
            "inScheme": OBJECTS_SCHEME,
            "description": o["Description"].strip(),
            "exampleScope": o["Example scope"].strip(),
            "assessedBy": [],
        }
        for o in read_tsv(OBJECTS_SRC)
    }

    recs = read_tsv(CRITERIA_SRC)
    names = {r["Name"]: slug(r["Name"]) for r in recs}

    for d in (CRITERIA_DIR, OBJECTS_DIR, PRINCIPLES_DIR, SCHEMAS_DIR):
        d.mkdir(exist_ok=True)
    for d in (CRITERIA_DIR, OBJECTS_DIR, PRINCIPLES_DIR):  # generated output; clear so renamed entries don't linger
        for old in d.glob("*.jsonld"):
            old.unlink()
    write_json(SCHEMAS_DIR / "context.jsonld", CONTEXT)

    principles = {}
    for r in recs:
        sid = names[r["Name"]]
        cid = "criterion/" + sid
        pid = "principle/" + slug(r["Relevant principle of AI-readiness"])
        principles.setdefault(pid, {"name": r["Relevant principle of AI-readiness"], "criteria": []})["criteria"].append(cid)

        evidence_text = r["Evidence"]
        shared = []
        m = re.search(r"Evidence can be shared with:(.*)$", evidence_text)
        if m:
            evidence_text = evidence_text[: m.start()]
            for n in re.findall(r'"([^"]+)"', m.group(1)):
                if n not in names:
                    sys.exit(f"{r['Name']}: unknown shared-evidence criterion {n!r}")
                shared.append("criterion/" + names[n])

        obj_label = r["Assessment object"].strip()
        obj_ids = object_ids(obj_label, objects, r["Name"])
        for o in objects.values():
            if o["id"] in obj_ids:
                o["assessedBy"].append(cid)

        good, poor = split_examples(r["Examples"])
        doc = {
            "@context": context_ref("../schemas/context.jsonld"),
            "id": cid,
            "type": ["AssessmentCriterion", "skos:Concept"],
            "identifier": sid,
            "name": r["Name"].strip(),
            "inScheme": CRITERIA_SCHEME,
            "principle": pid,
            "requirement": r["Requirement"].strip(),
            "requirementLevel": requirement_level(r["Requirement"]),
            "howToAssess": r["How to assess"].strip(),
            "assessmentObjectLabel": obj_label,
            "assessmentObject": obj_ids,
            "applicability": r["Applicability"].strip(),
            "evidence": split_list(evidence_text, r";"),
            "sharesEvidenceWith": shared,
            "assessmentFrequency": r["When applied"].strip(),
            "relatedStandard": [STANDARD_FIXES.get(x, x) for x in split_list(r["Related standards or publications"], r",")],
            "goodExample": good,
            "poorExample": poor,
        }
        doc = {k: v for k, v in doc.items() if v not in (None, "", [])}
        write_json(CRITERIA_DIR / f"{sid}.jsonld", doc)

    write_json(SCHEMAS_DIR / "index.jsonld", {
        "@context": context_ref("context.jsonld"),
        "@graph": [
            {
                "id": CRITERIA_SCHEME,
                "type": "skos:ConceptScheme",
                "name": "EMBL-EBI AI-readiness assessment criteria",
                "hasTopConcept": [c for p in principles.values() for c in p["criteria"]],
            },
            {
                "id": PRINCIPLES_SCHEME,
                "type": "skos:ConceptScheme",
                "name": "EMBL-EBI AI-readiness principles",
                "hasTopConcept": list(principles),
            },
            {
                "id": OBJECTS_SCHEME,
                "type": "skos:ConceptScheme",
                "name": "EMBL-EBI AI-readiness assessment objects",
                "hasTopConcept": [o["id"] for o in objects.values()],
            },
        ],
    })

    for pid, p in principles.items():
        write_json(PRINCIPLES_DIR / f"{pid.split('/', 1)[1]}.jsonld", {
            "@context": context_ref("../schemas/context.jsonld"),
            "id": pid,
            "type": ["Principle", "dqv:Dimension", "skos:Concept"],
            "identifier": pid.split("/", 1)[1],
            "name": p["name"],
            "inScheme": PRINCIPLES_SCHEME,
            "hasCriterion": p["criteria"],
        })

    for o in objects.values():
        doc = {"@context": context_ref("../schemas/context.jsonld"), **o}
        doc = {k: v for k, v in doc.items() if v not in ("", [])}
        write_json(OBJECTS_DIR / f"{o['identifier']}.jsonld", doc)

    unused = [n for n, o in objects.items() if not o["assessedBy"]]
    print(f"Wrote {len(recs)} criteria, {len(principles)} principles and {len(objects)} assessment objects.")
    if unused:
        print("Assessment objects not used by any criterion:", ", ".join(unused))


if __name__ == "__main__":
    main()
