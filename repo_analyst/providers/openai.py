"""
OpenAI Provider Implementation.
"""

from __future__ import annotations
import json
from typing import List, Dict, Any, Optional
import openai
from repo_analyst.config import settings
from repo_analyst.providers.base import BaseLLMProvider, ProviderStepResponse, ToolCallRequest


class OpenAIProvider(BaseLLMProvider):
    """Provider integrating OpenAI models (GPT-4o, GPT-4o-mini, o3-mini, etc.)."""

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        super().__init__(model_name or settings.DEFAULT_OPENAI_MODEL)
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is missing. Set OPENAI_API_KEY environment variable or pass api_key."
            )
        self.client = openai.OpenAI(api_key=self.api_key)

    def generate_step(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str,
        temperature: float = 0.1,
    ) -> ProviderStepResponse:
        system_msg = [{"role": "system", "content": system_prompt}]
        full_messages = system_msg + messages

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=full_messages,
            tools=tools if tools else None,
            temperature=temperature,
        )

        choice = response.choices[0]
        message = choice.message
        thought = message.content or ""

        tool_calls: List[ToolCallRequest] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        cached_tokens = 0
        if usage and hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
            cached_tokens = getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0

        return ProviderStepResponse(
            thought=thought,
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason or "stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            raw_message=message,
        )

    def generate_final_report(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
    ) -> tuple[str, int, int]:
        system_msg = [{"role": "system", "content": system_prompt}]
        prompt_msg = {
            "role": "user",
            "content": "All tool exploration is complete. Synthesize your findings now into the final comprehensive technical report following the required structure.",
        }
        full_messages = system_msg + messages + [prompt_msg]

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=full_messages,
            temperature=0.2,
        )

        content = response.choices[0].message.content or ""
        p_tok = response.usage.prompt_tokens if response.usage else 0
        c_tok = response.usage.completion_tokens if response.usage else 0
        return content, p_tok, c_tok
