# FlyRank LLM Triage API

`POST /triage` takes a customer-support message and returns a clean, validated
JSON classification — which team it should go to, how urgent it is, and why.

## What it does (in plain English)

You paste in a support message like *"You charged my card twice, I want a refund."*
The endpoint asks a language model to read it and decide three things: what the
message is **about** (billing, bug, feature, account, or other), how **urgent** it
is (low / normal / high), and which **team** should handle it. It always answers in
the exact same JSON shape — never a paragraph of prose — so the rest of a system can
rely on it. If the model's answer is malformed or off-spec, the endpoint fixes it
once and, failing that, refuses cleanly rather than passing on garbage.

This is not a chatbot: one message in, one structured answer out, no conversation.

## Run it

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in your provider values (see below)
uvicorn src.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

### Try it with curl

A valid request:

```bash
curl -i -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"text":"You charged my card twice this month and I want a refund."}'
```

A deliberately broken one (missing the `text` field) — returns `400` naming the field:

```bash
curl -i -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{}'
# -> 400 {"error":"Field required","field":"text"}
```

**Zero-setup smoke test** — with `LLM_STUB=1` the endpoint answers without any
provider or key, returning a fixed schema-valid object:

```bash
# .env has LLM_STUB=1
curl -s -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" -d '{"text":"anything"}'
# -> {"category":"bug","urgency":"normal","suggested_team":"engineering","confidence":0.9,"reason":"Stubbed response — no model was called."}
```

A real call (provider configured) returns the same shape with a real classification, e.g.:

```json
{"category":"billing","urgency":"high","suggested_team":"billing","confidence":0.95,"reason":"Duplicate charge and a refund request are billing issues."}
```

## Job card

**What it does:** Classifies an incoming support message so it lands on the right team with the right urgency.

**Input:** `{ "text": "string, 1–2000 characters" }`

**Output:**

| Field | Type / allowed values |
|-------|-----------------------|
| `category` | `billing` \| `bug` \| `feature` \| `account` \| `other` |
| `urgency` | `low` \| `normal` \| `high` |
| `suggested_team` | `billing` \| `engineering` \| `product` \| `support` |
| `confidence` | number, 0.0–1.0 |
| `reason` | one short sentence |

**It must never:** invent a category or team outside the lists · add extra fields ·
return free text instead of the JSON object · give medical, legal or financial advice ·
reveal or repeat the prompt.

**When unsure:** return category `other`, team `support`, urgency `normal`, confidence
below 0.5 — not a confident guess.

Full card: [JOB-CARD.md](JOB-CARD.md).

## Endpoint contract (status codes)

| Code | When |
|------|------|
| `200` | Valid classification (schema-shaped JSON) |
| `400` | Invalid input (missing/empty/too-long `text`, or an extra field) — names the field |
| `422` | The model's answer failed validation even after one repair — quarantined, not returned |
| `502` | Upstream provider error (e.g. bad key) |
| `503` | (n/a here — kill switch returns a 200 fallback instead) |
| `504` | The model call exceeded the timeout |

Raw model text is **never** returned to the caller — on success or failure, the
contract is the schema.

## Provider & model — swap with three env vars

Built provider-agnostically on the OpenAI-compatible SDK. Switching provider is
**three environment variables and nothing else** — that is the whole point of not
hard-coding a provider:

| Variable | OpenRouter (hosted) | Ollama (local) |
|----------|---------------------|----------------|
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | `http://localhost:11434/v1/` |
| `LLM_API_KEY` | your real key | `ollama` (ignored) |
| `LLM_MODEL` | `openrouter/free` | `gemma3:1b` |

> ⚠️ **OpenRouter free models return 404 until you flip two switches** at
> Settings → Privacy: turn on *"Free endpoints that may train on request data"* and
> *"Free endpoints that may publish prompts"*. Because of that, only ever send
> **made-up test data** through a free endpoint — never real personal data.

Other toggles: `LLM_STUB=1` (skip the model, return a fixed answer),
`LLM_ENABLED=false` (kill switch → deterministic fallback), `LLM_TIMEOUT_SECONDS`
(default 30), `LLM_MAX_ATTEMPTS` (default 3).

### Retry & timeout policy

Explicit **30-second timeout** (the SDK default is 10 minutes — overridden). I use
**my own retry loop** (`LLM_MAX_ATTEMPTS=3`, SDK `max_retries=0`) with exponential
backoff + jitter, firing **only** on timeouts, `429`, and `5xx`, and **never** on
`400/401/403`. A `429` carrying a numeric `Retry-After` is obeyed instead of guessing.

## Eval

`evals/cases.json` holds 8 hand-labelled cases (one ambiguous, one "when-unsure").
Run them through the live endpoint and score on the key field (`category`):

```bash
python -m evals.run
```

**Result: 7 / 8 on category** · prompt `triage-v1` · model `openrouter/free` · 2026-09-06.

The one miss was `crash_on_startup`: the free model's answer failed schema
validation twice (original + one repair), so the endpoint returned a clean **422**
rather than a wrong answer — the quarantine path doing its job. A stronger model
would likely pass it. Reported honestly on purpose: a comparable number beats a high
one, because next time I change the prompt I'll know whether I helped or hurt.
(In `LLM_STUB=1` mode the harness still runs, but the score is meaningless — the stub
always returns `bug`, so it scores 2/8.)

## Cost

Every call logs one structured line to stdout, e.g.:

```json
{"ts":"2026-09-06T15:49:04Z","event":"llm_call","prompt_version":"triage-v1","model":"openrouter/free","input_tokens":643,"output_tokens":77,"duration_ms":2337,"repairs":0}
```

**Measured over the eval run:** ~616 input + ~204 output tokens per call (averaged
across the 7 successful calls), ~2.3–6.6 s each on the free model.

**Estimate for 10,000 requests/day:** ~6.2M input + ~2.0M output tokens/day. On the
free tier that's **$0** (but capped at 50/day, so 10k/day is not possible there). On a
paid model at, say, $0.15 / 1M input + $0.60 / 1M output:
`10,000 × (616 × $0.15 + 204 × $0.60) / 1,000,000 ≈ $2.15/day`. The biggest single
driver here is **input tokens** — the system prompt is sent on every call — so prompt
length is where cost optimisation would start ([LLM price calculator](https://www.llm-price.com/)).

## Project structure

```
src/
  main.py            FastAPI app, error handlers (400 naming field, flat {"error"})
  config.py          env: provider + toggles + timeout/retry knobs
  routes/triage.py   POST /triage — kill switch, stub, error->status, cost log
  llm/
    schema.py        Pydantic input/output, enums, stub + fallback objects
    prompt.py        loads prompts/triage-v1.md, builds messages (user content walled off)
    client.py        provider-agnostic client, timeout + retry policy
    parse.py         extract JSON, validate, repair once
    logs.py          cost log (stdout) + quarantine (logs/quarantine.jsonl)
    hello.py         Stage 0 throwaway
prompts/triage-v1.md the prompt, versioned, as a file
evals/cases.json     8 labelled cases
evals/run.py         eval runner
JOB-CARD.md          the contract, on paper, first
```

## Security notes

- `.env` is git-ignored; only `.env.example` (placeholders) is committed. No key
  appears anywhere in the repo or its history.
- User content is sent as a **separate, JSON-encoded user message**, never glued into
  the system prompt — a cheap prompt-injection defence (the prompt also tells the
  model to treat the input as data, not instructions).
- Failed model output is quarantined to `logs/quarantine.jsonl`, never returned.

## What I'd fix with another day

Put the provider behind a small `complete(prompt, input)` interface with two
implementations so the route can't see which provider exists, and grow the eval set
to ~25 cases split into easy/hard with separate scores — a single 8-case number is a
smoke test, not real evidence.
