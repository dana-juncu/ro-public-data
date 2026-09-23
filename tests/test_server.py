"""
End-to-end check that the actual installed MCP server works, not just the
underlying source functions -- spawns ropublicdata.server as a real
subprocess and talks to it over stdio using the real MCP protocol, the
same way Claude Desktop or any other MCP client would. Adapted from the
original test_mcp_client.py exploration script.
"""
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "bnr_latest_rates",
    "bnr_last_10_days",
    "bnr_year_archive",
    "anaf_company_lookup",
    "anaf_company_lookup_batch",
    "data_europa_search_romania",
    "ins_tempo_browse",
    "ins_tempo_matrix_dimensions",
    "ins_tempo_query",
    "amccrs_search_buildings",
    "clasate_search",
    "clasate_item_detail",
}


@pytest.mark.asyncio
async def test_server_exposes_all_tools():
    params = StdioServerParameters(command=sys.executable, args=["-m", "ropublicdata"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert names == EXPECTED_TOOLS
            # Every tool needs a real docstring -- that's what an MCP
            # client (and the model using it) actually sees.
            assert all(t.description for t in tools.tools)


@pytest.mark.asyncio
async def test_server_calls_a_real_tool_end_to_end():
    params = StdioServerParameters(command=sys.executable, args=["-m", "ropublicdata"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("bnr_latest_rates", {})
            assert not result.is_error
            assert result.content
