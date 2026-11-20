"""
Mock / Offline Deterministic Provider for Testing and Offline Evaluation.
"""

from __future__ import annotations
from typing import List, Dict, Any
from repo_analyst.providers.base import BaseLLMProvider, ProviderStepResponse, ToolCallRequest


class MockLLMProvider(BaseLLMProvider):
    """Deterministic offline provider simulating agent ReAct turns for testing."""

    def __init__(self, model_name: str = "mock-evaluator"):
        super().__init__(model_name)
        self.step_counter = 0

    def generate_step(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str,
        temperature: float = 0.1,
    ) -> ProviderStepResponse:
        self.step_counter += 1

        # Turn 1: Inspect repository metadata
        if self.step_counter == 1:
            return ProviderStepResponse(
                thought="I need to inspect the repository metadata first to verify existence and default branch.",
                tool_calls=[
                    ToolCallRequest(
                        id="call_1",
                        name="get_repository_info",
                        arguments={"owner": "test_owner", "repo": "test_repo"},
                    )
                ],
                stop_reason="tool_use",
                prompt_tokens=450,
                completion_tokens=60,
                cached_tokens=0,
            )

        # Turn 2: Retrieve tree structure
        elif self.step_counter == 2:
            return ProviderStepResponse(
                thought="Metadata retrieved. Now listing repository tree to find manifests and entrypoints.",
                tool_calls=[
                    ToolCallRequest(
                        id="call_2",
                        name="get_repository_tree",
                        arguments={"owner": "test_owner", "repo": "test_repo", "recursive": True},
                    )
                ],
                stop_reason="tool_use",
                prompt_tokens=620,
                completion_tokens=55,
                cached_tokens=0,
            )

        # Turn 3: Inspect key source file
        elif self.step_counter == 3:
            return ProviderStepResponse(
                thought="Tree retrieved. Inspecting primary entrypoint file to verify architecture and conventions.",
                tool_calls=[
                    ToolCallRequest(
                        id="call_3",
                        name="read_file",
                        arguments={"owner": "owner", "repo": "repo", "path": "index.html", "start_line": 1, "end_line": 30},
                    )
                ],
                stop_reason="tool_use",
                prompt_tokens=780,
                completion_tokens=50,
                cached_tokens=0,
            )

        # Turn 4: Completion - no more tools needed
        else:
            return ProviderStepResponse(
                thought="I have gathered sufficient evidence to conclude analysis. No further tools needed.",
                tool_calls=[],
                stop_reason="end_turn",
                prompt_tokens=890,
                completion_tokens=40,
                cached_tokens=0,
            )

    def generate_final_report(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
    ) -> tuple[str, int, int]:
        report_json = {
            "executive_summary": "This repository exhibits a modular client-server architecture with high cohesion and modern dependency management.",
            "technology_stack": ["Python 3.12+", "FastAPI", "Pydantic", "Model Context Protocol (MCP)"],
            "architectural_style": "Layered ReAct Architecture",
            "architecture_findings": [
                {
                    "component": "Agent Core",
                    "pattern_observed": "ReAct Controller",
                    "description": "Orchestrates bounded turns and tool invocations with dynamic reflection.",
                    "evidence_files": ["repo_analyst/core/agent.py"],
                    "is_verified": True
                },
                {
                    "component": "MCP Adapter",
                    "pattern_observed": "Adapter / Gateway",
                    "description": "Standardizes tool exposure and discovery through Model Context Protocol.",
                    "evidence_files": ["repo_analyst/mcp_server/client.py"],
                    "is_verified": True
                }
            ],
            "technical_risks": [
                {
                    "severity": "medium",
                    "category": "API Limits",
                    "title": "Unauthenticated GitHub Rate Limits",
                    "details": "GitHub API allows 60 req/hr for unauthenticated calls.",
                    "affected_path": "repo_analyst/tools/github.py",
                    "mitigation": "Configure GITHUB_TOKEN environment variable."
                }
            ],
            "code_quality": [
                {
                    "category": "Typing",
                    "status": "positive",
                    "observation": "Comprehensive type annotations and Pydantic validation throughout.",
                    "file_reference": "repo_analyst/models.py"
                }
            ],
            "recommendations": [
                "Establish automated multi-model evaluation benchmarks in CI.",
                "Implement token budget telemetry with alert thresholds."
            ]
        }
        import json
        return json.dumps(report_json, indent=2), 1200, 350
