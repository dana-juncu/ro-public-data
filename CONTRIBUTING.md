# Contributing to RoPublicData

This is a solo, best-effort project — there's no formal review process,
but issues and PRs are welcome, especially for a source drifting (see
"When a source breaks" below) or a new source proposal that fits the
scope in `README.md`.

## Architecture

One MCP server, one tool per data operation, grouped by source. Each
source's actual HTTP/parsing logic lives in its own plain-function
module under `src/ropublicdata/sources/` — no MCP-specific code,
runnable and testable standalone (e.g. `python -m ropublicdata.sources.bnr`
from a dev install). `server.py` just wraps each function in an
`@mcp.tool()` with a docstring — that docstring is what an MCP client
(and the model using it) actually sees, so it describes the real data
returned, not just the function name.

```
RoPublicData/
├── pyproject.toml            # package metadata + the `ropublicdata` console script
├── LICENSE                   # MIT (code only — see README's data-licensing section)
├── README.md                 # public-facing docs
├── FINDINGS.md                # full investigation notes per source (how each
│                              # endpoint was found/verified, response shapes, gotchas)
├── src/ropublicdata/
│   ├── __init__.py
│   ├── __main__.py           # enables `python -m ropublicdata`
│   ├── server.py             # MCP server — tool registration only
│   └── sources/
│       ├── bnr.py             # BNR client — HTTP + XML parsing
│       ├── anaf.py            # ANAF client — HTTP + JSON parsing
│       ├── data_europa.py     # data.europa.eu client — HTTP + JSON parsing
│       ├── ins_tempo.py       # INS Tempo-Online client — HTTP + CSV parsing
│       ├── amccrs.py          # AMCCRS client — HTTP + JSON parsing
│       └── clasate_cimec.py   # clasate.cimec.ro client — HTTP + HTML parsing
└── test_mcp_client.py         # pure-Python MCP client, no npm needed —
                                # verifies the installed package end-to-end
```

Why one server instead of one-per-source: every source here is a
read-only, keyless wrapper with no shared state — a single server with
several tools is simpler to run, simpler to point a client at once, and
mirrors how Allemannsdata itself works as one hub.

## Dev setup

```bash
git clone <this repo>
cd RoPublicData
pip install -e .
```

`server.py` runs standalone too (`python -m ropublicdata`) for a quick
sanity check, but a stdio MCP server prints nothing and just sits there
waiting for a client, which looks exactly like it's frozen — that
silence is correct. `test_mcp_client.py` actually exercises it
end-to-end (spawns it as a subprocess, lists tools, calls one) without
needing any MCP client installed — good for verifying a change before
opening a PR.

## Adding a new source

1. Prototype it as `src/ropublicdata/sources/<name>.py` — plain
   functions, testable standalone (copy the shape of `sources/bnr.py`).
   Verify the real request/response shape live (browser devtools network
   tab, or a quick script) rather than trusting docs or an old capture
   — see "When a source breaks" below for why.
2. Register one `@mcp.tool()` wrapper per function in `server.py`, with
   a docstring that describes the real data returned, not just the
   function name.
3. Update the tools table in `README.md`.
4. If the source has any redistribution/attribution terms, note them
   in README's "Data licensing and usage notes" section.

Scope check before proposing a new source: economic and cultural public
data only, no legislation/parliament/administrative-political content
(see README's Scope section for the one intentional exception).

## When a source breaks

Every source here was live-verified at the time it was wired in — see
`FINDINGS.md` for the original investigation of each — but these are
public endpoints outside this project's control, and two of them
(AMCCRS, clasate.cimec.ro) are reverse-engineered internal endpoints
with no formal API contract at all. One already changed shape mid-build
(data.europa.eu's search API renamed a param, dropped its `q=*`
wildcard, and changed its count field from a nested object to a plain
integer, all without any changelog). If a tool starts failing:

1. Re-verify the endpoint's current shape directly (browser devtools,
   or the real site's own network requests) rather than assuming the
   code is just buggy.
2. Update the relevant `sources/<name>.py` to match.
3. Note what changed in that module's docstring, the way the existing
   modules do — future-you (or the next contributor) will hit the same
   question again.

## Windows / Claude Desktop packaging notes

If you build a local `.mcpb` Desktop Extension for your own use (rather
than the `pip install` + manual config path in the README), two real
gotchas surfaced while building this:

- If Claude Desktop is itself installed as a Windows Store (MSIX) app,
  its `${__dirname}` extension-install-path substitution can resolve to
  a path only *it* can see (MSIX path virtualization) — a spawned
  Python process can't open that same path, and the server shows
  "offline" with a `No such file or directory` error in
  `%LOCALAPPDATA%\Claude\Logs\mcp-server-*.log`. Fix: don't rely on a
  bundled copy inside the extension — point `mcp_config.args` at a
  real, non-virtualized path (an installed package via `-m
  ropublicdata`, or a cloned repo's `server.py`).
- Point `mcp_config.command` at the *exact* Python path from `where
  python` in the shell you've tested with, not a bare `"python"` —
  Claude Desktop doesn't necessarily spawn with your full user `PATH`.

This is also the reason the README's primary install path is `pip
install` + a manual `claude_desktop_config.json` edit rather than a
prebuilt `.mcpb` shipped in the repo: a single bundled extension file
doesn't generalize well across different Python installs and Claude
Desktop packaging (Store vs. direct download), so there's no one
`.mcpb` that reliably works for everyone.
