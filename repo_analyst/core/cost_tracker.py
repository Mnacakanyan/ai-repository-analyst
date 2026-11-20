"""
Token and Cost Tracking Engine.

Tracks input tokens, output tokens, cached tokens, and calculates USD cost based
on official provider rate cards (Anthropic & OpenAI).
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from repo_analyst.models import TokenUsage, RunCost


# Pricing per 1,000,000 tokens (USD)
# Source: Anthropic & OpenAI official pricing documentation
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Anthropic
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-3-5-sonnet-latest": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-3-5-haiku-20241022": {
        "input": 0.80,
        "output": 4.00,
        "cache_write": 1.00,
        "cache_read": 0.08,
    },
    "claude-3-5-haiku-latest": {
        "input": 0.80,
        "output": 4.00,
        "cache_write": 1.00,
        "cache_read": 0.08,
    },
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00,
        "cache_write": 18.75,
        "cache_read": 1.50,
    },
    # OpenAI
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00,
        "cache_read": 1.25,
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
        "cache_read": 0.075,
    },
    "o1": {
        "input": 15.00,
        "output": 60.00,
        "cache_read": 7.50,
    },
    "o3-mini": {
        "input": 1.10,
        "output": 4.40,
        "cache_read": 0.55,
    },
    # Mock / Fallback
    "mock-evaluator": {
        "input": 0.0,
        "output": 0.0,
        "cache_read": 0.0,
    }
}


class CostTracker:
    """Tracks token consumption and calculates cumulative operational costs."""

    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cached_tokens = 0
        self.call_history = []

    def record_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RunCost:
        """Records token usage from a single API response and returns the incremental cost."""
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cached_tokens += cached_tokens

        incremental_cost = self._calculate_cost(prompt_tokens, completion_tokens, cached_tokens)
        
        self.call_history.append({
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_usd": incremental_cost.total_cost_usd,
            "metadata": metadata or {},
        })
        return incremental_cost

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> RunCost:
        rates = MODEL_PRICING.get(self.model)
        if not rates:
            # Fallback to general estimation if exact submodel key is unknown
            rates = {"input": 3.00, "output": 15.00, "cache_read": 0.30}

        prompt_rate = rates.get("input", 3.00) / 1_000_000.0
        completion_rate = rates.get("output", 15.00) / 1_000_000.0
        cache_rate = rates.get("cache_read", prompt_rate * 0.1) / 1_000_000.0

        # Cached tokens get lower rate, standard uncached prompt tokens pay standard input rate
        uncached_prompt = max(0, prompt_tokens - cached_tokens)
        prompt_cost = (uncached_prompt * prompt_rate) + (cached_tokens * cache_rate)
        completion_cost = completion_tokens * completion_rate
        total_cost = prompt_cost + completion_cost

        return RunCost(
            provider=self.provider,
            model=self.model,
            prompt_cost_usd=round(prompt_cost, 6),
            completion_cost_usd=round(completion_cost, 6),
            total_cost_usd=round(total_cost, 6),
        )

    def get_token_usage(self) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.total_prompt_tokens,
            completion_tokens=self.total_completion_tokens,
            cached_tokens=self.total_cached_tokens,
            total_tokens=self.total_prompt_tokens + self.total_completion_tokens,
        )

    def get_total_cost(self) -> RunCost:
        return self._calculate_cost(
            self.total_prompt_tokens,
            self.total_completion_tokens,
            self.total_cached_tokens,
        )
