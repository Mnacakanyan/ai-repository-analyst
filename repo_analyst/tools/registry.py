"""
Tool Registry and Schema Declarations for Agent Tool Calling.
"""

from __future__ import annotations
import time
import json
from typing import List, Dict, Any, Callable
from repo_analyst.tools.github import GitHubClient
from repo_analyst.tools.manifests import ManifestParser
from repo_analyst.models import ToolCallRecord


class ToolRegistry:
    """Manages available tools, function definitions, and execution."""

    def __init__(self, github_client: GitHubClient):
        self.github = github_client
        self._tools: Dict[str, Callable] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        self._tools["get_repository_info"] = self._tool_get_repository_info
        self._tools["get_repository_tree"] = self._tool_get_repository_tree
        self._tools["read_file"] = self._tool_read_file
        self._tools["search_code"] = self._tool_search_code
        self._tools["analyze_dependencies"] = self._tool_analyze_dependencies

    def get_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Returns tool declarations formatted for Anthropic Claude API."""
        return [
            {
                "name": "get_repository_info",
                "description": "Fetches general repository information: stars, default branch, primary language, license, open issues, and description.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "GitHub repository owner (user or org)"},
                        "repo": {"type": "string", "description": "Repository name"},
                    },
                    "required": ["owner", "repo"],
                },
            },
            {
                "name": "get_repository_tree",
                "description": "Lists the directory and file tree of the repository to inspect folder structure and locate key source files.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "GitHub repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                        "branch": {"type": "string", "description": "Branch name (optional, defaults to default branch)"},
                        "recursive": {"type": "boolean", "description": "Whether to list recursively (default: true)"},
                    },
                    "required": ["owner", "repo"],
                },
            },
            {
                "name": "read_file",
                "description": "Reads the text content of a file from the repository, optionally limited to specific line numbers.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "GitHub repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                        "path": {"type": "string", "description": "Relative file path inside the repository"},
                        "start_line": {"type": "integer", "description": "Starting line number (1-indexed)"},
                        "end_line": {"type": "integer", "description": "Ending line number (inclusive)"},
                    },
                    "required": ["owner", "repo", "path"],
                },
            },
            {
                "name": "search_code",
                "description": "Searches for a keyword or pattern across code files in the repository.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "GitHub repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                        "query": {"type": "string", "description": "Search term or class/function name"},
                    },
                    "required": ["owner", "repo", "query"],
                },
            },
            {
                "name": "analyze_dependencies",
                "description": "Reads and parses project dependency manifests (requirements.txt, package.json, build.gradle, Podfile, pyproject.toml, etc.) to extract libraries and frameworks.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "GitHub repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                        "manifest_path": {"type": "string", "description": "Path to the manifest file"},
                    },
                    "required": ["owner", "repo", "manifest_path"],
                },
            },
        ]

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Returns tool declarations formatted for OpenAI function calling."""
        anthropic_defs = self.get_anthropic_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in anthropic_defs
        ]

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> tuple[str, ToolCallRecord]:
        """
        Executes the named tool and records duration, status, and output preview.
        Returns (result_string, ToolCallRecord).
        """
        start_time = time.time()
        func = self._tools.get(name)

        if not func:
            duration_ms = (time.time() - start_time) * 1000.0
            error_msg = f"Error: Tool '{name}' is not recognized. Available tools: {list(self._tools.keys())}"
            record = ToolCallRecord(
                tool_name=name,
                arguments=arguments,
                output_preview=error_msg[:200],
                duration_ms=round(duration_ms, 2),
                is_error=True,
            )
            return error_msg, record

        try:
            result = func(**arguments)
            if not isinstance(result, str):
                result_str = json.dumps(result, indent=2, default=str)
            else:
                result_str = result
            is_error = False
        except Exception as e:
            result_str = f"Tool Execution Error ({name}): {type(e).__name__} - {str(e)}"
            is_error = True

        duration_ms = (time.time() - start_time) * 1000.0
        record = ToolCallRecord(
            tool_name=name,
            arguments=arguments,
            output_preview=(result_str[:250] + "...") if len(result_str) > 250 else result_str,
            duration_ms=round(duration_ms, 2),
            is_error=is_error,
        )
        return result_str, record

    # Individual tool wrappers
    def _tool_get_repository_info(self, owner: str, repo: str) -> Dict[str, Any]:
        meta = self.github.get_repository_info(owner, repo)
        return meta.model_dump()

    def _tool_get_repository_tree(
        self, owner: str, repo: str, branch: Optional[str] = None, recursive: bool = True
    ) -> List[Dict[str, Any]]:
        tree = self.github.get_repository_tree(owner, repo, branch=branch, recursive=recursive)
        return [entry.model_dump() for entry in tree]

    def _tool_read_file(
        self,
        owner: str,
        repo: str,
        path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
    ) -> Dict[str, Any]:
        content = self.github.read_file(owner, repo, path, start_line=start_line, end_line=end_line)
        return content.model_dump()

    def _tool_search_code(self, owner: str, repo: str, query: str) -> List[Dict[str, Any]]:
        return self.github.search_code(owner, repo, query)

    def _tool_analyze_dependencies(self, owner: str, repo: str, manifest_path: str) -> Dict[str, Any]:
        file_content = self.github.read_file(owner, repo, manifest_path)
        parsed = ManifestParser.parse_manifest(manifest_path, file_content.content)
        if not parsed:
            return {
                "manifest_path": manifest_path,
                "status": "unsupported_format",
                "raw_preview": file_content.content[:500],
            }
        return parsed.model_dump()
