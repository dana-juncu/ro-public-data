"""
data.europa.eu Search API — Romanian public datasets (economic + cultural),
federated from data.gov.ro and other Romanian catalogs into the EU-wide
open data portal.

Source confirmed live Sept 2026 (see ../FINDINGS.md), then RE-confirmed and
corrected Sept 22, 2026 after the API changed shape mid-project:

  - The filter param is `filter` (singular), not `filters` — the old
    `filters=dataset` value is silently accepted but matches nothing.
  - `q=*` is NOT a wildcard on the current API — it matches zero results.
    Browse-all is `q=` (empty string).
  - `result.count` is now a plain integer, not `result.count.total`.

All three found by loading the real portal search UI
(https://data.europa.eu/data/datasets?...) and reading the exact request
it fires — the same method used throughout this project rather than
trusting an earlier capture or general knowledge, since this API has
already changed shape once during the project.

Theme filtering: the `categories` facet works (confirmed against a real
EU vocabulary code, e.g. "ECON"), but most Romanian datasets harvested
from data.gov.ro simply aren't tagged with an EU theme at all — filtering
by theme silently drops the vast majority of real results. Exposed here
as an optional filter with that caveat documented, not a primary path.

No key, no login.
"""
import json
from datetime import datetime as _datetime

import requests

# ── Config ──
URL = "https://data.europa.eu/api/hub/search/search"
TIMEOUT = 20
MAX_LIMIT = 100

# EU "data-theme" vocabulary codes relevant to this hub's scope (economic +
# cultural data) — confirmed live against the vocabulary endpoint. Pass one
# of these to `theme`, but see the module docstring's caveat: most RO
# datasets on this portal aren't tagged with any theme, so this narrows
# hard rather than gently.
ECONOMY_THEME = "ECON"  # "Economy and finance"
CULTURE_THEME = "EDUC"  # "Education, culture and sport" — closest EU code; not a pure culture-only tag

_INCLUDES = (
    "id,title.en,description.en,catalog.id,publisher.name,modified,issued,"
    "distributions.format.label"
)


def _iso_date(value: str) -> str:
    """Trim an ISO timestamp like '2026-09-18T11:07:36.277358' down to the date."""
    if not value:
        return ""
    try:
        return _datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value[:10]


def _clean(result: dict) -> dict:
    title = (result.get("title") or {}).get("en") or (result.get("description") or {}).get("en") or ""
    description = (result.get("description") or {}).get("en") or ""
    publisher = (result.get("publisher") or {}).get("name", "")
    catalog = (result.get("catalog") or {}).get("id", "")
    formats = sorted({
        (d.get("format") or {}).get("label", "")
        for d in result.get("distributions", [])
        if (d.get("format") or {}).get("label")
    })
    dataset_id = result.get("id", "")
    return {
        "id": dataset_id,
        "title": title,
        "description": description if description != title else "",
        "publisher": publisher,
        "catalog": catalog,
        "modified": _iso_date(result.get("modified", "")),
        "issued": _iso_date(result.get("issued", "")),
        "formats": formats,
        "url": f"https://data.europa.eu/data/datasets/{dataset_id}?locale=en" if dataset_id else "",
    }


def search_romania_datasets(
    query: str = "",
    theme: str | None = None,
    limit: int = 10,
    page: int = 0,
) -> dict:
    """
    Search Romanian public datasets on data.europa.eu — the EU-wide open
    data portal, which harvests data.gov.ro and other Romanian government
    catalogs (confirmed: data.gov.ro datasets appear here directly). Every
    result is real, live, and always scoped to country=Romania.

    query: free-text search (e.g. "buget", "energie", "accidente rutiere").
    Leave empty to browse the most recently updated Romanian datasets.
    theme: optional EU theme code to narrow results (e.g. "ECON" for
    economy/finance). Use sparingly — most Romanian datasets on this
    portal aren't tagged with a theme at all, so this filter can hide
    real results rather than just narrowing them.
    limit: max results per page (capped at 100).
    page: zero-based page number, for paging through more than `limit`
    results.

    Returns {"total": N, "results": [...]}, each result with title,
    description, publisher, source catalog, modified/issued dates,
    available file formats, and a direct URL to the dataset page.
    """
    limit = max(1, min(limit, MAX_LIMIT))
    facets = {"country": ["ro"]}
    if theme:
        facets["categories"] = [theme]

    params = {
        "q": query or "",
        "filter": "dataset",
        "limit": limit,
        "page": page,
        "sort": "relevance+desc" if query else "modified+desc",
        "includes": _INCLUDES,
        "facets": json.dumps(facets),
    }

    resp = requests.get(URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result", {})

    return {
        "total": result.get("count", 0),
        "results": [_clean(r) for r in result.get("results", [])],
    }


if __name__ == "__main__":
    import json

    out = search_romania_datasets("buget", limit=3)
    print(json.dumps(out, indent=2, ensure_ascii=False))
