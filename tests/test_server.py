"""Smoke tests for the tinkershop MCPServer."""

from __future__ import annotations

import re

import pytest

from tinkershop.server import create_server


@pytest.mark.asyncio
async def test_server_registers_web_search_tool() -> None:
    mcp = create_server()
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert "web_search" in names


@pytest.mark.asyncio
async def test_web_search_tool_description_is_meaningful() -> None:
    mcp = create_server()
    tools = await mcp.list_tools()
    tool = next(t for t in tools if t.name == "web_search")
    assert tool.description
    assert "DuckDuckGo" in tool.description
    # inputSchema should declare the expected query parameter.
    schema_props = tool.input_schema.get("properties", {})
    assert "query" in schema_props
    assert re.search(r"\\bmax_results\\b", str(tool.input_schema)) or "max_results" in schema_props
