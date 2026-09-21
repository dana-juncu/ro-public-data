"""
BNR (Banca Naţională a României) — official daily exchange rates.

Source confirmed live Sept 2026 (see ../FINDINGS.md for the full
investigation). The URL used in most community references
(www.bnr.ro/nbrfxrates.xml) is dead; the real, current feed lives on a
dedicated subdomain.

No key, no auth, no rate limit documented. BNR's own docs say the file
updates once daily after 13:00 and ask integrators to cache locally
rather than poll the HTML pages.
"""
from xml.etree import ElementTree

import requests

# ── Config ──
BASE_URL = "https://curs.bnr.ro"
LATEST_URL = f"{BASE_URL}/nbrfxrates.xml"
LAST_10_DAYS_URL = f"{BASE_URL}/nbrfxrates10days.xml"
YEAR_ARCHIVE_URL = f"{BASE_URL}/files/xml/years/nbrfxrates{{year}}.xml"
XML_NS = {"bnr": "https://www.bnr.ro/xsd"}
TIMEOUT = 20


def _parse_cube(cube_el: ElementTree.Element) -> dict:
    """Turn one <Cube date="..."> element into a plain dict."""
    rates = {}
    for rate_el in cube_el.findall("bnr:Rate", XML_NS):
        currency = rate_el.get("currency")
        multiplier = int(rate_el.get("multiplier", "1"))
        rates[currency] = {
            "rate_ron": float(rate_el.text),
            "multiplier": multiplier,
        }
    return {"date": cube_el.get("date"), "rates": rates}


def get_latest_rates() -> dict:
    """
    Fetch today's official BNR reference rates (RON per unit of foreign
    currency, or per `multiplier` units for a few high-denomination
    currencies like JPY/HUF — see the `multiplier` field).
    """
    resp = requests.get(LATEST_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)
    cube = root.find(".//bnr:Cube", XML_NS)
    if cube is None:
        raise RuntimeError(
            f"Unexpected BNR XML structure — no <Cube> found. "
            f"Root tag was {root.tag!r}; check {LATEST_URL} manually."
        )
    return _parse_cube(cube)


def get_last_10_days() -> list[dict]:
    """Fetch the last 10 days of rates — one dict per day, oldest first."""
    resp = requests.get(LAST_10_DAYS_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)
    cubes = root.findall(".//bnr:Cube", XML_NS)
    if not cubes:
        raise RuntimeError(
            f"Unexpected BNR XML structure — no <Cube> elements found. "
            f"Check {LAST_10_DAYS_URL} manually."
        )
    return [_parse_cube(c) for c in cubes]


def get_year_archive(year: int) -> list[dict]:
    """Fetch every daily rate published in a given year (back to 2005)."""
    url = YEAR_ARCHIVE_URL.format(year=year)
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)
    cubes = root.findall(".//bnr:Cube", XML_NS)
    if not cubes:
        raise RuntimeError(
            f"Unexpected BNR XML structure — no <Cube> elements found for "
            f"year {year}. Check {url} manually (years before 2005 don't exist)."
        )
    return [_parse_cube(c) for c in cubes]


if __name__ == "__main__":
    latest = get_latest_rates()
    print(f"BNR rates for {latest['date']}:")
    for ccy, info in sorted(latest["rates"].items()):
        mult = f" (per {info['multiplier']})" if info["multiplier"] != 1 else ""
        print(f"  1 {ccy}{mult} = {info['rate_ron']} RON")
