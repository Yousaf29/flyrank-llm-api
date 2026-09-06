"""Parse, validate, and repair the model's answer.

The model is an external source; its answer is untrusted raw input — exactly like
data scraped from the web. We strip any code fence, extract the JSON object,
validate it against our schema, and if that fails we give the model one chance to
fix its own mistake. Fail twice and the output is quarantined, never returned.
"""
import json
import re

from pydantic import ValidationError

from src.llm import prompt as prompt_mod
from src.llm.client import complete
from src.llm.schema import TriageOutput


class OutputValidationError(Exception):
    """Raised when the model's answer cannot be made schema-valid, even after repair."""

    def __init__(self, raw: str, error: str):
        self.raw = raw
        self.error = error
        super().__init__(error)


def extract_json(text: str) -> str:
    """Pull the JSON object out of a model reply.

    Handles ```json fences and chatty preambles like 'Sure! Here is the JSON:'.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    # Grab from the first '{' to the last '}' — ignores anything around the object.
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    return cleaned.strip()


def parse_and_validate(text: str) -> TriageOutput:
    """Extract JSON and validate against the schema. Raises on any failure."""
    return TriageOutput.model_validate_json(extract_json(text))


def run_triage(user_text: str) -> tuple[TriageOutput, dict]:
    """Call the model, validate, repair once if needed.

    Returns (validated_output, meta) where meta carries token usage and the
    repair count for the cost log. Raises OutputValidationError if even the
    repaired answer is invalid.
    """
    # First attempt.
    text, usage = complete(prompt_mod.build_messages(user_text))
    try:
        result = parse_and_validate(text)
        return result, {"usage": usage, "repairs": 0}
    except (json.JSONDecodeError, ValidationError) as first_error:
        error_msg = str(first_error)
        broken = text

    # Repair once — hand the model its own broken answer and the exact error.
    text2, usage2 = complete(
        prompt_mod.build_repair_messages(user_text, broken, error_msg)
    )
    try:
        result = parse_and_validate(text2)
        # Report combined token usage across both calls.
        combined = {
            k: (usage.get(k) or 0) + (usage2.get(k) or 0)
            for k in ("input_tokens", "output_tokens")
        }
        return result, {"usage": combined, "repairs": 1}
    except (json.JSONDecodeError, ValidationError) as second_error:
        raise OutputValidationError(raw=text2, error=str(second_error))
