"""
clasate.cimec.ro — Bunuri Culturale Clasate (Romania's official registry
of classified cultural goods: museum pieces legally protected under the
"Tezaur" or "Fond" tiers of the National Cultural Heritage).

Source confirmed live Sept 16, 2026 and RE-confirmed (with a richer
parse than the original prototype) Sept 22, 2026 — see ../FINDINGS.md
for the original investigation.

Two-level structure, both plain server-rendered HTML, no JS execution
or headless browser needed anywhere:

  1. LIST: GET /Lista.asp
     Query params (all optional, combine freely):
       - psearch=<text>          free-text search (confirmed live: also
                                  matches thematic collections, e.g.
                                  "Brancusi" -> 46 real results)
       - clasificare=tez | fond  legal classification tier
       - obiect3d=da             only items with a 3D scan
       - start=<N> & pageno=<N>  pagination — 50 rows/page, both params
                                  required together (start is the 1-based
                                  row offset)
     Each row is a <tr> with <td data-title="..."> cells — confirmed
     richer than the original prototype knew: Detinator (holder),
     Judet (county), Categorie, Titlu, Autor, Domeniu, Clasare (order),
     and a thumbnail — enough to browse/filter without a detail fetch
     per item.

  2. DETAIL: GET /Detaliu.asp?tit=<slug>&k=<guid>
     `tit` is a cosmetic slug (doesn't need to be exact/current); `k`
     is the item's real stable key. Every field on the page follows the
     same "<b>Label: </b> value" pattern (Tip, Descriere, Deţinător,
     Domeniu, Datare, Epoca/Perioada, Etnia/Cultura, Loc de descoperire,
     Material/Tehnică, Nr. inventar, Ordin de clasare, ...) — parsed
     generically below rather than hardcoding a fixed field list, since
     which fields are present varies per item. Also carries a real photo
     (/medium/imaginiNN/<guid>.jpg), sometimes a classification-order PDF
     (/omc/OMC-<order>.PDF), and 3D-scanned items embed a Sketchfab model.

Page is explicitly CC BY-SA 4.0 licensed (footer link to
creativecommons.org/licenses/by-sa/4.0) — the only source in this
project with an explicit open license, covering the images too.

No key, no login, no rate limit observed.

GOTCHA (found via two separate live CI failures, Sept 2026): this site
is noticeably slower/less consistent than the others here — a plain GET
occasionally takes longer than a generous timeout with no other symptom
(not a 403, not a redirect, just slow or briefly unreachable),
independent of any client-side rate limiting. The first fix here (one
retry, 20s timeout) wasn't enough — a second live CI run still hit it on
both calls, meaning the slow/unreachable window can run well past 20s.
Bumped to 2 retries with a longer timeout and a backoff pause
(`_get_with_retry` below); a genuine outage still eventually raises, it
just takes longer to give up. Not a code bug, just this specific
unofficial, no-SLA site under real-world conditions — see
CONTRIBUTING.md's "When a source breaks".
"""
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ── Config ──
BASE = "https://clasate.cimec.ro"
TIMEOUT = 25
RETRIES = 2
RETRY_PAUSE = 5  # seconds, doubled after each retry
PAGE_SIZE = 50


def _get_with_retry(url: str, params: dict) -> requests.Response:
    """GET with a couple of retries on timeout/connection error -- see the
    module docstring's GOTCHA. Any other failure (4xx/5xx, etc.) still
    raises immediately, same as a plain requests.get()."""
    pause = RETRY_PAUSE
    for attempt in range(RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt == RETRIES:
                raise
            time.sleep(pause)
            pause *= 2
    resp.raise_for_status()
    return resp


def _absolute(url: str) -> str:
    return urljoin(BASE + "/", url) if url else ""


def _parse_count(text: str) -> int:
    match = re.search(r"din\s*([\d.,]+)", text)
    if not match:
        return 0
    return int(match.group(1).replace(".", "").replace(",", ""))


def search_items(
    query: str = "",
    clasificare: str = "",
    obiect3d: bool = False,
    page: int = 1,
) -> dict:
    """
    Search Romania's official registry of classified cultural goods
    (Bunuri Culturale Clasate) — museum pieces legally protected under
    the "Tezaur" (highest tier) or "Fond" classification.

    query: free-text search across the whole registry (e.g. "Brancusi",
    "amfora", a museum name).
    clasificare: "tez" (Tezaurul Patrimoniului Cultural Naţional, the
    highest tier) or "fond" (Fondul Patrimoniului Cultural Naţional).
    Leave empty for both.
    obiect3d: if true, only items with an interactive 3D scan.
    page: 1-based page number, 50 items per page.

    Returns {"total_matches": N, "page": page, "items": [...]}, each
    item with holder institution, county, category, title, author,
    domain, classification order, a thumbnail image URL, and the item's
    own detail-page URL (pass its `k` and `tit` to get_item_detail()
    for the full record).
    """
    params = {"start": (page - 1) * PAGE_SIZE + 1, "pageno": page}
    if query:
        params["psearch"] = query
    if clasificare:
        params["clasificare"] = clasificare
    if obiect3d:
        params["obiect3d"] = "da"

    resp = _get_with_retry(f"{BASE}/Lista.asp", params)
    soup = BeautifulSoup(resp.text, "html.parser")

    count_text = soup.get_text(" ", strip=True)
    total = _parse_count(count_text)

    items = []
    for row in soup.select("tbody tr"):
        cells = {
            td.get("data-title", "").strip(): td.get_text(" ", strip=True)
            for td in row.select("td[data-title]")
        }
        if not cells:
            continue
        link = row.select_one('a[href^="Detaliu.asp"]')
        img = row.select_one("img")

        k = tit = ""
        if link:
            match = re.search(r"tit=([^&]+)&k=([a-f0-9]+)", link.get("href", ""))
            if match:
                tit, k = match.group(1), match.group(2)

        items.append({
            "k": k,
            "tit": tit,
            "url": f"{BASE}/Detaliu.asp?tit={tit}&k={k}" if k else "",
            "holder": cells.get("Detinator", ""),
            "county": cells.get("Judet", ""),
            "category": cells.get("Categorie", ""),
            "title": cells.get("Titlu", "").strip().replace("\xa0", ""),
            "author": cells.get("Autor", "").strip().replace("\xa0", ""),
            "domain": cells.get("Domeniu", ""),
            "classification": cells.get("Clasare", ""),
            "thumbnail_url": _absolute(img["src"]) if img and img.get("src") else "",
        })

    return {"total_matches": total, "page": page, "items": items}


def get_item_detail(k: str, tit: str = "item") -> dict:
    """
    Get the full record for one classified cultural good, by its
    stable key `k` (and cosmetic slug `tit` — from search_items()'s
    `k`/`tit` fields; `tit` doesn't need to be exact).

    Returns every "Label: value" field the item's page actually has
    (varies per item — e.g. archaeological pieces have Datare/
    Epoca/Etnia, others don't) as a flat dict, plus image_url (the
    item's real photo, when present), pdf_url (the official
    classification order document, when scanned/available), and
    sketchfab_url (an embeddable 3D model, for scanned items).
    """
    resp = _get_with_retry(f"{BASE}/Detaliu.asp", {"tit": tit, "k": k})
    soup = BeautifulSoup(resp.text, "html.parser")

    fields = {}
    for b in soup.find_all("b"):
        label = b.get_text(strip=True).rstrip(":").strip()
        if not label:
            continue
        parent = b.parent
        if not parent:
            continue
        full_text = parent.get_text(" ", strip=True)
        raw_label = b.get_text(strip=True)
        value = full_text[len(raw_label):].strip() if full_text.startswith(raw_label) else full_text
        if value:
            fields[label] = value

    img = soup.select_one('img[src*="medium/imagini"]')
    pdf_match = re.search(r'href="([^"]*\.PDF[^"]*)"', resp.text, re.IGNORECASE)
    sketchfab_match = re.search(r'(https://sketchfab\.com/models/[a-f0-9]+/embed[^"]*)', resp.text)

    return {
        "k": k,
        "tit": tit,
        "url": f"{BASE}/Detaliu.asp?tit={tit}&k={k}",
        "fields": fields,
        "image_url": _absolute(img["src"]) if img and img.get("src") else "",
        "pdf_url": _absolute(pdf_match.group(1)) if pdf_match else "",
        "sketchfab_url": sketchfab_match.group(1) if sketchfab_match else "",
        "license": "CC BY-SA 4.0",
    }


if __name__ == "__main__":
    import json

    results = search_items(query="Brancusi", page=1)
    print(f"Total matches: {results['total_matches']}")
    print(json.dumps(results["items"][:2], indent=2, ensure_ascii=False))

    if results["items"]:
        first = results["items"][0]
        detail = get_item_detail(first["k"], first["tit"])
        print(json.dumps(detail, indent=2, ensure_ascii=False))
