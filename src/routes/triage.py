"""POST /triage — classify a support message into a fixed shape.

Stage 2: the prompt (a versioned file) is wired to the endpoint. The model is
called with the user's content as a separate, JSON-encoded message. Parsing is
naive for now — robust parse/validate/repair/quarantine arrives in Stage 3.
"""
from fastapi import APIRouter

from src import config
from src.llm.client import complete
from src.llm.prompt import build_messages
from src.llm.schema import STUB_OUTPUT, TriageInput, TriageOutput

router = APIRouter(tags=["triage"])


@router.post("/triage", response_model=TriageOutput)
def triage(body: TriageInput):
    # Stub mode: skip the model entirely, return a fixed schema-valid object.
    if config.LLM_STUB:
        return STUB_OUTPUT

    # Call the model with our versioned prompt + the user's walled-off content.
    text, _usage = complete(build_messages(body.text))

    # Naive parse for Stage 2 — Stage 3 makes this trustworthy.
    return TriageOutput.model_validate_json(text)
