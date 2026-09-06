"""Configuration read from environment variables (.env).

The provider is never hard-coded: base URL, key and model all come from env, so
the same code runs against Ollama on a laptop or OpenRouter in a datacentre.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: str = "0") -> bool:
    """Read a boolean-ish env var. '1', 'true', 'yes', 'on' are all True."""
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


# Provider (the three lines that swap OpenRouter <-> Ollama <-> anything else).
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "openrouter/free")

# Behaviour toggles.
LLM_STUB = _flag("LLM_STUB", "0")            # skip model, return fixed valid answer
LLM_ENABLED = _flag("LLM_ENABLED", "true")   # kill switch (false -> deterministic fallback)

# Reliability knobs.
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_ATTEMPTS = int(os.getenv("LLM_MAX_ATTEMPTS", "3"))

PORT = int(os.getenv("PORT", "8000"))
