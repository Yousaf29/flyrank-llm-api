"""POST /triage — classify a support message into a fixed, validated shape.

Stage 4: production-ready. The model call has a real timeout and a bounded retry
policy (in the client); this route adds the kill switch, maps failures to clean
HTTP statuses (504 timeout, 502 upstream, 422 unrepairable), and writes one
structured cost line per successful call.
"""
import time

from fastapi import APIRouter, HTTPException

from src import config
from src.llm import logs
from src.llm.client import LLMTimeout, LLMUpstreamError
from src.llm.parse import OutputValidationError, run_triage
from src.llm.prompt import PROMPT_VERSION
from src.llm.schema import FALLBACK_OUTPUT, STUB_OUTPUT, TriageInput, TriageOutput

router = APIRouter(tags=["triage"])


@router.post("/triage", response_model=TriageOutput)
def triage(body: TriageInput):
    # Kill switch: turn the model off without a deploy. Zero model calls.
    if not config.LLM_ENABLED:
        return FALLBACK_OUTPUT

    # Stub mode: skip the model, return a fixed schema-valid object (free to run).
    if config.LLM_STUB:
        return STUB_OUTPUT

    start = time.monotonic()
    try:
        result, meta = run_triage(body.text)
    except LLMTimeout:
        raise HTTPException(status_code=504, detail="The model took too long to respond.")
    except LLMUpstreamError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream model error: {exc}")
    except OutputValidationError as exc:
        # Second attempt also failed: set the answer aside, never return it.
        logs.quarantine(
            input_text=body.text,
            raw=exc.raw,
            error=exc.error,
            prompt_version=PROMPT_VERSION,
        )
        raise HTTPException(
            status_code=422,
            detail="Could not produce a valid result: the model's answer failed "
            "validation after one repair attempt.",
        )

    # One structured cost line per call: what we spent and whether we repaired.
    logs.log_cost(
        prompt_version=PROMPT_VERSION,
        model=config.LLM_MODEL,
        input_tokens=meta["usage"].get("input_tokens"),
        output_tokens=meta["usage"].get("output_tokens"),
        duration_ms=int((time.monotonic() - start) * 1000),
        repairs=meta["repairs"],
    )
    return result
