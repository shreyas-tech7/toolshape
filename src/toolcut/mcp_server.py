"""Serve one shape as an MCP server over stdio with the official MCP Python SDK.

    python -m toolcut.mcp_server --shape A --api-url http://127.0.0.1:PORT
"""

from __future__ import annotations

import argparse

import anyio
import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .shapes import SHAPES, Shape


def build_server(shape: Shape) -> Server:
    async def list_tools(ctx, params):
        return types.ListToolsResult(tools=[types.Tool(**t) for t in shape.list_tools()])

    async def call_tool(ctx, params):
        # Blocking HTTP and the sandbox run in a worker thread so the event loop stays free.
        result = await anyio.to_thread.run_sync(shape.call_tool, params.name, dict(params.arguments or {}))
        return types.CallToolResult(content=[types.TextContent(type="text", text=result.text)], isError=result.is_error)

    return Server(f"toolcut-shape-{shape.key.lower()}", on_list_tools=list_tools, on_call_tool=call_tool)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shape", required=True, choices=sorted(SHAPES))
    ap.add_argument("--api-url", required=True)
    args = ap.parse_args(argv)
    if not args.api_url.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise SystemExit("toolcut serves the local fake API only (http://127.0.0.1:PORT)")
    server = build_server(SHAPES[args.shape](args.api_url))

    async def run():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(run)


if __name__ == "__main__":
    main()
