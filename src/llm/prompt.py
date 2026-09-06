"""Load the versioned prompt file and build the message list.

The prompt is code: it lives in prompts/<job>-v<n>.md, gets a version number, and
is diffable in review — never a string buried in a route handler.

The user's message is sent as a SEPARATE user message, JSON-encoded. Two reasons:
the model weights the system and user roles differently, and JSON-encoding keeps
untrusted content inside its own quotes so it cannot break out and hijack the
instructions (a cheap prompt-injection defence).
"""
import json
from pathlib import Path

PROMPT_VERSION = "triage-v1"

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / f"{PROMPT_VERSION}.md"


def load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_messages(user_text: str) -> list[dict]:
    """System prompt (our spec) + the user's content as a walled-off user message."""
    return [
        {"role": "system", "content": load_system_prompt()},
        # JSON-encode so quotes/newlines in the input can't escape their container.
        {"role": "user", "content": json.dumps({"message": user_text})},
    ]


def build_repair_messages(user_text: str, bad_output: str, error: str) -> list[dict]:
    """Same prompt, plus the rejected answer and the exact validation error."""
    messages = build_messages(user_text)
    messages.append({"role": "assistant", "content": bad_output})
    messages.append(
        {
            "role": "user",
            "content": (
                "Your previous answer was rejected for this reason:\n"
                f"{error}\n\n"
                "Return ONLY corrected JSON matching the schema. No other text."
            ),
        }
    )
    return messages
