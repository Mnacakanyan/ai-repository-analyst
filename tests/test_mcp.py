"""
Tests for Official Model Context Protocol (MCP) Server & Client Integration.
"""

import pytest
from repo_analyst.mcp_server.server import mcp_server
from repo_analyst.mcp_server.client import MCPClientAdapter


@pytest.mark.asyncio
async def test_mcp_server_tool_listing():
    tools = await mcp_server.list_tools()
    tool_names = [t.name for t in tools]
    assert "repo_get_info" in tool_names
    assert "repo_get_tree" in tool_names
    assert "repo_read_file" in tool_names
    assert "repo_analyze_manifest" in tool_names


@pytest.mark.asyncio
async def test_mcp_client_adapter_schema_conversion():
    adapter = MCPClientAdapter(server=mcp_server)
    await adapter.initialize()

    anthropic_tools = adapter.get_anthropic_tools()
    assert len(anthropic_tools) >= 4
    info_tool = next(t for t in anthropic_tools if t["name"] == "repo_get_info")
    assert "owner" in info_tool["input_schema"]["properties"]
    assert "repo" in info_tool["input_schema"]["properties"]

    openai_tools = adapter.get_openai_tools()
    assert len(openai_tools) >= 4
    assert openai_tools[0]["type"] == "function"
