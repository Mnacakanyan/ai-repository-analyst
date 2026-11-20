"""
Anthropic Claude Model Provider Implementation.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import anthropic
from repo_analyst.config import settings
from repo_analyst.providers.base import BaseLLMProvider, ProviderStepResponse, ToolCallRequest


class AnthropicProvider(BaseLLMProvider):
    """Provider integrating Anthropic Claude models (Claude 3.5 Sonnet, Claude 3.5 Haiku, etc.)."""

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        super().__init__(model_name or settings.DEFAULT_ANTHROPIC_MODEL)
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError(
                "Anthropic API key is missing. Set ANTHROPIC_API_KEY environment variable or pass api_key."
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate_step(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str,
        temperature: float = 0.1,
    ) -> ProviderStepResponse:
        """Executes a single turn with Anthropic Claude."""
        # Convert internal message format to Anthropic format if necessary
        formatted_messages = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role in ("user", "assistant"):
                formatted_messages.append({"role": role, "content": content})
            elif role == "tool":
                # Convert OpenAI/generic tool role into Anthropic user tool_result
                formatted_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.get("tool_call_id", "tool_call_0"),
                            "content": str(content),
                        }
                    ],
                })

        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            temperature=temperature,
            system=system_prompt,
            tools=tools,
            messages=formatted_messages,
        )

        thought_parts = []
        tool_calls: List[ToolCallRequest] = []

        for block in response.content:
            if block.type == "text":
                thought_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        usage = response.usage
        prompt_tokens = usage.input_tokens
        completion_tokens = usage.output_tokens
        cached_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0

        return ProviderStepResponse(
            thought="\n".join(thought_parts),
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "end_turn",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            raw_message=response,
        )

    def generate_final_report(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
    ) -> tuple[str, int, int]:
        """Synthesizes the complete markdown and structured analysis."""
        formatted_messages = []
        for m in messages:
            if m["role"] in ("user", "assistant"):
                formatted_messages.append({"role": m["role"], "content": m["content"]})
            elif m["role"] == "tool":
                formatted_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.get("tool_call_id", "tool_call_0"),
                            "content": str(m["content"]),
                        }
                    ],
                })

        # Add synthesis trigger
        formatted_messages.append({
            "role": "user",
            "content": "All tool exploration is complete. Synthesize your findings now into the final comprehensive technical report following the required structure.",
        })

        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            temperature=0.2,
            system=system_prompt,
            messages=formatted_messages,
        )

        text_content = "".join([b.text for b in response.content if b.type == "text"])
        return text_content, response.usage.input_tokens, response.usage.output_tokens
