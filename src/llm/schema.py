"""The contract. Written from the job card, before the model exists.

Closed lists become enums; confidence is a bounded number; extra fields are
forbidden so the model can never quietly add one. A structurally valid JSON
object with a category we never allowed is still a failure — caught here.
"""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Category(str, Enum):
    billing = "billing"
    bug = "bug"
    feature = "feature"
    account = "account"
    other = "other"


class Urgency(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


class Team(str, Enum):
    billing = "billing"
    engineering = "engineering"
    product = "product"
    support = "support"


class TriageInput(BaseModel):
    """What the caller sends us."""
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)


class TriageOutput(BaseModel):
    """What we promise to return — every time, in this exact shape."""
    model_config = ConfigDict(extra="forbid")

    category: Category
    urgency: Urgency
    suggested_team: Team
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=200)


# A fixed, schema-valid answer used by stub mode (LLM_STUB=1) so the whole
# endpoint can be built and tested without spending a single model call.
STUB_OUTPUT = TriageOutput(
    category=Category.bug,
    urgency=Urgency.normal,
    suggested_team=Team.engineering,
    confidence=0.9,
    reason="Stubbed response — no model was called.",
)

# The deterministic fallback returned when the kill switch (LLM_ENABLED=false)
# is on. Safe and neutral: it routes to a human instead of guessing.
FALLBACK_OUTPUT = TriageOutput(
    category=Category.other,
    urgency=Urgency.normal,
    suggested_team=Team.support,
    confidence=0.0,
    reason="LLM triage is disabled; routed to support for manual review.",
)
