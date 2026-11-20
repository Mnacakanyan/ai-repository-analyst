"""
Tests for Token and Cost Accounting Engine.
"""

from repo_analyst.core.cost_tracker import CostTracker


def test_cost_tracker_anthropic_sonnet():
    tracker = CostTracker(provider="Anthropic", model="claude-3-5-sonnet-20241022")
    # 1,000,000 prompt tokens = $3.00, 100,000 completion = $1.50
    cost = tracker.record_usage(prompt_tokens=1_000_000, completion_tokens=100_000)

    assert cost.prompt_cost_usd == 3.00
    assert cost.completion_cost_usd == 1.50
    assert cost.total_cost_usd == 4.50

    usage = tracker.get_token_usage()
    assert usage.prompt_tokens == 1_000_000
    assert usage.completion_tokens == 100_000
    assert usage.total_tokens == 1_100_000


def test_cost_tracker_prompt_caching():
    tracker = CostTracker(provider="Anthropic", model="claude-3-5-sonnet-20241022")
    # 1,000,000 prompt tokens, of which 800,000 are cached ($0.30/M) and 200,000 uncached ($3.00/M)
    # uncached: 200k * $3/M = $0.60
    # cached: 800k * $0.30/M = $0.24
    # completion: 0
    # total prompt: $0.84
    cost = tracker.record_usage(prompt_tokens=1_000_000, completion_tokens=0, cached_tokens=800_000)
    assert abs(cost.prompt_cost_usd - 0.84) < 1e-4


def test_cost_tracker_openai_gpt4o():
    tracker = CostTracker(provider="OpenAI", model="gpt-4o")
    # 1,000,000 prompt = $2.50, 100,000 completion = $1.00
    cost = tracker.record_usage(prompt_tokens=1_000_000, completion_tokens=100_000)
    assert cost.prompt_cost_usd == 2.50
    assert cost.completion_cost_usd == 1.00
    assert cost.total_cost_usd == 3.50
