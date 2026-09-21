"""
INS Tempo-Online — Romania's National Institute of Statistics data
warehouse (statistici.insse.ro), covering population, economy, labour,
prices, culture, and dozens of other official statistical domains.

Source confirmed live Sept 15, 2026 and RE-confirmed unchanged Sept 22,
2026 (see ../FINDINGS.md for the original investigation). No public docs
exist for this API — the shape was reverse-engineered by watching the
real Angular frontend's (/tempo-online/) network calls against its
backend (/tempo-ins/), cross-checked against the gov2-ro/tempo-ins-dump
GitHub project's source for the final /pivot step.

Four-step pipeline, all keyless:
  1. GET /tempo-ins/context/          -> the FULL category tree in one
                                          call, flattened, each node
                                          carrying its own parentCode and
                                          nesting level.
  2. GET /tempo-ins/context/{code}    -> drill into one category: returns
                                          its ancestors plus its direct
                                          children, which are either more
                                          sub-categories (childrenUrl:
                                          "context") or dataset "matrices"
                                          (childrenUrl: "matrix").
  3. GET /tempo-ins/matrix/{code}     -> a matrix's full metadata: title
                                          plus `dimensionsMap`, the
                                          selectable dimensions (age, sex,
                                          region, year, ...), each with a
                                          list of {label, nomItemId}
                                          options, and `details` (the
                                          matMaxDim/matUMSpec/matRegJ
                                          values step 4 needs).
  4. POST /tempo-ins/pivot            -> the actual data pull: one
                                          nomItemId per dimension (in
                                          dimensionsMap order), joined
                                          with ":" as `encQuery`. Returns
                                          CSV text.

Confirmed live (Sept 22, 2026 re-check): matrix POP105A (resident
population by age/sex/urban-rural/region/year), queried for
Total/Total/Total/TOTAL/2025 -> 19,043,151, matching Romania's real
official resident-population figure for 1 Jan 2025 exactly.

LEGAL NOTE: INS's own terms of use (in the frontend app's config)
restrict reproduction/redistribution of TEMPO-Online content without
written INS authorization, but explicitly allow quoting with clear
source attribution.

GOTCHA: INS's frontend itself warns that queries selecting more than
30,000 total cells (the product of every selected dimension's option
count) will be rejected — keep selections narrow, or chunk wide queries
(e.g. one call per year) rather than selecting "all" on every dimension.
"""
import csv
import io

import requests

# ── Config ──
BASE = "http://statistici.insse.ro:8077/tempo-ins"
TIMEOUT = 30


def browse(code: str = "") -> dict:
    """
    Browse INS's statistical category tree.

    code="" (default): returns the FULL tree in one call — every
    category and sub-category, flattened, each with its own code,
    name, parentCode, and nesting level. Good for a one-shot keyword
    search across all ~340 categories rather than drilling one level
    at a time.

    code=<a category code>: drills into that one category, returning
    its direct children — either more sub-categories, or (at a leaf)
    the actual dataset "matrices" available there, each with the
    matrix code needed by matrix_dimensions()/query().
    """
    if not code:
        raw = requests.get(f"{BASE}/context/", timeout=TIMEOUT).json()
        return {
            "categories": [
                {
                    "code": item["context"]["code"],
                    "name": item["context"]["name"],
                    "parent_code": item.get("parentCode", ""),
                    "level": item.get("level", 0),
                    "is_matrix": item["context"].get("childrenUrl") == "matrix",
                }
                for item in raw
            ]
        }

    raw = requests.get(f"{BASE}/context/{code}", timeout=TIMEOUT).json()
    return {
        "name": raw.get("context", {}).get("name", ""),
        "code": raw.get("context", {}).get("code", code),
        "path": [a["name"] for a in raw.get("ancestors", []) if a.get("name") and a["name"] != "home"],
        "children": [
            {
                "code": c["code"],
                "name": c["name"],
                "is_matrix": c.get("childrenUrl") == "matrix",
            }
            for c in raw.get("children", [])
        ],
    }


def matrix_dimensions(matrix_code: str) -> dict:
    """
    Get one statistics matrix's full metadata: its title and every
    selectable dimension (e.g. age, sex, region, year) with the exact
    option labels and IDs query() needs. Always call this before
    query() to find the right nomItemId for each dimension — dimension
    order and option IDs vary per matrix and aren't guessable.
    """
    meta = requests.get(f"{BASE}/matrix/{matrix_code}", timeout=TIMEOUT).json()
    details = meta.get("details", {})
    return {
        "matrix_code": matrix_code,
        "title": meta.get("matrixName", ""),
        "dimensions": [
            {
                "label": d.get("label", ""),
                "options": [
                    {"id": o["nomItemId"], "label": o["label"].strip()}
                    for o in d.get("options", [])
                ],
            }
            for d in meta.get("dimensionsMap", [])
        ],
        # Internal fields query() needs verbatim — pass matrix_dimensions()'s
        # own result straight through rather than re-deriving these.
        "_details": {
            "matMaxDim": details.get("matMaxDim", 0),
            "matUMSpec": details.get("matUMSpec", 0),
            "matRegJ": details.get("matRegJ", 0),
        },
    }


def query(matrix_code: str, selections: list[int]) -> list[dict]:
    """
    Pull actual data from one INS statistics matrix.

    selections: one nomItemId per dimension, IN THE SAME ORDER as
    matrix_dimensions()'s `dimensions` list (e.g. for POP105A: [age,
    sex, urban/rural, region, year, unit]). Get valid IDs by calling
    matrix_dimensions(matrix_code) first — there's no way to guess
    them. Selecting too many combinations at once (over ~30,000
    resulting cells) will be rejected by INS; prefer several narrow
    calls (e.g. one per year) over one very wide one.

    Returns each result row as a dict of {dimension_label: value,
    ..., "value": <the number>} — parsed from INS's own CSV export.
    """
    meta = matrix_dimensions(matrix_code)
    details = meta["_details"]
    payload = {
        "language": "ro",
        "encQuery": ":".join(str(s) for s in selections),
        "matCode": matrix_code,
        "matMaxDim": details["matMaxDim"],
        "matUMSpec": details["matUMSpec"],
        "matRegJ": details["matRegJ"],
    }
    resp = requests.post(f"{BASE}/pivot", json=payload, timeout=TIMEOUT)
    resp.raise_for_status()

    reader = csv.reader(io.StringIO(resp.text))
    rows = [row for row in reader if row]
    if not rows:
        return []

    header = [h.strip() for h in rows[0]]
    results = []
    for row in rows[1:]:
        entry = dict(zip(header[:-1], (v.strip() for v in row[:-1])))
        try:
            entry[header[-1]] = float(row[-1].strip())
        except (ValueError, IndexError):
            entry[header[-1]] = row[-1].strip() if len(row) > len(header) - 1 else None
        results.append(entry)
    return results


if __name__ == "__main__":
    import json

    dims = matrix_dimensions("POP105A")
    print(dims["title"])
    for d in dims["dimensions"]:
        print(f"  {d['label']}: {len(d['options'])} options, e.g. {d['options'][0]}")

    # Total/Total/Total/TOTAL/2025/persons
    selections = [1, 105, 108, 112, 4912, 9685]
    result = query("POP105A", selections)
    print(json.dumps(result, indent=2, ensure_ascii=False))
