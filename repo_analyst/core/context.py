"""
Context Management and Working Memory for the Agent Loop.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from repo_analyst.models import AgentStep, ToolCallRecord


class WorkingMemory:
    """Maintains active findings, verified files, and pruned conversation context."""

    def __init__(self, max_context_chars: int = 120_000):
        self.max_context_chars = max_context_chars
        self.steps: List[AgentStep] = []
        self.verified_files: Dict[str, str] = {}  # path -> brief summary or key excerpts
        self.manifest_data: Dict[str, Any] = {}
        self.discovered_risks: List[Dict[str, Any]] = []
        self.discovered_architecture: List[Dict[str, Any]] = []

    def add_step(self, step: AgentStep):
        self.steps.append(step)

    def register_verified_file(self, path: str, summary: str):
        self.verified_files[path] = summary

    def get_summary_state(self) -> str:
        """Returns a compact textual summary of working memory to keep prompts grounded."""
        verified_list = list(self.verified_files.keys())
        lines = [
            f"- Inspected files ({len(verified_list)}): {', '.join(verified_list[:20]) if verified_list else 'None yet'}",
            f"- Recorded architecture observations: {len(self.discovered_architecture)}",
            f"- Recorded potential risks: {len(self.discovered_risks)}",
        ]
        return "\n".join(lines)

    def prune_old_tool_outputs(self, messages: List[Dict[str, Any]], retain_latest: int = 4) -> List[Dict[str, Any]]:
        """
        Compresses older verbose tool outputs in conversation history to save tokens
        while preserving the LLM thoughts and the latest observations.
        """
        total_len = sum(len(str(m.get("content", ""))) for m in messages)
        if total_len <= self.max_context_chars:
            return messages

        # Compress older tool results
        pruned_messages = []
        tool_count = 0
        total_tool_msgs = sum(1 for m in messages if m.get("role") == "tool" or (isinstance(m.get("content"), list) and any(item.get("type") == "tool_result" for item in m.get("content") if isinstance(item, dict))))

        for m in messages:
            is_tool = m.get("role") == "tool"
            # For Anthropic, role is user with tool_result blocks
            content = m.get("content")
            if is_tool or (isinstance(content, list) and any(item.get("type") == "tool_result" for item in content if isinstance(item, dict))):
                tool_count += 1
                if tool_count <= total_tool_msgs - retain_latest:
                    # Truncate content of older tool observations
                    pruned_messages.append({
                        "role": m.get("role"),
                        "content": "[Previous tool output compressed to preserve context budget]"
                    })
                    continue
            pruned_messages.append(m)

        return pruned_messages
