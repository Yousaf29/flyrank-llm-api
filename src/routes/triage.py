"""POST /triage — classify a support message into a fixed shape.

Stage 1: the contract exists before the model does. Input is validated, the
output schema is fixed, and stub mode returns a canned valid answer. No model
call happens yet — that arrives in Stage 2.
"""
from fastapi import APIRouter

from src import config
from src.llm.schema import STUB_OUTPUT, TriageInput, TriageOutput

router = APIRouter(tags=["triage"])


@router.post("/triage", response_model=TriageOutput)
def triage(body: TriageInput):
    # Stub mode: skip the model entirely, return a fixed schema-valid object.
    if config.LLM_STUB:
        return STUB_OUTPUT

    # Real model call is wired up in Stage 2.
    return STUB_OUTPUT
