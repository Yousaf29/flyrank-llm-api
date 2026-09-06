"""POST /triage — classify a support message into a fixed shape.

Stage 3: the model's answer is treated as untrusted input. It is parsed and
validated against the schema; a failure triggers exactly one repair retry; a
second failure is quarantined and the caller gets a clean 422. Raw model text is
never returned — the endpoint's contract is the schema, on success and failure.
"""
from fastapi import APIRouter, HTTPException

from src import config
from src.llm import logs
from src.llm.parse import OutputValidationError, run_triage
from src.llm.prompt import PROMPT_VERSION
from src.llm.schema import STUB_OUTPUT, TriageInput, TriageOutput

router = APIRouter(tags=["triage"])


@router.post("/triage", response_model=TriageOutput)
def triage(body: TriageInput):
    # Stub mode: skip the model entirely, return a fixed schema-valid object.
    if config.LLM_STUB:
        return STUB_OUTPUT

    try:
        result, _meta = run_triage(body.text)
        return result
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
