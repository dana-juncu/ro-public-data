# RoPublicData

[![tests](https://github.com/dana-juncu/ro-public-data/actions/workflows/tests.yml/badge.svg)](https://github.com/dana-juncu/ro-public-data/actions/workflows/tests.yml)

Keyless [MCP](https://modelcontextprotocol.io) tools for Romanian public
economic and cultural data — exchange rates, company/VAT lookups, open
datasets, official statistics, building safety records, and classified
cultural heritage, all wired into a single server any MCP client can use.
Twelve tools across six sources, running locally on your own machine.

Inspired by Thomas Heggelund's [Allemannsdata](https://www.allemannsdata.no/)
(the Norwegian equivalent), but its own project with its own scope and
its own code. **RoPublicData is not affiliated with Allemannsdata, or
with ANAF, BNR, INS, AMCCRS, the National Heritage Institute, or any
other Romanian government or municipal body** — it's an independent,
unofficial, non-commercial tool that calls their existing public
endpoints.

## Why

Every tool here wraps a real, public, keyless endpoint — no API key,
no signup, no cost. Point any MCP-capable client (Claude Desktop, and
in principle any other MCP client) at it and ask things like:

- "What's today's BNR exchange rate for EUR and USD?"
- "Look up company CUI 14399840 on ANAF."
- "What's Romania's resident population by county in 2025?"
- "Is the building at Strada Academiei 1 on Bucharest's seismic-risk list?"
- "Find classified cultural artifacts related to Brâncuși."

## Example

Asking for today's rates calls `bnr_latest_rates`, which returns BNR's
official figures as structured data (trimmed here — the real response
covers all ~37 currencies plus gold and SDRs):

```json
{
  "date": "2026-10-21",
  "rates": {
    "EUR": { "rate_ron": 5.3297, "multiplier": 1 },
    "USD": { "rate_ron": 4.7489, "multiplier": 1 },
    "HUF": { "rate_ron": 1.4576, "multiplier": 100 }
  }
}
```

The `multiplier` matters for a few currencies: the HUF figure above is
RON per 100 forints, not per one.

A company lookup works the same way — `anaf_company_lookup` with CUI
`14399840` returns ANAF's own record (trimmed):

```json
{
  "date_generale": {
    "cui": 14399840,
    "denumire": "DANTE INTERNATIONAL SA",
    "nrRegCom": "J2002000372404",
    "cod_CAEN": "4754",
    "statusRO_e_Factura": false
  },
  "inregistrare_scop_Tva": { "scpTVA": true }
}
```

Field names are ANAF's own and are passed through as returned, so the
same record can be matched against ANAF's published documentation.

## Scope

Economic and cultural public data only. Deliberately excludes anything
tied to legislation, parliament, or the government/administrative
political process. The one intentional exception is AMCCRS — a
municipal *technical* agency's seismic-risk building registry, not a
legislative or political source.

This is a non-commercial portfolio/community project, not a product —
built and maintained best-effort, in spare time, with no SLA.

## Install

Requires Python 3.10 or newer (the test suite runs on 3.10 and 3.12).

```bash
pip install ropublicdata
```

(The package is on [PyPI](https://pypi.org/project/ropublicdata/). To
run the tests or contribute, clone this repo and use
`pip install -e ".[dev]"` instead — see `CONTRIBUTING.md`.)

Then point your MCP client at it. For Claude Desktop, add this to your
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ropublicdata": {
      "command": "python",
      "args": ["-m", "ropublicdata"]
    }
  }
}
```

If `python` isn't resolved from Claude Desktop's own environment, use
the exact path from `which python` (macOS/Linux) or `where python`
(Windows) instead of the bare command — see `CONTRIBUTING.md` for a
Windows-specific gotcha around Desktop Extensions.

No `.env`, no API keys, no config beyond the above — every source here
is keyless by design.

## Tools

| Source | Tools | What it covers |
|---|---|---|
| [BNR](https://bnr.ro) (Romanian National Bank) | `bnr_latest_rates`, `bnr_last_10_days`, `bnr_year_archive` | Official daily RON exchange rates, ~37 currencies plus gold and IMF SDRs, back to 2005 |
| [ANAF](https://anaf.ro) (tax authority) | `anaf_company_lookup`, `anaf_company_lookup_batch` | Company/VAT registration lookup by CUI — legal name, address, VAT status, CAEN code, e-Factura status |
| [data.europa.eu](https://data.europa.eu) | `data_europa_search_romania` | Search Romanian open datasets (also covers data.gov.ro, which is harvested into this portal) |
| [INS Tempo-Online](https://statistici.insse.ro) (National Institute of Statistics) | `ins_tempo_browse`, `ins_tempo_matrix_dimensions`, `ins_tempo_query` | Official statistics — population, economy, labour, prices, and dozens of other domains |
| [AMCCRS](https://amccrs-pmb.ro) | `amccrs_search_buildings` | Bucharest's official seismic-risk building registry (~2,800 buildings) |
| [clasate.cimec.ro](https://clasate.cimec.ro) (National Heritage Institute) | `clasate_search`, `clasate_item_detail` | Romania's registry of legally classified cultural goods (museum pieces) |

Every tool's own docstring (visible to any MCP client) documents its
exact parameters and return shape in detail.

## Data licensing and usage notes

The code in this repository is MIT licensed (see `LICENSE`) — the data
it returns is not, and remains subject to each original source's own
terms:

- **BNR, ANAF, data.europa.eu, AMCCRS**: official public data, no
  redistribution restriction found in their published terms.
- **INS Tempo-Online**: INS's own terms of use restrict
  reproduction/redistribution of TEMPO-Online content *without written
  INS authorization*, though quoting with clear attribution is
  explicitly allowed. Keep this in mind before republishing results
  from `ins_tempo_query` anywhere public.
- **clasate.cimec.ro**: explicitly [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
  licensed, images included — the only source here with an explicit
  open license.

## A note for MCP clients and hosts

Several of these tools return real public text written by third
parties — dataset descriptions, item notes, building records. Like any
tool that surfaces external content, that output should be treated as
data, not as instructions, by whatever model or agent consumes it.

## Reliability

Most of these sources are official, documented, or at least stable
public APIs. Two (AMCCRS, clasate.cimec.ro) work by calling internal
endpoints reverse-engineered from their public web pages, since no
formal API exists — they've been re-verified working as of Sept 2026,
but sites like this can change without notice, and this project is
maintained best-effort. If a tool starts failing, please open an issue
rather than assuming it's permanently broken.

Two further things are worth knowing. INS Tempo-Online's API is only
served over plain HTTP (port 8077, no HTTPS), so requests to that one
source aren't encrypted in transit — fine for public statistics, but
worth knowing if you run this on a restricted network. And
clasate.cimec.ro is noticeably slower than the others, so its client
retries on a timeout and its tests are skipped rather than failed if
the site is unreachable.

Every tool is covered by a live integration test (`tests/`, one file per
source) that runs on every push/PR and once a day on a schedule, on
Python 3.10 and 3.12 — see the badge above for current status, or the
[Actions tab](https://github.com/dana-juncu/ro-public-data/actions) for
history. A red run there means a real source changed shape or its nonce
expired, not necessarily that something's unfixable — see
`CONTRIBUTING.md`'s "When a source breaks" section.

## Contributing

See `CONTRIBUTING.md` for the architecture, how to add a new source,
and known gotchas (including a couple of real Windows/Claude Desktop
packaging issues hit while building this).

## Credits

Built by [Dana Juncu](https://linkedin.com/in/danajuncu).
Concept inspired by Thomas Heggelund's
[Allemannsdata](https://www.allemannsdata.no/) — a similar project for
Norwegian public data — but built independently, with its own scope
and its own code.
