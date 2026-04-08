"""Tests for per model cost calculation and token tracker cost accumulation."""

import pytest

from qallm.llm.base import MODEL_RATES, LLMResponse, TokenTracker, calculate_cost_usd

# -- calculate_cost_usd


def test_cost_gpt4o_mini_known_rate():
    cost = calculate_cost_usd("gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.15 + 0.60)


def test_cost_gpt5_mini_known_rate():
    cost = calculate_cost_usd("gpt-5-mini", 1_000_000, 1_000_000)
    assert cost == pytest.approx(2.50 + 10.00)


def test_cost_claude_haiku_known_rate():
    cost = calculate_cost_usd("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.80 + 4.00)


def test_cost_unknown_model_is_zero():
    cost = calculate_cost_usd("ollama/llama3.1:8b", 100_000, 50_000)
    assert cost == 0.0


def test_cost_zero_tokens():
    assert calculate_cost_usd("gpt-4o-mini", 0, 0) == 0.0


def test_cost_only_input_tokens():
    cost = calculate_cost_usd("gpt-4o-mini", 1_000_000, 0)
    assert cost == pytest.approx(0.15)


def test_cost_only_output_tokens():
    cost = calculate_cost_usd("gpt-4o-mini", 0, 1_000_000)
    assert cost == pytest.approx(0.60)


# -- TokenTracker cost accumulation


def test_tracker_accumulates_cost():
    tracker = TokenTracker(budget=10_000)
    tracker.record(LLMResponse(content="x", input_tokens=1_000, output_tokens=500, model="gpt-4o-mini"))
    expected = calculate_cost_usd("gpt-4o-mini", 1_000, 500)
    assert tracker.total_cost_usd == pytest.approx(expected)


def test_tracker_cost_accumulates_across_calls():
    tracker = TokenTracker(budget=50_000)
    tracker.record(LLMResponse(content="a", input_tokens=1_000, output_tokens=500, model="gpt-4o-mini"))
    tracker.record(LLMResponse(content="b", input_tokens=2_000, output_tokens=800, model="gpt-5-mini"))
    expected = calculate_cost_usd("gpt-4o-mini", 1_000, 500) + calculate_cost_usd("gpt-5-mini", 2_000, 800)
    assert tracker.total_cost_usd == pytest.approx(expected)


def test_tracker_cost_zero_for_ollama():
    tracker = TokenTracker(budget=10_000)
    tracker.record(LLMResponse(content="x", input_tokens=5_000, output_tokens=2_000, model="ollama/llama3.1:8b"))
    assert tracker.total_cost_usd == 0.0


def test_tracker_to_dict_includes_cost():
    tracker = TokenTracker(budget=1_000)
    tracker.record(LLMResponse(content="x", input_tokens=100, output_tokens=50, model="gpt-4o-mini"))
    d = tracker.to_dict()
    assert "total_cost_usd" in d
    assert d["total_cost_usd"] >= 0.0


def test_tracker_history_includes_per_call_cost():
    tracker = TokenTracker(budget=5_000)
    tracker.record(LLMResponse(content="x", input_tokens=1_000, output_tokens=500, model="gpt-4o-mini"))
    entry = tracker.history[0]
    assert "cost_usd" in entry
    assert entry["cost_usd"] == pytest.approx(calculate_cost_usd("gpt-4o-mini", 1_000, 500))


# -- MODEL_RATES table


def test_model_rates_has_required_models():
    assert "gpt-4o-mini" in MODEL_RATES
    assert "gpt-5-mini" in MODEL_RATES
    assert "claude-haiku-4-5-20251001" in MODEL_RATES


def test_model_rates_values_are_positive():
    for model, rates in MODEL_RATES.items():
        assert rates["input"] > 0, f"{model} input rate should be > 0"
        assert rates["output"] > 0, f"{model} output rate should be > 0"


def test_output_rate_exceeds_input_rate():
    """Output tokens are consistently more expensive than input tokens."""
    for model, rates in MODEL_RATES.items():
        assert rates["output"] > rates["input"], f"{model}: output should cost more than input"


# -- /api/llm/rates endpoint


def test_rates_endpoint_returns_200(client):
    r = client.get("/api/llm/rates")
    assert r.status_code == 200


def test_rates_endpoint_structure(client):
    data = client.get("/api/llm/rates").json()
    assert "unit" in data
    assert "rates" in data
    assert "note" in data


def test_rates_endpoint_contains_known_models(client):
    rates = client.get("/api/llm/rates").json()["rates"]
    assert "gpt-4o-mini" in rates
    assert "gpt-5-mini" in rates
    assert "claude-haiku-4-5-20251001" in rates


def test_rates_endpoint_model_has_input_output_fields(client):
    rates = client.get("/api/llm/rates").json()["rates"]
    for model, pricing in rates.items():
        assert "input_per_1m_usd" in pricing, f"{model} missing input_per_1m_usd"
        assert "output_per_1m_usd" in pricing, f"{model} missing output_per_1m_usd"
