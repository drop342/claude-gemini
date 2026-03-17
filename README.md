# Claude-Gemini

CLI bridge for delegating heavy reasoning from Claude Code to the Gemini API. Claude is the Equipped Reasoner (tools, coordination, endurance); Gemini 3.1 Pro is the Naked Reasoner (pure deduction at ~1/7th the inference cost).

## Architecture

```
Claude (Equipped Reasoner)          Gemini 3.1 Pro (Naked Reasoner)
+---------------------------+       +---------------------------+
| Tool orchestration        |       | Pure logical deduction    |
| File system operations    | ----> | Cross-disciplinary proofs |
| Git, bash, coordination   | <---- | First-principles analysis |
| Code implementation       |       | Structural pattern detect |
| Multi-agent management    |       | Novel problem solving     |
+---------------------------+       +---------------------------+
```

## Commands

| Command | Use Case | Default Model | Default Tier |
|---------|----------|---------------|--------------|
| `reason` | Pure reasoning dispatch (Naked Reasoner) | pro | max |
| `analyze` | Code analysis, pattern detection | auto | high |
| `summarize` | Condense large files/logs | flash | high |
| `vision` | Screenshot/image analysis | pro | high |
| `generate` | Code generation from specs | auto | high |
| `ask` | Q&A with file context | auto | high |
| `diff` | Code review of changes | pro | high |
| `bulk` | Batch process multiple files | flash | high |
| `raw` | Direct API call | flash | high |
| `cost` | Today's spending report | - | - |

## Deep Thinking

All commands have deep thinking enabled by default via Gemini's `ThinkingConfig`. Four tiers control token budgets:

| Tier | Flash Budget | Pro Budget | Use Case |
|------|-------------|------------|----------|
| LOW | 1,024 | 2,048 | Simple classification, fast summarization |
| MEDIUM | 4,096 | 8,192 | Standard analytical tasks |
| HIGH | 8,192 | 16,384 | Architecture, code review (default) |
| MAX | 16,384 | 32,768 | Novel proofs, cryptography, combinatorial |

## Key Features

- **Auto-routing**: Automatically selects Pro for complex tasks (security, architecture, debugging) and Flash for simple ones (summarize, format, extract)
- **SHA256 response caching**: Identical prompts return cached results within TTL
- **Daily budget enforcement**: Configurable spending cap with automatic cutoff
- **Retry with backoff**: Handles 429/503/504 errors with exponential retry
- **Stdin piping**: `git diff | gcop diff` or `cat *.py | gcop analyze --focus security`
- **Vision support**: Multimodal image analysis (PNG, JPG, PDF)
- **Structured output**: All commands return JSON for easy parsing by calling agents

## Setup

```bash
git clone https://github.com/herakles-dev/claude-gemini.git
cd claude-gemini
pip install -r requirements.txt

# Set your API key
export GEMINI_API_KEY="your-key"

# Or point to an .env file
export GCOP_SECRETS_PATH="~/.secrets/.env"

# Make CLI executable
chmod +x bin/gemini
ln -s $(pwd)/bin/gemini /usr/local/bin/gcop
```

Requires: Python 3.11+, `google-genai` SDK

## Usage Examples

```bash
# Pure reasoning (Naked Reasoner mode)
gcop reason "Prove the logical flaw in this concurrent algorithm" --tier max
gcop reason --prompt-file problem.md --file traces.log -o solution.md

# Code analysis
gcop analyze --file main.py --focus security
cat *.log | gcop summarize --length short --tier low

# Vision
gcop vision --image screenshot.png --task ui-review

# Code review
git diff HEAD~3 | gcop diff

# Q&A with context
gcop ask --file api.py "What auth method does this use?"

# Cost tracking
gcop cost
```

## Project Structure

```
bin/
  gemini            # CLI entry point (argparse, 12 subcommands)
lib/
  client.py         # Core Gemini client (generate, route_model, ThinkingConfig)
  cache.py          # SHA256 response cache with TTL and eviction
  cost.py           # Daily JSONL cost logs + budget enforcement
  prompts/
    templates.py    # Task-specific prompt templates (system + user pairs)
config/
  models.yml        # Model specs, pricing, routing rules, budget config
```

## Tech Stack

Python, Google GenAI SDK

---

Built by [D. Michael Piscitelli](https://github.com/herakles-dev) | [herakles.dev](https://herakles.dev)
