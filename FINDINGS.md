# RO Open-Data MCP — Prototype Findings (Sept 15, 2026)

Live-tested via the browser pane on your machine (the cloud sandbox's own network is locked to an allowlist and can't reach any of these sites directly — even Wikipedia gets a 403 there, so all testing below ran on your real network).

## Confirmed working

### BNR — exchange rates
- **Status: solid, ready to wrap.**
- The URL used in most community references (`www.bnr.ro/nbrfxrates.xml`) is dead — it 404s and redirects to the homepage.
- The real, current, officially documented feed lives on a dedicated subdomain: **`https://curs.bnr.ro/nbrfxrates.xml`** (also `nbrfxrates10days.xml` for the last 10 days, and `files/xml/years/nbrfxrates{YEAR}.xml` for full-year archives back to 2005).
- Fetched it live — real, clean XML, 37 currencies + gold (XAU) + IMF special drawing rights (XDR), rate as of today.
- BNR's own docs say the file updates once daily after 13:00, and explicitly ask integrators to cache locally rather than poll the HTML pages. Official XSD schema is published at `curs.bnr.ro/xsd/nbrfxrates.xsd`.
- No key, no auth, no rate limit mentioned. This is a genuinely clean one to wrap first.

### data.europa.eu — Search API (meta-tool candidate)
- **Status: SOLVED — confirmed fully working, and confirms data.gov.ro is reachable through it.**
- My first two guesses at filter syntax (`filters={"country":["ro"]}`, `filter=country:ro`) both failed with 400s. Found the real syntax by loading the actual portal search page in the browser and watching the network request it fires itself, rather than guessing further — the param is called `facets`, a JSON object of facet-name → list of values: **`facets={"country":["ro"]}`**.
- Confirmed live: `count.total` = 5,483 for country=ro, exactly matching what the portal UI shows. The first result was itself a `data.gov.ro` dataset (source_type `dcat-ap`, publisher "Guvernul României", direct XLS download link included) — meaning **data.gov.ro is harvested into this portal**, so this one working API effectively stands in for the native data.gov.ro API we never found. That's a nice bonus: one meta-tool covers both.
- Also found a theme/category vocabulary (`?filter=vocabulary&vocabulary=data-theme&limit=50`) — 14 standard EU DCAT-AP theme codes (e.g. `INTR` international issues, `AGRI` agriculture/fisheries/forestry/food). **Not yet confirmed**: whether combining `facets={"country":["ro"],"categories":["ECON"]}` (or whatever the economy/culture codes turn out to be) actually narrows results — only the country facet has been proven end-to-end so far.
- Working script with both the country search and the theme-vocabulary lookup saved as `test_data_europa.py`.

## Solved this session (after initial debugging)

### ANAF — company/VAT lookup
- **Status: SOLVED — confirmed fully working.**
- Root cause: the path documented by every community reference I found (anaf-mcp, itrack/anaf, several blog posts) is **stale**. They document `/PlatitorTvaRest/api/v9/ws/tva`; the current real path is **`/api/PlatitorTvaRest/v9/tva`** (segment order changed, "ws" dropped) — found via [anafpy's docs](https://anafpy.readthedocs.io/en/latest/anaf-reference/public/api/), which look actively maintained.
- Hitting the wrong (old) path gets intercepted by ANAF's WebSEAL gateway and returns a 403 that reads exactly like an auth wall — very easy to mistake for "this API now requires login," which is what it looked like at first.
- With the corrected path, `POST https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva` with `Content-Type: application/json` and a body like `[{"cui": 14399840, "data": "2026-09-15"}]` returns clean, complete JSON — confirmed live against eMAG (Dante International SA), OMV Petrom, and Banca Transilvania, full address/registration/VAT-status/CAEN-code data for each, no key, no login.
- Rate limit per the docs: 1 request/second, up to 100 CUIs per request.
- Updated `test_anaf.py` with the corrected path and confirmed-real test CUIs — ready to run once you're on a machine with normal internet access (this doesn't need the browser-driving trick, a plain `requests.post()` to the corrected URL works directly).
- ANAF also has several sibling endpoints worth knowing about for later: e-Factura registry, financial statements (`/bilant`), farmers' and religious-entities registries, plus async versions of the TVA lookup for bulk use.

### clasate.cimec.ro — Bunuri Clasate
- **Status: SOLVED — fully mapped end to end, no headless browser needed anywhere.**
- The homepage (`/`) is just the filter/facet form — the actual results live on a separate endpoint, `/Lista.asp`, found by inspecting the page's own links rather than guessing.
- List: `GET /Lista.asp?clasificare=tez` (or `fond`, or omit for all 116,208). Pagination looked JS-only at first (the "page 2" links have `onclick` handlers, no plain `href`) — but inspecting the hidden form those `onclick` handlers submit (`document.navigaretop`) showed it's just a plain GET form with `start` and `pageno` fields, e.g. `&start=51&pageno=2` for page 2. Confirmed live: page 1 shows "Nr. ord.: 1 - 50 din 47664", page 2 shows "51 - 100" — exactly right, no JS execution needed to replicate it.
- Each row links to `Detaliu.asp?tit=<slug>&k=<guid>` — `k` is the item's real stable key.
- Detail page: plain server-rendered HTML with rich real fields — type/subtype, description, holder institution, domain, dating, era/period, ethnicity/culture, find location, material, technique, dimensions, who catalogued/verified it, inventory number, and the classification order number/date with a direct link to the official order PDF. Real photo at `/medium/imagini55/<guid>.jpg`; 3D-scanned items additionally embed a Sketchfab model. Confirmed live against a Chalcolithic (Cucuteni culture) stone hammer-axe held by Muzeul Național al Carpaților Răsăriteni, full findspot/dating/technique data.
- **Bonus**: the site is explicitly licensed CC BY-SA 4.0 (footer link) — the only source this session with an explicit open license, worth flagging since it covers reuse of the photos too, not just the metadata.
- No key, no login, no rate limit observed. Working client (`list_page()` + `get_detail()`) saved as `test_clasate_cimec.py`.

### INS Tempo-Online — statistics
- **Status: SOLVED — confirmed fully working end to end, including the actual data pull.**
- Real API root: `http://statistici.insse.ro:8077/tempo-ins/` (note: `tempo-ins`, not `tempo-online` — that's the frontend app path). No public docs exist for this API; the full shape was reverse-engineered by watching the real frontend's network calls, cross-checked against gov2-ro/tempo-ins-dump's source code for the final step.
- Full four-step pipeline, all keyless, all confirmed live with real data:
  1. `GET /tempo-ins/context/` — top-level category tree
  2. `GET /tempo-ins/context/{code}` — drill into a category → sub-categories or dataset "matrices" (e.g. `POP105A`)
  3. `GET /tempo-ins/matrix/{matrixCode}` — full metadata: title, definition, methodology, and the selectable dimensions with their option codes
  4. `POST /tempo-ins/pivot` — the actual data pull, body includes `encQuery` (colon-separated option codes, one per dimension) plus a few metadata fields from step 3
- Tested live end-to-end: queried POP105A (resident population) for Total/Total/Total/Romania/2025 → got back **19,043,151**, Romania's real total resident population as of 1 Jan 2025.
- **Legal note worth flagging**: INS's own terms of use (in the app's config JSON) restrict reproduction/redistribution of TEMPO-Online content without written INS authorization, but explicitly allow quoting with clear source attribution. Fine for research/reference use with credit; wholesale redistribution is the part to be careful about before this goes anywhere public-facing.
- Confirmed the 30,000-cell-per-request limit is real (INS's own frontend warning text, word for word) — keep dimension selections narrow or chunk by year for wide queries.
- Full working client (4 functions covering the whole pipeline) saved as `test_ins_tempo.py`.

### AMCCRS — Bucharest seismic-risk building registry
- **Status: SOLVED — confirmed fully working, including nonce-reusability.**
- The public list page (`amccrs-pmb.ro/lista-imobile-2/`) doesn't server-render its table — it's a WordPress "Ninja Tables" plugin pulling data client-side. Found the real call by watching the page's own network traffic: `GET /wp-admin/admin-ajax.php?action=wp_ajax_ninja_tables_public_action&table_id=2383&target_action=get-all-data&skip_rows=0&limit_rows=0&ninja_table_public_nonce={nonce}`.
- **Tested the nonce specifically**: reused the nonce captured on the list page from a completely different page load (the site homepage) and it worked identically — so a script can scrape the nonce once and keep reusing it, rather than needing a fetch-page-then-extract step before every call. It'll expire eventually (standard WP nonce behavior, typically ~12-24h), so worth a "re-scrape on failure" fallback for a long-running tool, but not a per-call requirement.
- Confirmed live: `limit_rows=0` returns all **2,796 rows** — real addresses, sector, construction year, named certified structural engineers, and seismic risk classification. No key, no login, no rate limit observed.
- **Correction (Sept 2026, from building a public map on top of this data — see the separate `bucharest-seismic-risk-map` project):** the risk-class field is messier than "RsI/RsII/RsIII" suggested above. A 4th class, **RsIV**, exists in the real data (11 rows); only **~59%** of rows are actually classified into RsI-RsIV at all — the largest single bucket (~52%) is a bureaucratic status phrase meaning "flagged urgent-category, not yet formally classified," and another ~4% read "CONSOLIDATE" (was at risk, since retrofitted). `sources/amccrs.py`'s `_risk_class()` now normalizes all of this into `RsI`..`RsIV` / `consolidated` / `pending` / `unknown` instead of returning a mix of clean codes and raw Romanian status text.
- In scope per project decision: AMCCRS is a municipal technical agency, not a legislative/political body.
- Working client (`fetch_all()` + a `scrape_nonce()` fallback) saved as `test_amccrs.py`.

### LMI — historic monuments list (PDFs via cultura.ro)
- **Status: confirmed real, not yet extractable by a plain script.**
- The per-county PDF links off cultura.ro are real and load — spot-checked one, 2.17MB, genuine LMI content.
- The domain sits behind a Cloudflare challenge ("Verifying your browser..."). The browser pane cleared it fine (resolved itself after a few seconds), but a plain `requests.get()` from an unauthenticated script will very likely get the Cloudflare interstitial instead of the PDF — this needs either a Cloudflare-bypass library (e.g. `cloudscraper`) or a documented manual-download step, not yet built or tested.
- Didn't attempt full PDF text/table extraction this session (2.17MB is large to pull through the browser-pane pipeline) — once a script can reliably fetch the raw PDF, extraction is a separate, standard step (e.g. `pdfplumber`/`camelot` for the tabular monument listings).

## Not yet tested this session
Confirming data.europa.eu's theme/category filter codes (whether `categories` facet actually narrows results beyond `country`) — flagged as still open in `test_data_europa.py`.

## Recommended next step
Six of seven sources are fully solved and ready to wrap as MCP tools today: **BNR, ANAF, data.europa.eu (country search), INS Tempo-Online, AMCCRS, clasate.cimec.ro**. Only LMI remains blocked — it needs a Cloudflare-bypass approach before it's scriptable. data.europa.eu's theme filtering is a nice-to-have to confirm later, not a blocker — the country facet alone is already a strong meta-tool.

## Summary table

| Source | Status | Auth/key | Notes |
|---|---|---|---|
| BNR (exchange rates) | Solved | None | Daily XML, cache locally |
| ANAF (VAT/company lookup) | Solved | None | 1 req/s, 100 CUIs/request |
| data.europa.eu (search, incl. data.gov.ro) | Solved | None | Theme-filter codes not yet confirmed |
| INS Tempo-Online (statistics) | Solved | None | Redistribution restricted, quoting OK |
| AMCCRS (Bucharest seismic risk) | Solved | None (reusable nonce) | Municipal agency, in scope |
| clasate.cimec.ro (Bunuri Clasate) | Solved | None | CC BY-SA 4.0 licensed — the only explicitly open-licensed source so far |
| LMI (historic monuments PDFs) | Partial | None | Cloudflare-protected, needs bypass |
