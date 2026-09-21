"""
Minimal MCP client — verifies the installed ropublicdata package works
end-to-end without needing Node/npx (useful if your network blocks the
npm registry, like it blocked some of the data sources during
prototyping).

This spawns `python -m ropublicdata` as a real subprocess and talks to
it over stdio using the actual MCP protocol — the same way Claude
Desktop or any other MCP client would, just without a GUI. Requires the
package to be installed first (`pip install -e .` from the repo root).

Run: python test_mcp_client.py
"""
import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "ropublicdata"])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Connected. Server exposes {len(tools.tools)} tool(s):")
            for t in tools.tools:
                print(f"  - {t.name}")
            print()

            print("Calling bnr_latest_rates()...")
            result = await session.call_tool("bnr_latest_rates", {})
            if result.is_error:
                print("Tool returned an error:")
                for block in result.content:
                    print(" ", getattr(block, "text", block))
            else:
                print("Success — real data back from BNR:")
                for block in result.content:
                    print(" ", getattr(block, "text", block))


if __name__ == "__main__":
    asyncio.run(main())
