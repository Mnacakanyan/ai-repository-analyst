"""
Official Model Context Protocol (MCP) Server for Repository Analysis.

Exposes GitHub repository analysis tools over stdio/JSON-RPC following
the official Model Context Protocol specification. Compatible with
Claude Desktop, Claude Code, Cursor, and custom MCP clients.
"""

from __future__ import annotations
import asyncio
import sys
import json
from typing import Optional

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

from repo_analyst.tools.github import GitHubClient
from repo_analyst.tools.manifests import ManifestParser

# Initialize MCP Server
mcp_server = MCPServer(
    name="ai-repo-analyst",
    instructions="MCP Server providing GitHub repository exploration, file reading, and dependency analysis tools.",
)

# Shared GitHub API Client
_github_client = GitHubClient()


@mcp_server.tool()
def repo_get_info(owner: str, repo: str) -> str:
    """Fetch metadata for a GitHub repository (stars, description, branch, language)."""
    meta = _github_client.get_repository_info(owner, repo)
    return meta.model_dump_json(indent=2)


@mcp_server.tool()
def repo_get_tree(owner: str, repo: str, branch: Optional[str] = None, recursive: bool = True) -> str:
    """List directory and file tree of a GitHub repository."""
    tree = _github_client.get_repository_tree(owner, repo, branch=branch, recursive=recursive)
    return json.dumps([item.model_dump() for item in tree], indent=2)


@mcp_server.tool()
def repo_read_file(
    owner: str,
    repo: str,
    path: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
) -> str:
    """Read contents of a file in the repository with optional line range."""
    # Convert 0 to None if passed as 0
    end = None if (end_line is None or end_line <= 0) else end_line
    content = _github_client.read_file(owner, repo, path, start_line=start_line, end_line=end)
    return content.model_dump_json(indent=2)


@mcp_server.tool()
def repo_search_code(owner: str, repo: str, query: str) -> str:
    """Search code across the repository for keywords or class names."""
    results = _github_client.search_code(owner, repo, query)
    return json.dumps(results, indent=2)


@mcp_server.tool()
def repo_analyze_manifest(owner: str, repo: str, manifest_path: str) -> str:
    """Parse a dependency manifest (requirements.txt, package.json, build.gradle, Podfile, etc.)."""
    content = _github_client.read_file(owner, repo, manifest_path)
    parsed = ManifestParser.parse_manifest(manifest_path, content.content)
    if parsed:
        return parsed.model_dump_json(indent=2)
    return json.dumps({"error": f"Unsupported or unparseable manifest at {manifest_path}"})


def run_mcp_server():
    """Runs the MCP server over stdio for external MCP clients."""
    if hasattr(mcp_server, "run"):
        mcp_server.run()
    else:
        asyncio.run(mcp_server.run_stdio_async())


if __name__ == "__main__":
    run_mcp_server()
