"""The LLM client — a thin wrapper over the OpenAI-compatible SDK.

Stage 2: build the client from env and make one low-temperature call.
(The real timeout, retry policy and cost logging arrive in Stage 4.)
"""
from openai import OpenAI

from src import config


def _client() -> OpenAI:
    return OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)


def complete(messages: list[dict]) -> tuple[str, dict]:
    """Send messages to the model, return (text, usage).

    temperature=0 because triage is classification: we want the same answer for
    the same input, not creativity.
    """
    res = _client().chat.completions.create(
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
