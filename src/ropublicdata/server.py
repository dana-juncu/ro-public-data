"""
RoPublicData MCP Server

A non-commercial hub of keyless MCP tools wrapping Romanian public
economic and cultural data sources — inspired by Thomas Heggelund's
Allemannsdata (the Norwegian equivalent), but its own project with its
own scope: Romania's economic and cultural open data, deliberately
excluding legislation/parliament/administrative-political content.

Every tool here is read-only, needs no API key, and hits a real public
endpoint that was live-tested and documented in FINDINGS.md before being
wrapped. See FINDINGS.md for the investigation behind each source, and
sources/ for the standalone client each tool calls.

── Adding a new source ──
1. Prototype it as sources/<name>.py — plain functions, no MCP-specific
   code, testable and runnable standalone (see sources/bnr.py).
2. Register one @mcp.tool() wrapper per function below, with a clear
   docstring — that docstring is what an MCP client (and the model
   using it) sees, so make it describe the real data, not just repeat
   the function name.
3. Update the SOURCES table in README.md.

Run: ropublicdata  (installed console script), or python -m ropublicdata,
or python src/ropublicdata/server.py during development.
"""
from mcp.server.mcpserver import MCPServer

from ropublicdata.sources import amccrs, anaf, bnr, clasate_cimec, data_europa, ins_tempo

# ── Config ──
SERVER_NAME = "ropublicdata"

mcp = MCPServer(SERVER_NAME)


@mcp.tool()
def bnr_latest_rates() -> dict:
    """
    Get today's official BNR (Romanian National Bank) reference exchange
    rates — RON per unit of foreign currency for ~37 currencies plus gold
    (XAU) and IMF special drawing rights (XDR). Updates once daily after
    13:00 Romania time; BNR asks integrators to cache rather than poll.
    Returns {"date": "YYYY-MM-DD", "rates": {"EUR": {"rate_ron": 5.26,
    "multiplier": 1}, ...}}. A `multiplier` other than 1 (e.g. HUF, JPY)
    means the rate is per that many units of the currency.
    """
    return bnr.get_latest_rates()


@mcp.tool()
def bnr_last_10_days() -> list[dict]:
    """
    Get BNR's official exchange rates for each of the last 10 days,
    oldest first. Same shape as bnr_latest_rates, one entry per day.
    Useful for short-term trend questions without hitting the
    per-year archive.
    """
    return bnr.get_last_10_days()


@mcp.tool()
def bnr_year_archive(year: int) -> list[dict]:
    """
    Get BNR's full official exchange-rate history for a given year
    (available back to 2005). Same per-day shape as bnr_latest_rates.
    Use this for historical/backtesting questions rather than scraping
    day by day.
    """
    return bnr.get_year_archive(year)


@mcp.tool()
def anaf_company_lookup(cui: int, as_of: str = "") -> dict | None:
    """
    Look up a single Romanian company by CUI (its tax/registration
    number) via ANAF, Romania's tax authority. Returns real registration
    data as of a given date (YYYY-MM-DD; defaults to today if omitted):
    legal name, address, registration status/date, trade registry number
    (nrRegCom), CAEN activity code, VAT-payer status and history, and
    e-Factura/split-VAT/inactive-taxpayer flags. Returns null if ANAF has
    no record for that CUI. No key needed.
    """
    return anaf.get_company(cui, as_of=as_of or None)


@mcp.tool()
def anaf_company_lookup_batch(cuis: list[int], as_of: str = "") -> list[dict]:
    """
    Look up multiple Romanian companies by CUI in one call (up to 100 —
    ANAF accepts a whole batch in a single request, so prefer this over
    calling anaf_company_lookup repeatedly). Same per-company fields as
    anaf_company_lookup. CUIs ANAF has no record for are simply omitted
    from the results, not treated as errors.
    """
    return anaf.get_companies(cuis, as_of=as_of or None)


@mcp.tool()
def data_europa_search_romania(
    query: str = "",
    theme: str = "",
    limit: int = 10,
    page: int = 0,
) -> dict:
    """
    Search Romanian public datasets on data.europa.eu, the EU-wide open
    data portal — which harvests data.gov.ro and other Romanian government
    catalogs directly, so this one tool covers Romania's national open
    data portal too. Always scoped to Romania.

    query: free-text search (e.g. "buget", "energie", "accidente
    rutiere"). Leave empty to browse the most recently updated Romanian
    datasets instead of searching.
    theme: optional EU theme code to narrow results, e.g. "ECON" (economy
    and finance) or "EDUC" (education, culture and sport — the closest EU
    code to "culture"). Use sparingly: most Romanian datasets on this
    portal aren't tagged with any theme, so this can hide real results
    rather than just narrowing them.
    limit: max results per page (capped at 100). page: zero-based, for
    paging through more results.

    Returns {"total": N, "results": [...]}, each with title, description,
    publisher, source catalog, modified/issued dates, available file
    formats, and a direct URL to the dataset page.
    """
    return data_europa.search_romania_datasets(
        query=query, theme=theme or None, limit=limit, page=page
    )


@mcp.tool()
def ins_tempo_browse(code: str = "") -> dict:
    """
    Browse INS Tempo-Online's statistical category tree — Romania's
    National Institute of Statistics data warehouse, covering
    population, economy, labour, prices, culture, and dozens of other
    official domains.

    code="" (default): returns the FULL category tree in one call —
    every category and sub-category (~340), flattened, each with its
    code, name, parent code, and nesting level. Good for finding a
    topic by keyword across the whole tree at once.
    code=<a category code from that tree>: drills into it, returning
    its direct children — either more sub-categories, or (at a leaf)
    the actual dataset "matrices" available there, each with the
    matrix code ins_tempo_matrix_dimensions() and ins_tempo_query()
    need.
    """
    return ins_tempo.browse(code)


@mcp.tool()
def ins_tempo_matrix_dimensions(matrix_code: str) -> dict:
    """
    Get one INS statistics matrix's title and every selectable
    dimension (e.g. age, sex, region, year) with the exact option
    labels and IDs ins_tempo_query() needs. ALWAYS call this before
    ins_tempo_query() — dimension order and option IDs vary per matrix
    and can't be guessed. Find matrix codes via ins_tempo_browse().
    """
    return ins_tempo.matrix_dimensions(matrix_code)


@mcp.tool()
def ins_tempo_query(matrix_code: str, selections: list[int]) -> list[dict]:
    """
    Pull actual official statistics data from one INS Tempo-Online
    matrix. `selections` must be one option ID per dimension, in the
    same order as ins_tempo_matrix_dimensions()'s dimensions list —
    always call that first to get valid IDs for the matrix you want.
    Keep selections narrow: INS rejects queries whose selected options
    multiply out to more than ~30,000 cells, so prefer several narrow
    calls (e.g. one per year) over one very wide one. Returns each
    result row as a dict of dimension labels to their chosen values,
    plus the numeric "Valoare" (value).

    Note: INS's terms restrict reproducing/redistributing this data
    without written authorization, though quoting with attribution is
    explicitly allowed — keep that in mind before using results in
    anything published.
    """
    return ins_tempo.query(matrix_code, selections)


@mcp.tool()
def amccrs_search_buildings(
    street: str = "",
    sector: str = "",
    risk_class: str = "",
    limit: int = 50,
) -> dict:
    """
    Search Bucharest's official seismic-risk building registry
    (AMCCRS), ~2,796 buildings total. All filters are optional and
    combine with AND; leave everything empty to browse from the start
    of the list.

    street: case-insensitive substring match on the street address
    (e.g. "Calea Victoriei").
    sector: exact match, e.g. "Sector 3" (Bucharest has Sectors 1-6).
    risk_class: exact match on "RsI" (highest risk), "RsII", or
    "RsIII" (lowest of the three classified risk levels).
    limit: max buildings to return (the search still runs over the
    full registry; this only caps the response size).

    Returns {"total_matches": N, "buildings": [...]}, each with
    address, sector, year built, height regime, apartment count, the
    certifying technical expert, expertise year, current risk class,
    any prior classifications, and notes.
    """
    return amccrs.search_buildings(street=street, sector=sector, risk_class=risk_class, limit=limit)


@mcp.tool()
def clasate_search(
    query: str = "",
    clasificare: str = "",
    obiect3d: bool = False,
    page: int = 1,
) -> dict:
    """
    Search Romania's official registry of classified cultural goods
    (Bunuri Culturale Clasate) — legally protected museum pieces, CC
    BY-SA 4.0 licensed (images included).

    query: free-text search across the whole registry (e.g.
    "Brancusi", "amfora", a museum name).
    clasificare: "tez" (Tezaurul Patrimoniului Cultural Naţional, the
    highest protection tier) or "fond" (Fondul Patrimoniului Cultural
    Naţional). Leave empty for both.
    obiect3d: if true, only items with an interactive 3D scan.
    page: 1-based page number, 50 items per page.

    Returns {"total_matches": N, "page": page, "items": [...]}, each
    with holder institution, county, category, title, author, domain,
    classification order, a thumbnail, and enough (`k`/`tit`) to call
    clasate_item_detail() for the full record.
    """
    return clasate_cimec.search_items(query=query, clasificare=clasificare, obiect3d=obiect3d, page=page)


@mcp.tool()
def clasate_item_detail(k: str, tit: str = "item") -> dict:
    """
    Get the full record for one classified cultural good, by its
    stable key `k` (get `k` and `tit` from clasate_search() results —
    `tit` is just a cosmetic slug and doesn't need to be exact).

    Returns every field the item's page actually has (varies per
    item — archaeological pieces carry dating/era/culture/findspot,
    others don't) plus image_url (the item's real photo, when
    present), pdf_url (the official classification order document,
    when available), and sketchfab_url (an embeddable 3D model, for
    scanned items). CC BY-SA 4.0 licensed — safe to reuse with
    attribution, including the images.
    """
    return clasate_cimec.get_item_detail(k, tit)


def main() -> None:
    """Entry point for the `ropublicdata` console script and `python -m ropublicdata`."""
    mcp.run()


if __name__ == "__main__":
    main()
