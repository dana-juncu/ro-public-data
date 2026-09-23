"""
BNR (Banca Naţională a României) — official daily exchange rates.

Source confirmed live Sept 2026 (see ../FINDINGS.md for the full
investigation). The URL used in most community references
(www.bnr.ro/nbrfxrates.xml) is dead; the real, current feed lives on a
dedicated subdomain.

No key, no auth, no rate limit documented. BNR's own docs say the file
updates once daily after 13:00 and ask integrators to cache locally
rather than poll the HTML pages.

GOTCHA (found via a live CI failure, Sept 2026): BNR's own XML feeds
don't agree on their namespace URI. The daily feed and the 10-days feed
use `xmlns="https://www.bnr.ro/xsd"` (https), but the per-year archive
files use `xmlns="http://www.bnr.ro/xsd"` (plain http, no 's') — at
least for 2020, spot-checked live. A namespace-exact XPath query against
one hardcoded URI silently returns zero results on whichever feed uses
the other one, with no error — it looks like "no data for that year"
rather than "wrong namespace". Matched with a wildcard namespace
(`{*}Cube`) below instead, so it doesn't matter which URI a given feed
happens to use.

GOTCHA 2 (same CI run): the 10-days feed's own XML doesn't actually come
back oldest-first, despite that being the natural reading of "last 10
days" -- live-confirmed it's newest-first (today's Cube first). Sorted
explicitly below so `get_last_10_days()` has one stable, documented
order regardless of what BNR's raw feed does today or does differently
in the future.
"""
from xml.etree import ElementTree

import requests

# ── Config ──
BASE_URL = "https://curs.bnr.ro"
LATEST_URL = f"{BASE_URL}/nbrfxrates.xml"
LAST_10_DAYS_URL = f"{BASE_URL}/nbrfxrates10days.xml"
YEAR_ARCHIVE_URL = f"{BASE_URL}/files/xml/years/nbrfxrates{{year}}.xml"
TIMEOUT = 20


def _parse_cube(cube_el: ElementTree.Element) -> dict:
    """Turn one <Cube date="..."> element into a plain dict."""
    rates = {}
    # Wildcard namespace ({*}) rather than a hardcoded URI -- see the
    # module docstring's GOTCHA: BNR's own feeds don't agree on http vs
    # https for this namespace.
    for rate_el in cube_el.findall("{*}Rate"):
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
    cube = root.find(".//{*}Cube")
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
    cubes = root.findall(".//{*}Cube")
    if not cubes:
        raise RuntimeError(
            f"Unexpected BNR XML structure — no <Cube> elements found. "
            f"Check {LAST_10_DAYS_URL} manually."
        )
    # Sort oldest-first explicitly -- see the module docstring's GOTCHA 2:
    # the raw feed is actually newest-first, the opposite of what "last 10
    # days" suggests.
    return sorted((_parse_cube(c) for c in cubes), key=lambda day: day["date"])


def get_year_archive(year: int) -> list[dict]:
    """Fetch every daily rate published in a given year (back to 2005)."""
    url = YEAR_ARCHIVE_URL.format(year=year)
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)
    cubes = root.findall(".//{*}Cube")
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
