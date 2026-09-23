"""
AMCCRS (Administraţia Municipală pentru Consolidarea Clădirilor cu Risc
Seismic) — Bucharest's official registry of buildings classified by
earthquake risk (RsI-RsIV, plus "consolidated"/retrofitted and "pending"/
not-yet-classified — see `_risk_class()` below), addresses, technical
experts, and expertise dates.

Source confirmed live Sept 15, 2026 and RE-confirmed unchanged Sept 22,
2026, including the same reusable nonce still working a week later (see
../FINDINGS.md for the original investigation).

The public page (amccrs-pmb.ro/lista-imobile-2/) doesn't server-render
its table — it's a WordPress "Ninja Tables" plugin instance pulling data
client-side from a public AJAX action. Found by watching the page's own
network traffic; no docs exist for this endpoint.

  GET https://amccrs-pmb.ro/wp-admin/admin-ajax.php
      ?action=wp_ajax_ninja_tables_public_action
      &table_id=2383
      &target_action=get-all-data
      &default_sorting=old_first
      &skip_rows=0
      &limit_rows=0            # 0 = no limit, returns everything
      &ninja_table_public_nonce=<nonce>

NONCE: confirmed reusable across page loads and, now, across a full week
— the same hardcoded nonce below still worked identically on Sept 22. It
will expire eventually; scrape_nonce() re-pulls one from the live page's
embedded JSON config if a call ever starts failing.

Confirmed live (Sept 22 re-check): limit_rows=0 returns exactly the same
2,796 rows as the original investigation, same last entry ("Strada
Soldat Ghiţă Şerban (bloc 8C), Sector 3, RsIII").

No key, no login, no rate limit observed. AMCCRS is a municipal
technical agency (not a legislative/political body) — in scope per this
project's scope decision despite being municipality-published.
"""
import re

import requests

# ── Config ──
BASE = "https://amccrs-pmb.ro"
PAGE_URL = f"{BASE}/lista-imobile-2/"
AJAX_URL = f"{BASE}/wp-admin/admin-ajax.php"
TABLE_ID = 2383
TIMEOUT = 30

# Scraped Sept 15, 2026; re-confirmed still valid Sept 22, 2026. Reusable
# across calls until it eventually expires — see scrape_nonce() below.
KNOWN_NONCE = "38bfcec5fa"


def scrape_nonce() -> str:
    """
    Pull a fresh nonce straight from the live page, for when
    KNOWN_NONCE eventually expires. The page embeds it inline inside a
    JSON config blob, as part of the AJAX URL string itself
    (...&ninja_table_public_nonce=<nonce>), not as a standalone JSON
    field — matched accordingly below.
    """
    resp = requests.get(PAGE_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    match = re.search(r"ninja_table_public_nonce=([a-f0-9]+)", resp.text)
    if not match:
        raise RuntimeError("Could not find nonce in page HTML — page structure may have changed")
    return match.group(1)


RS_RE = re.compile(r"Rs\s*([IV]+)", re.IGNORECASE)
CONSOLIDATED_RE = re.compile(r"CONSOLIDAT", re.IGNORECASE)
PENDING_RE = re.compile(r"NEINCADRAT|NEÎNCADRAT", re.IGNORECASE)


def _risk_class(raw: str) -> str:
    """
    Normalize AMCCRS's raw risk-class free text into one of a fixed set
    of values: 'RsI'..'RsIV' (classified, I = highest risk), 'consolidated'
    (was at risk, since retrofitted), 'pending' (flagged urgent-category but
    not yet formally classified into a risk class), or 'unknown' for the
    small number of rows (3 of 2,796 as of Sept 2026) that are neither —
    real AMCCRS data-entry artifacts, like a technical expert's name typed
    into this field instead of a classification.

    This field is much messier than a first look suggests: only ~59% of
    rows are actually RsI-RsIV. The single largest bucket (~52%) is a
    bureaucratic status phrase meaning "flagged urgent-category, not yet
    classified" — these buildings are NOT known to be at any particular
    risk level, they're in the queue. Another ~4% read "5.CONSOLIDATE" /
    "CONSOLIDATE" — buildings that WERE at risk but have since been
    structurally retrofitted: a resolved case, not a current risk. Real
    raw text, verbatim: 'INCADRARE IN CATEGORIE DE URGENTA; NEINCADRATE IN
    CLASE DE RISC SEISMIC CORESPUNZATOARE' (-> 'pending'), '5.CONSOLIDATE'
    (-> 'consolidated'), '3.Clasa de risc seismic RsIII.' (-> 'RsIII').
    Treating any of this as a silent empty value, or lumping
    'pending'/'consolidated' in with an actual RsI-RsIV class, would
    misrepresent real buildings as more or less at-risk than AMCCRS's own
    registry actually says.
    """
    raw = (raw or "").strip()
    if not raw:
        return "unknown"
    match = RS_RE.search(raw)
    if match:
        numeral = match.group(1).upper()
        if numeral in ("I", "II", "III", "IV"):
            return f"Rs{numeral}"
    if CONSOLIDATED_RE.search(raw):
        return "consolidated"
    if PENDING_RE.search(raw):
        return "pending"
    return "unknown"


def _clean(row: dict) -> dict:
    v = row.get("value", {})
    return {
        "address": (v.get("adresa", "") + " " + v.get("nr", "")).strip(),
        "sector": v.get("sector", ""),
        "year_built": v.get("anulconstruirii", ""),
        "height_regime": (v.get("regimuldeinaltime") or "").strip(),
        "apartment_count": v.get("numardeapartamente", ""),
        "expertise_year": v.get("anulelaborariiexpertizeitehnice", ""),
        "technical_expert": (v.get(
            "expertultehnicatestatpentrucerintaesentialadecalitaterezistentamecanicasistabilitatemdrap", ""
        ) or "").strip(),
        "risk_class": _risk_class(v.get("ultimaincadrareinclasaderisc", "")),
        "previous_classifications": v.get("incadrarianterioareinclasaderisc", ""),
        "notes": v.get("observatii", ""),
    }


def _fetch_all(nonce: str = KNOWN_NONCE) -> list[dict]:
    params = {
        "action": "wp_ajax_ninja_tables_public_action",
        "table_id": TABLE_ID,
        "target_action": "get-all-data",
        "default_sorting": "old_first",
        "skip_rows": 0,
        "limit_rows": 0,
        "ninja_table_public_nonce": nonce,
    }
    resp = requests.get(AJAX_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    rows = resp.json()
    return [_clean(row) for row in rows]


def search_buildings(
    street: str = "",
    sector: str = "",
    risk_class: str = "",
    limit: int = 50,
) -> dict:
    """
    Search Bucharest's official seismic-risk building registry
    (~2,796 buildings total). All filters are optional and combine
    with AND; leave all empty to browse from the start of the list.

    street: case-insensitive substring match on the street address
    (e.g. "Calea Victoriei").
    sector: exact match, e.g. "Sector 3" (Bucharest has Sectors 1-6).
    risk_class: exact match on "RsI" (highest risk) through "RsIV"
    (lowest classified risk), or "consolidated" (was at risk, since
    retrofitted) or "pending" (flagged urgent-category, not yet
    formally classified — this is the largest single bucket, over
    half the registry). See `_risk_class()` in this module for why
    the raw AMCCRS data needs this normalization.
    limit: max buildings to return (the search runs over the full
    registry regardless; this only caps the response size).

    Returns {"total_matches": N, "buildings": [...]}, each building
    with address, sector, year built, height regime, apartment count,
    the certifying technical expert, expertise year, current risk
    class, any prior classifications, and notes.
    """
    all_rows = _fetch_all()

    street_lower = street.strip().lower()
    matches = [
        b
        for b in all_rows
        if (not street_lower or street_lower in b["address"].lower())
        and (not sector or b["sector"].strip().lower() == sector.strip().lower())
        and (not risk_class or b["risk_class"].strip().lower() == risk_class.strip().lower())
    ]

    return {
        "total_matches": len(matches),
        "buildings": matches[: max(1, limit)],
    }


if __name__ == "__main__":
    import json

    out = search_buildings(sector="Sector 3", risk_class="RsI", limit=3)
    print(json.dumps(out, indent=2, ensure_ascii=False))
