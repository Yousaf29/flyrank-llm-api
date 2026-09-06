"""Structured logging: a cost line per call, and a quarantine line per failure.

Both are written as one JSON object per line (JSON Lines) so they are greppable
and machine-readable. Quarantine keeps a failed answer aside — with the input,
the error and the prompt version — instead of crashing or reaching a database.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_QUARANTINE = _LOG_DIR / "quarantine.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_cost(
    *,
    prompt_version: str,
    model: str,
    input_tokens,
    output_tokens,
    duration_ms: int,
    repairs: int,
) -> None:
    """One structured cost line per request, to stdout (Twelve-Factor: logs are streams)."""
    line = {
        "ts": _now(),
        "event": "llm_call",
        "prompt_version": prompt_version,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
        "repairs": repairs,
    }
    print(json.dumps(line), file=sys.stdout, flush=True)


def quarantine(*, input_text: str, raw: str, error: str, prompt_version: str) -> None:
    """Append a failed model answer to logs/quarantine.jsonl for later inspection."""
    _LOG_DIR.mkdir(exist_ok=True)
    line = {
        "ts": _now(),
        "prompt_version": prompt_version,
        "input": input_text,
        "raw_output": raw,
        "error": error,
    }
    with _QUARANTINE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")
