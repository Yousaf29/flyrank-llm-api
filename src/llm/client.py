"""The LLM client — provider-agnostic, with an explicit timeout and retry policy.

The SDK's defaults (a 10-minute timeout, 2 silent retries) are wrong for an HTTP
endpoint, so we override both: our own timeout, and our own retry loop that fires
ONLY on the failures worth retrying (timeouts, 429, 5xx) with exponential backoff
plus jitter — and never on 400/401/403, where a retry just burns quota.
"""
import random
import re
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from src import config

# Provider-side errors worth retrying (5xx family; 529 = overloaded).
_RETRYABLE_STATUS = {500, 502, 503, 504, 529}
# Never retry these — the answer will be the same in four seconds.
_NEVER_RETRY_STATUS = {400, 401, 403}


class LLMTimeout(Exception):
    """The model call exceeded our timeout (mapped to 504 by the route)."""


class LLMUpstreamError(Exception):
    """A non-retryable or exhausted provider error (mapped to 502 by the route)."""


def _build_client() -> OpenAI:
    # max_retries=0: we run our OWN retry loop, so the SDK never retries silently.
    return OpenAI(
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
        timeout=config.LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )


def _retry_after_seconds(exc: APIStatusError):
    """If a 429 carries a numeric Retry-After header, obey it instead of guessing."""
    try:
        value = exc.response.headers.get("retry-after")
    except Exception:
        return None
    if value and re.fullmatch(r"\d+", value.strip()):
        return int(value.strip())
    return None


def _backoff(attempt: int, retry_after=None) -> None:
    """Wait before the next attempt: Retry-After if given, else 1s/2s/4s + jitter."""
    if retry_after is not None:
        time.sleep(retry_after)
        return
    delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
    time.sleep(delay)


def complete(messages: list[dict]) -> tuple[str, dict]:
    """Call the model with a timeout and bounded retries. Returns (text, usage).

    temperature=0: triage is classification — same input, same answer, not creativity.
    """
    client = _build_client()
    max_attempts = max(1, config.LLM_MAX_ATTEMPTS)

    for attempt in range(1, max_attempts + 1):
        try:
            res = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=messages,
                temperature=0,
            )
            text = res.choices[0].message.content or ""
            usage = {
                "input_tokens": getattr(res.usage, "prompt_tokens", None),
                "output_tokens": getattr(res.usage, "completion_tokens", None),
            }
            return text, usage

        except APITimeoutError:
            if attempt == max_attempts:
                raise LLMTimeout(f"Model did not respond within {config.LLM_TIMEOUT_SECONDS}s")
            _backoff(attempt)

        except RateLimitError as exc:  # 429 — subclass of APIStatusError, catch first
            if attempt == max_attempts:
                raise LLMUpstreamError("Rate limited (429) after retries")
            _backoff(attempt, _retry_after_seconds(exc))

        except APIConnectionError:
            if attempt == max_attempts:
                raise LLMUpstreamError("Connection error after retries")
            _backoff(attempt)

        except APIStatusError as exc:
            status = exc.status_code
            if status in _NEVER_RETRY_STATUS:
                # Bad key / bad request / forbidden — fail fast, no retry.
                raise LLMUpstreamError(f"Provider returned {status}; not retrying")
            if status in _RETRYABLE_STATUS:
                if attempt == max_attempts:
                    raise LLMUpstreamError(f"Provider returned {status} after retries")
                _backoff(attempt)
            else:
                raise LLMUpstreamError(f"Provider returned {status}")

    raise LLMUpstreamError("Retries exhausted")
