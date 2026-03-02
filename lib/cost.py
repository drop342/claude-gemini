"""Cost tracking for Gemini API usage.

Uses daily log files (costs-YYYY-MM-DD.jsonl) so daily_spend() only reads today's file.
"""
import json
import os
from datetime import datetime
from pathlib import Path

COST_DIR = Path(os.environ.get("GEMINI_COST_DIR", os.path.expanduser("~/.cache/claude-gemini")))
DAILY_BUDGET = float(os.environ.get("GEMINI_DAILY_BUDGET", "5.00"))

# Pricing per 1M tokens (USD) as of Feb 2026
PRICING = {
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 10.00},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-flash-preview": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}


def _today_log() -> Path:
    return COST_DIR / f"costs-{datetime.now().strftime('%Y-%m-%d')}.jsonl"


def _read_today() -> list[dict]:
    """Read only today's cost log — O(today's calls) not O(all history)."""
    path = _today_log()
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = PRICING.get(model, PRICING.get("gemini-2.5-flash"))
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000


def log_usage(model: str, input_tokens: int, output_tokens: int, cost_usd: float, task: str = "") -> None:
    COST_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_usd, 6),
        "task": task,
    }
    with open(_today_log(), "a") as f:
        f.write(json.dumps(entry) + "\n")


def daily_spend() -> float:
    return sum(e.get("cost_usd", 0.0) for e in _read_today())


def check_budget() -> tuple[bool, float, float]:
    """Returns (within_budget, spent_today, daily_limit)."""
    spent = daily_spend()
    return spent < DAILY_BUDGET, spent, DAILY_BUDGET


def summary(date: str | None = None) -> dict:
    """Return cost summary. Pass date='YYYY-MM-DD' for historical, None for today."""
    if date:
        path = COST_DIR / f"costs-{date}.jsonl"
        entries = []
        if path.exists():
            for line in path.read_text().splitlines():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    else:
        entries = _read_today()

    total_cost = 0.0
    total_calls = 0
    models = {}
    for entry in entries:
        total_cost += entry.get("cost_usd", 0.0)
        total_calls += 1
        m = entry.get("model", "unknown")
        if m not in models:
            models[m] = {"calls": 0, "cost": 0.0, "tokens": 0}
        models[m]["calls"] += 1
        models[m]["cost"] += entry.get("cost_usd", 0.0)
        models[m]["tokens"] += entry.get("input_tokens", 0) + entry.get("output_tokens", 0)

    result = {
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "total_cost": round(total_cost, 4),
        "total_calls": total_calls,
        "daily_budget": DAILY_BUDGET,
        "budget_remaining": round(DAILY_BUDGET - total_cost, 4),
        "models": models,
    }
    return result
