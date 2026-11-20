"""
Autonomous Agent Orchestrator for Repository Analysis.

Implements the ReAct (Reasoning + Acting) loop with bounded turns, context pruning,
token & cost tracking, dynamic tool invocation, and structured report synthesis.
"""

from __future__ import annotations
import json
import logging
import re
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timezone

from repo_analyst.config import settings
from repo_analyst.models import (
    RepoMetadata,
    AnalysisReport,
    AgentStep,
    ToolCallRecord,
    ArchitectureFinding,
    TechnicalRisk,
    CodeQualityObservation,
    DependencyManifest,
)
from repo_analyst.core.cost_tracker import CostTracker
from repo_analyst.core.context import WorkingMemory
from repo_analyst.tools.github import GitHubClient
from repo_analyst.tools.registry import ToolRegistry
from repo_analyst.mcp_server.client import MCPClientAdapter
from repo_analyst.providers.base import BaseLLMProvider
from repo_analyst.providers.anthropic import AnthropicProvider
from repo_analyst.providers.openai import OpenAIProvider
from repo_analyst.providers.mock import MockLLMProvider

logger = logging.getLogger("repo_analyst.agent")


SYSTEM_PROMPT = """You are a Senior Principal Software Architect and AI Engineer conducting an autonomous, deep technical evaluation of a GitHub repository.

Your objective:
Investigate the repository thoroughly using your available inspection tools and synthesize a production-grade Technical Architecture & Quality Report.

Guidelines for autonomous tool use:
1. Do not guess repository structure or file content. Always verify by calling tools.
2. Step 1: Check repository metadata (`repo_get_info` or `get_repository_info`) to learn default branch, primary language, and description.
3. Step 2: Retrieve the repository tree (`repo_get_tree` or `get_repository_tree`) to inspect module organization and find entrypoints.
4. Step 3: Analyze dependency manifests (`repo_analyze_manifest` or `analyze_dependencies`) to identify libraries, frameworks, and engine dependencies.
5. Step 4: Select 2 to 5 high-impact source files (entry points, architecture coordinators, core abstractions, config files) and read key sections with `repo_read_file` or `read_file`.
6. Distinguish verified facts (supported by exact file paths and evidence) from hypotheses.
7. Identify architectural patterns, module relationships, technical risks (security, scale, concurrency, error handling), and code quality observations.
8. When you have sufficient evidence, stop issuing tool calls to conclude the investigation.
"""


TOOL_ALIASES: Dict[str, str] = {
    "get_repository_info": "repo_get_info",
    "get_repository_tree": "repo_get_tree",
    "read_file": "repo_read_file",
    "search_code": "repo_search_code",
    "analyze_dependencies": "repo_analyze_manifest",
    "repo_get_info": "get_repository_info",
    "repo_get_tree": "get_repository_tree",
    "repo_read_file": "read_file",
    "repo_search_code": "search_code",
    "repo_analyze_manifest": "analyze_dependencies",
}


class RepositoryAnalystAgent:
    """Autonomous agent orchestrating repository exploration and technical analysis."""

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        use_mcp: bool = True,
        max_turns: Optional[int] = None,
        max_budget_usd: Optional[float] = None,
        on_step_callback: Optional[Callable[[AgentStep], None]] = None,
    ):
        self.github_client = GitHubClient()
        self.use_mcp = use_mcp
        self.max_turns = max_turns or settings.MAX_TURNS
        self.max_budget_usd = max_budget_usd or settings.MAX_TOTAL_COST_USD
        self.on_step_callback = on_step_callback

        # Set up tool execution adapter
        if self.use_mcp:
            self.mcp_client = MCPClientAdapter()
            self.tool_executor = self.mcp_client.execute_tool
        else:
            self.tool_registry = ToolRegistry(self.github_client)
            self.tool_executor = self.tool_registry.execute_tool

        # Set up LLM provider
        self.provider = provider or self._resolve_default_provider()
        self.cost_tracker = CostTracker(
            provider=self.provider.__class__.__name__,
            model=self.provider.model_name,
        )
        self.memory = WorkingMemory()

    def _resolve_default_provider(self) -> BaseLLMProvider:
        """Resolves the default provider from configuration."""
        if settings.ANTHROPIC_API_KEY:
            return AnthropicProvider(model_name=settings.DEFAULT_ANTHROPIC_MODEL)
        elif settings.OPENAI_API_KEY:
            return OpenAIProvider(model_name=settings.DEFAULT_OPENAI_MODEL)
        else:
            logger.warning("No API keys found in environment. Falling back to MockLLMProvider for offline execution.")
            return MockLLMProvider()

    def _get_provider_tools(self) -> List[Dict[str, Any]]:
        """Retrieves tool schemas formatted for the active provider."""
        is_openai = isinstance(self.provider, OpenAIProvider)
        if self.use_mcp:
            return self.mcp_client.get_openai_tools() if is_openai else self.mcp_client.get_anthropic_tools()
        else:
            return self.tool_registry.get_openai_tools() if is_openai else self.tool_registry.get_anthropic_tools()

    def analyze(self, repo_url: str) -> AnalysisReport:
        """
        Runs the autonomous ReAct investigation loop against the repository URL
        and returns a complete AnalysisReport.
        """
        owner, repo = self.github_client.parse_repo_url(repo_url)

        # Initial baseline metadata fetch (guarantees repository exists before LLM turns)
        initial_meta = self.github_client.get_repository_info(owner, repo)

        initial_user_prompt = (
            f"Analyze the public GitHub repository '{owner}/{repo}'.\n"
            f"Repository URL: {initial_meta.html_url}\n"
            f"Description: {initial_meta.description or 'No description'}\n"
            f"Primary Language: {initial_meta.primary_language or 'Unknown'}\n"
            f"Default Branch: {initial_meta.default_branch}\n\n"
            f"Please conduct an autonomous technical investigation. Inspect tree structure, analyze dependencies, "
            f"read key source files, evaluate architecture, identify risks, and prepare a structured report."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": initial_user_prompt}
        ]

        tools = self._get_provider_tools()
        step_number = 0

        # Autonomous ReAct Loop
        while step_number < self.max_turns:
            step_number += 1

            # Check budget limit
            total_cost = self.cost_tracker.get_total_cost()
            if total_cost.total_cost_usd >= self.max_budget_usd:
                logger.warning(f"Reached budget cap (${self.max_budget_usd:.2f}). Ending exploration turns.")
                break

            # Prune older messages if token context is expanding
            pruned_messages = self.memory.prune_old_tool_outputs(messages)

            # Generate reasoning step and potential tool calls
            step_resp = self.provider.generate_step(
                messages=pruned_messages,
                tools=tools,
                system_prompt=SYSTEM_PROMPT,
            )

            # Record token usage & cost
            self.cost_tracker.record_usage(
                prompt_tokens=step_resp.prompt_tokens,
                completion_tokens=step_resp.completion_tokens,
                cached_tokens=step_resp.cached_tokens,
                metadata={"step": step_number, "thought": step_resp.thought[:100]},
            )

            current_step = AgentStep(
                step_number=step_number,
                thought=step_resp.thought or "(No verbal thought emitted)",
                tool_calls=[],
            )

            # If no tool calls were requested, the agent is satisfied
            if not step_resp.tool_calls:
                self.memory.add_step(current_step)
                if self.on_step_callback:
                    self.on_step_callback(current_step)
                logger.info(f"Agent concluded tool exploration at step {step_number}.")
                break

            # Append assistant message with thought and tool calls
            messages.append({
                "role": "assistant",
                "content": step_resp.thought or "Calling inspection tools...",
            })

            # Execute tool calls
            for tc in step_resp.tool_calls:
                tool_name = tc.name
                tool_args = tc.arguments or {}

                # Map tool aliases between MCP ("repo_...") and direct registry names
                available_tools = [t["name"] if "name" in t else t.get("function", {}).get("name") for t in tools]
                if tool_name not in available_tools:
                    alias = TOOL_ALIASES.get(tool_name)
                    if alias and alias in available_tools:
                        tool_name = alias
                    elif f"repo_{tool_name}" in available_tools:
                        tool_name = f"repo_{tool_name}"
                    elif tool_name.startswith("repo_") and tool_name[5:] in available_tools:
                        tool_name = tool_name[5:]

                # Guarantee owner and repo match target repo
                if "owner" not in tool_args or tool_args["owner"] in ("owner", "test_owner", "{owner}"):
                    tool_args["owner"] = owner
                if "repo" not in tool_args or tool_args["repo"] in ("repo", "test_repo", "{repo}"):
                    tool_args["repo"] = repo

                # Tool dispatch
                output_str, record = self.tool_executor(tool_name, tool_args)
                current_step.tool_calls.append(record)

                # Track inspected files in working memory
                if "read_file" in tool_name and "path" in tool_args:
                    self.memory.register_verified_file(tool_args["path"], output_str[:300])

                # Feed tool result back into conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": output_str,
                })

            self.memory.add_step(current_step)
            if self.on_step_callback:
                self.on_step_callback(current_step)

        # Synthesis Phase: produce comprehensive report
        report = self._synthesize_report(
            owner=owner,
            repo=repo,
            initial_meta=initial_meta,
            messages=messages,
            steps_executed=step_number,
        )
        return report

    def _synthesize_report(
        self,
        owner: str,
        repo: str,
        initial_meta: RepoMetadata,
        messages: List[Dict[str, Any]],
        steps_executed: int,
    ) -> AnalysisReport:
        """Synthesizes final structured report via LLM and builds AnalysisReport object."""
        synthesis_prompt = (
            f"You have completed your autonomous investigation of {owner}/{repo}.\n"
            f"Now output a detailed JSON analysis matching this schema:\n"
            f"{{\n"
            f'  "executive_summary": "...",\n'
            f'  "technology_stack": ["list", "of", "technologies"],\n'
            f'  "architectural_style": "e.g. Clean Architecture / Microservices / Layered / Event-driven",\n'
            f'  "architecture_findings": [\n'
            f'    {{"component": "...", "pattern_observed": "...", "description": "...", "evidence_files": ["path/to/file"], "is_verified": true}}\n'
            f"  ],\n"
            f'  "technical_risks": [\n'
            f'    {{"severity": "low|medium|high|critical", "category": "...", "title": "...", "details": "...", "affected_path": "...", "mitigation": "..."}}\n'
            f"  ],\n"
            f'  "code_quality": [\n'
            f'    {{"category": "...", "status": "positive|neutral|concern", "observation": "...", "file_reference": "..."}}\n'
            f"  ],\n"
            f'  "recommendations": ["specific actionable engineering recommendation", "..."]\n'
            f"}}\n"
            f"Return ONLY the valid JSON block without markdown fences."
        )

        synthesis_messages = messages + [{"role": "user", "content": synthesis_prompt}]
        raw_text, p_tok, c_tok = self.provider.generate_final_report(
            messages=synthesis_messages,
            system_prompt=SYSTEM_PROMPT,
        )

        self.cost_tracker.record_usage(
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            metadata={"stage": "report_synthesis"},
        )

        # Parse synthesized JSON or build graceful fallback
        parsed_data = self._extract_json(raw_text)

        # Build list of parsed manifests from memory
        manifests: List[DependencyManifest] = []
        for step in self.memory.steps:
            for tc in step.tool_calls:
                if "manifest" in tc.tool_name or "dependencies" in tc.tool_name:
                    try:
                        data = json.loads(tc.output_preview)
                        if "manifest_type" in data:
                            manifests.append(DependencyManifest(**data))
                    except Exception:
                        pass

        # Build structured Pydantic report
        return AnalysisReport(
            repository=initial_meta,
            agent_model=self.provider.model_name,
            executive_summary=parsed_data.get("executive_summary", raw_text[:500]),
            technology_stack=parsed_data.get("technology_stack", [initial_meta.primary_language] if initial_meta.primary_language else []),
            architectural_style=parsed_data.get("architectural_style", "Modular Architecture"),
            architecture_findings=[
                ArchitectureFinding(**f) for f in parsed_data.get("architecture_findings", [])
            ],
            dependencies=manifests,
            technical_risks=[
                TechnicalRisk(**r) for r in parsed_data.get("technical_risks", [])
            ],
            code_quality=[
                CodeQualityObservation(**q) for q in parsed_data.get("code_quality", [])
            ],
            recommendations=parsed_data.get("recommendations") or [
                "Establish automated CI pipeline with test coverage enforcement.",
                "Implement dependency vulnerability monitoring.",
            ],
            tokens=self.cost_tracker.get_token_usage(),
            cost=self.cost_tracker.get_total_cost(),
            steps_executed=steps_executed,
            verified_files_count=len(self.memory.verified_files),
        )

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extracts JSON object from text, handling markdown fences and whitespace."""
        cleaned = text.strip()
        # Remove ```json ... ```
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1)
        else:
            json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(1)

        try:
            return json.loads(cleaned)
        except Exception:
            # Fallback structure if LLM returned freeform text
            return {
                "executive_summary": text[:600],
                "technology_stack": [],
                "architectural_style": "Identified in summary",
                "architecture_findings": [],
                "technical_risks": [],
                "code_quality": [],
                "recommendations": [],
            }
