"""FlyRank W7 A17 — Put an LLM behind your API.

One endpoint (POST /triage) that takes a messy support message and returns
clean, validated JSON — with a timeout, retries, a cost log and a kill switch.
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.routes import triage

app = FastAPI(
    title="FlyRank LLM Triage API",
    description="Classify a support message into clean, validated JSON via an LLM.",
    version="1.0.0",
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Invalid input -> 400 naming the offending field, before any model call.

    Every rejected request is a model call we did not pay for.
    """
    first = exc.errors()[0]
    # loc looks like ("body", "text"); take the last part as the field name.
    field = ".".join(str(p) for p in first.get("loc", []) if p != "body") or "body"
    return JSONResponse(
        status_code=400,
        content={"error": first.get("msg", "Invalid input"), "field": field},
    )


app.include_router(triage.router)
