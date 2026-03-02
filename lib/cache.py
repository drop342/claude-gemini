"""SHA256-based response cache for Gemini API calls."""
import hashlib
import json
import os
import time
from pathlib import Path

CACHE_DIR = Path(os.environ.get("GEMINI_CACHE_DIR", os.path.expanduser("~/.cache/claude-gemini")))
DEFAULT_TTL = 3600  # 1 hour
MAX_ENTRIES = 500   # Auto-evict oldest beyond this


def _cache_key(model: str, prompt: str, system_instruction: str = "",
               files: list[str] | None = None) -> str:
    content = f"{model}:{system_instruction}:{prompt}"
    if files:
        for f in sorted(files):
            try:
                content += f":{Path(f).stat().st_mtime}:{f}"
            except OSError:
                content += f":missing:{f}"
    return hashlib.sha256(content.encode()).hexdigest()


def get(model: str, prompt: str, files: list[str] | None = None,
        ttl: int = DEFAULT_TTL, system_instruction: str = "") -> dict | None:
    key = _cache_key(model, prompt, system_instruction, files)
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("timestamp", 0) > ttl:
            path.unlink(missing_ok=True)
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def put(model: str, prompt: str, response: dict, files: list[str] | None = None,
        system_instruction: str = "") -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(model, prompt, system_instruction, files)
    path = CACHE_DIR / f"{key}.json"
    response["timestamp"] = time.time()
    response["cache_key"] = key
    path.write_text(json.dumps(response, default=str))
    _evict_if_needed()


def _evict_if_needed() -> None:
    """Remove oldest entries if cache exceeds MAX_ENTRIES."""
    if not CACHE_DIR.exists():
        return
    entries = sorted(CACHE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if len(entries) <= MAX_ENTRIES:
        return
    # Also purge expired entries first
    now = time.time()
    removed = 0
    for entry in entries:
        try:
            data = json.loads(entry.read_text())
            if now - data.get("timestamp", 0) > DEFAULT_TTL:
                entry.unlink()
                removed += 1
        except (json.JSONDecodeError, OSError):
            entry.unlink(missing_ok=True)
            removed += 1
    # If still over limit, remove oldest
    if len(entries) - removed > MAX_ENTRIES:
        remaining = sorted(CACHE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
        for entry in remaining[:len(remaining) - MAX_ENTRIES]:
            entry.unlink(missing_ok=True)


def clear() -> int:
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count
