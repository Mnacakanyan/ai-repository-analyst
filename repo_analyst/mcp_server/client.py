"""
MCP Client Integration.

Discovers tools from the MCP server, translates schemas for LLM tool calling,
and executes tool calls through the MCP protocol interface.
"""

from __future__ import annotations
import asyncio
import time
from typing import List, Dict, Any, Optional
from repo_analyst.mcp_server.server import mcp_server
from repo_analyst.models import ToolCallRecord


class MCPClientAdapter:
    """
    Adapter interfacing the agent with the MCP server.

    Performs dynamic tool discovery and execution via the official MCP server interface.
    """

    def __init__(self, server=mcp_server):
        self.server = server
        self._cached_tools: Optional[List[Any]] = None

    async def initialize(self):
        """Discovers tools available on the MCP Server."""
        self._cached_tools = await self.server.list_tools()

    def get_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Converts discovered MCP tools to Anthropic tool definitions."""
        if self._cached_tools is None:
            asyncio.run(self.initialize())

        anthropic_tools = []
        for t in self._cached_tools:
            anthropic_tools.append({
                "name": t.name,
                "description": t.description or f"MCP Tool: {t.name}",
                "input_schema": t.input_schema or {"type": "object", "properties": {}},
            })
        return anthropic_tools

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Converts discovered MCP tools to OpenAI tool definitions."""
        anth_tools = self.get_anthropic_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in anth_tools
        ]

    async def execute_tool_async(self, name: str, arguments: Dict[str, Any]) -> tuple[str, ToolCallRecord]:
        """Asynchronously calls an MCP tool on the server."""
        start_time = time.time()
        is_error = False
        try:
            call_result = await self.server.call_tool(name, arguments)
            # In MCP 2.x, call_result.content is a list of TextContent or ImageContent
            texts = []
            if hasattr(call_result, "content") and call_result.content:
                for c in call_result.content:
                    if hasattr(c, "text"):
                        texts.append(c.text)
                    else:
                        texts.append(str(c))
                output_str = "\n".join(texts)
            elif hasattr(call_result, "structured_content") and call_result.structured_content:
                output_str = str(call_result.structured_content)
            else:
                output_str = str(call_result)
        except Exception as e:
            output_str = f"MCP Execution Error ({name}): {type(e).__name__} - {str(e)}"
            is_error = True

        duration_ms = (time.time() - start_time) * 1000.0
        record = ToolCallRecord(
            tool_name=name,
            arguments=arguments,
            output_preview=(output_str[:250] + "...") if len(output_str) > 250 else output_str,
            duration_ms=round(duration_ms, 2),
            is_error=is_error,
        )
        return output_str, record

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> tuple[str, ToolCallRecord]:
        """Synchronous wrapper for agent execution loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Running in an active loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return executor.submit(asyncio.run, self.execute_tool_async(name, arguments)).result()
            else:
                return loop.run_until_complete(self.execute_tool_async(name, arguments))
        except RuntimeError:
            return asyncio.run(self.execute_tool_async(name, arguments))
