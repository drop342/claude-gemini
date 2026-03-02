"""Gemini API client for Claude Code delegation.

Core design:
- Claude Code calls this via CLI (Bash tool)
- Returns structured JSON for easy parsing
- Deep thinking enabled by default (ThinkingConfig)
- Auto-routes to Flash (cheap/fast) or Pro (complex) based on task
- Tracks costs, caches responses, handles errors gracefully
"""
import json
import os
import sys
import time
from pathlib import Path

from google import genai

try:
    from . import cache, cost
except ImportError:
    from lib import cache, cost

# Model aliases for easy routing
MODELS = {
    "pro": "gemini-3.1-pro-preview",
    "flash": "gemini-2.5-flash",
    "flash-preview": "gemini-2.5-flash-preview",
    "2.5-pro": "gemini-2.5-pro",
}
DEFAULT_MODEL = "flash"

# Thinking tiers: named levels -> token budgets
# Maps the SOP's LOW/MEDIUM/HIGH/MAX to concrete budgets per model class
THINKING_TIERS = {
    "low":    {"flash": 1024,  "pro": 2048},
    "medium": {"flash": 4096,  "pro": 8192},
    "high":   {"flash": 8192,  "pro": 16384},
    "max":    {"flash": 16384, "pro": 32768},
}
DEFAULT_TIER = "high"

# Legacy direct budget mapping (still works with --thinking-budget)
THINKING_BUDGETS = {
    "pro": 16384,       # = tier "high"
    "flash": 8192,      # = tier "high"
    "flash-preview": 8192,
    "2.5-pro": 16384,
}
DEFAULT_THINKING_BUDGET = 8192

# Naked Reasoner system instruction — pure deduction mode for Gemini
NAKED_REASONER_INSTRUCTION = (
    "You are the naked reasoning engine. Focus entirely on logical deduction, "
    "structural mapping, and first-principles problem solving. Cross disciplinary "
    "boundaries if required. Do not output tool-calling boilerplate. Do not write "
    "execution code unless explicitly asked. Return the logical proof, architectural "
    "resolution, or analytical framework."
)


def _resolve_model(model: str) -> str:
    return MODELS.get(model, model)


def _resolve_thinking_budget(model: str, tier: str | None = None, budget: int | None = None) -> int:
    """Resolve thinking budget from tier name or explicit budget.

    Priority: explicit budget > tier > model default (HIGH)
    """
    if budget is not None:
        return budget
    tier = (tier or DEFAULT_TIER).lower()
    model_class = "pro" if "pro" in model else "flash"
    return THINKING_TIERS.get(tier, THINKING_TIERS["high"]).get(model_class, DEFAULT_THINKING_BUDGET)


def _auto_load_secrets() -> None:
    """Auto-load GEMINI_API_KEY from a .env file if not already in environment.
    Reads from GCOP_SECRETS_PATH env var, or ~/.secrets/.env by default."""
    if os.environ.get("GEMINI_API_KEY"):
        return
    secrets_path = Path(os.environ.get("GCOP_SECRETS_PATH", Path.home() / ".secrets" / ".env"))
    if not secrets_path.exists():
        return
    for line in secrets_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        # Handle export KEY=VALUE and KEY=VALUE
        if line.startswith("export "):
            line = line[7:]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key == "GEMINI_API_KEY" and value:
            os.environ["GEMINI_API_KEY"] = value
            return


def _get_client() -> genai.Client:
    _auto_load_secrets()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print(json.dumps({
            "error": "GEMINI_API_KEY not found. Set it in your environment or ~/.secrets/.env",
            "status": "error",
        }), file=sys.stderr)
        sys.exit(1)
    return genai.Client(api_key=api_key)


def route_model(task: str, content_size: int = 0, focus: str = "") -> str:
    """Auto-select model based on task type, content size, and focus area.

    Pro for: architecture, security, complex analysis, vision, reasoning
    Flash for: summarization, formatting, simple Q&A, bulk ops
    """
    combined = f"{task} {focus}".lower()
    pro_signals = [
        "architect", "security", "threat", "design", "review", "debug",
        "complex", "vulnerability", "reason", "proof", "diff", "vision",
        "concurrent", "crypto", "fraud", "compliance",
    ]
    if any(s in combined for s in pro_signals):
        return "pro"
    if content_size > 500_000:
        return "pro"
    return "flash"


def generate(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    system_instruction: str = "",
    files: list[str] | None = None,
    images: list[str] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 16384,
    json_mode: bool = True,
    use_cache: bool = True,
    task_label: str = "",
    think: bool = True,
    tier: str | None = None,
    thinking_budget: int | None = None,
) -> dict:
    """Generate a response from Gemini with deep thinking enabled by default.

    Args:
        prompt: The user prompt / question
        model: Model alias or full model ID
        system_instruction: System-level instruction (separate from prompt for security)
        files: List of file paths to include as context
        images: List of image file paths for vision tasks
        temperature: Sampling temperature (0.0-1.0)
        max_tokens: Max output tokens
        json_mode: Request JSON response format
        use_cache: Enable response caching
        task_label: Label for cost tracking
        think: Enable deep thinking (default: True)
        tier: Thinking tier (low/medium/high/max) — overrides default budget
        thinking_budget: Explicit token budget (overrides tier)

    Returns:
        dict with: response, model, tokens, cost, cached, latency_ms, thinking_tokens
    """
    resolved_model = _resolve_model(model)

    # Check budget
    within_budget, spent, limit = cost.check_budget()
    if not within_budget:
        return {
            "status": "error",
            "error": f"Daily budget exceeded: ${spent:.2f} / ${limit:.2f}",
            "model": resolved_model,
        }

    # Build content parts
    content_parts = []

    # Add file contents
    if files:
        for fpath in files:
            p = Path(fpath)
            if p.exists() and p.is_file():
                try:
                    text = p.read_text(errors="replace")
                    content_parts.append(f"--- File: {fpath} ---\n{text}\n--- End: {fpath} ---")
                except Exception as e:
                    content_parts.append(f"--- File: {fpath} (error: {e}) ---")

    # Add images
    image_parts = []
    if images:
        for img_path in images:
            p = Path(img_path)
            if p.exists():
                try:
                    mime = _detect_mime(p)
                    image_parts.append(genai.types.Part.from_bytes(
                        data=p.read_bytes(),
                        mime_type=mime,
                    ))
                except Exception as e:
                    content_parts.append(f"[Image load error for {img_path}: {e}]")

    # Combine prompt
    full_prompt = "\n\n".join(content_parts + [prompt]) if content_parts else prompt

    # Check cache (includes system_instruction in key for correctness)
    if use_cache and not images:
        cached_response = cache.get(resolved_model, full_prompt, files,
                                    system_instruction=system_instruction)
        if cached_response:
            cached_response["cached"] = True
            cached_response["status"] = "ok"
            return cached_response

    # Call Gemini API with retry for transient errors
    client = _get_client()
    start = time.time()
    max_retries = 3
    retry_delay = 1.0

    # Build request parts
    request_parts = []
    if image_parts:
        request_parts.extend(image_parts)
    request_parts.append(full_prompt)

    # Build thinking config (deep think by default)
    thinking_config = None
    if think:
        budget = _resolve_thinking_budget(model, tier=tier, budget=thinking_budget)
        thinking_config = genai.types.ThinkingConfig(
            thinking_budget=budget,
            include_thoughts=True,
        )

    config_kwargs = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "system_instruction": system_instruction or None,
    }
    # JSON mode and thinking are incompatible in some models —
    # if thinking is on, skip response_mime_type and parse JSON ourselves
    if json_mode and not think:
        config_kwargs["response_mime_type"] = "application/json"
    if thinking_config:
        config_kwargs["thinking_config"] = thinking_config

    kwargs = {
        "model": resolved_model,
        "contents": request_parts,
        "config": genai.types.GenerateContentConfig(**config_kwargs),
    }

    response = None
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(**kwargs)
            break
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            retryable = any(s in err_str for s in [
                "429", "resource exhausted", "too many requests",
                "503", "service unavailable", "overloaded",
                "504", "deadline exceeded", "timeout",
            ])
            if retryable and attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))
                continue
            break

    if response is None:
        latency_ms = int((time.time() - start) * 1000)
        return {
            "status": "error",
            "error": str(last_error),
            "error_type": type(last_error).__name__ if last_error else "Unknown",
            "model": resolved_model,
            "latency_ms": latency_ms,
            "retries": attempt,
        }

    try:

        latency_ms = int((time.time() - start) * 1000)

        # Extract usage
        usage = response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        thinking_tokens = getattr(usage, "thoughts_token_count", 0) or 0
        cost_usd = cost.estimate_cost(resolved_model, input_tokens, output_tokens + thinking_tokens)

        # Log cost
        cost.log_usage(resolved_model, input_tokens, output_tokens, cost_usd, task_label)

        # Extract text and thinking content
        text = response.text or ""

        # Extract thinking/reasoning from response parts if available
        thinking_text = None
        if think and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "thought") and part.thought:
                    thinking_text = part.text

        # Try to parse JSON if json_mode
        parsed = None
        if json_mode:
            # With thinking enabled, response may have markdown fences
            clean_text = text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            try:
                parsed = json.loads(clean_text)
            except json.JSONDecodeError:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = None

        result = {
            "status": "ok",
            "response": parsed if parsed is not None else text,
            "raw_text": text if parsed is not None else None,
            "model": resolved_model,
            "thinking": think,
            "thinking_tokens": thinking_tokens,
            "thinking_text": thinking_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 6),
            "latency_ms": latency_ms,
            "cached": False,
        }

        # Cache the result
        if use_cache and not images:
            cache.put(resolved_model, full_prompt, result, files,
                      system_instruction=system_instruction)

        return result

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "model": resolved_model,
            "latency_ms": latency_ms,
        }


def _detect_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")
