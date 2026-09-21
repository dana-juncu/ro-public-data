"""
ANAF (Agenţia Naţională de Administrare Fiscală) — company/VAT lookup.

Source confirmed live Sept 2026 (see ../FINDINGS.md for the full
investigation). The path documented by most community references
(anaf-mcp, itrack/anaf, several blog posts) is stale and gets caught by
ANAF's WebSEAL gateway, returning a misleading 403 that looks like an
auth wall. The correct current path is used below.

No key, no login. Rate limit per ANAF's own docs: max 1 request/second,
up to 100 CUIs per request — since ANAF accepts a whole list of CUIs in
one call, batch lookups should go through get_companies() rather than
looping single calls.
"""
from datetime import date as _date

import requests

# ── Config ──
URL = "https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva"
TIMEOUT = 20
MAX_CUIS_PER_REQUEST = 100


def _today() -> str:
    return _date.today().isoformat()


def get_companies(cuis: list[int], as_of: str | None = None) -> list[dict]:
    """
    Look up one or more companies by CUI (Romanian tax/registration
    number) as of a given date (defaults to today). Up to 100 CUIs per
    call — ANAF's API accepts the whole batch in a single request, no
    need to loop.

    Returns ANAF's raw per-company records (address, VAT status,
    registration details, CAEN code, etc.) in a list, one per requested
    CUI that ANAF could resolve — unresolved CUIs are simply omitted
    from the response by ANAF, not raised as errors.
    """
    if len(cuis) > MAX_CUIS_PER_REQUEST:
        raise ValueError(
            f"ANAF accepts at most {MAX_CUIS_PER_REQUEST} CUIs per request; "
            f"got {len(cuis)}. Split into multiple calls."
        )
    as_of = as_of or _today()
    payload = [{"cui": cui, "data": as_of} for cui in cuis]

    resp = requests.post(
        URL,
        json=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    # ANAF wraps results in {"cod": 200, "message": "...", "found": [...], "notFound": [...]}
    if isinstance(data, dict) and "found" in data:
        return data["found"]
    # Some ANAF responses are a bare list instead — handle both shapes.
    if isinstance(data, list):
        return data
    raise RuntimeError(f"Unexpected ANAF response shape: {data!r}")


def get_company(cui: int, as_of: str | None = None) -> dict | None:
    """Look up a single company by CUI. Returns None if ANAF has no record for it."""
    results = get_companies([cui], as_of=as_of)
    return results[0] if results else None


if __name__ == "__main__":
    import json

    # Real, confirmed-live CUIs from prototyping
    demo_cuis = [
        14399840,  # DANTE INTERNATIONAL SA (eMAG)
        1590082,   # OMV PETROM SA
        5022670,   # BANCA TRANSILVANIA SA
    ]
    results = get_companies(demo_cuis)
    print(json.dumps(results, indent=2, ensure_ascii=False)[:3000])
