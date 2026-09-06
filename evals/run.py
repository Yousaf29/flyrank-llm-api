"""Run the eval set through the /triage endpoint and print a score.

  python -m evals.run

Grades on the key field (category). Uses the in-process app, so it honours your
.env — set your provider (LLM_STUB unset, LLM_ENABLED=true) for a real score.
On OpenRouter this spends 8 of your 50 daily calls, so budget for two runs.
"""
import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from src.llm.prompt import PROMPT_VERSION
from src.main import app

CASES = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))


def main() -> None:
    client = TestClient(app)
    passed = 0
    failures = []

    for case in CASES:
        resp = client.post("/triage", json={"text": case["text"]})
        if resp.status_code != 200:
            failures.append(f"{case['name']}: HTTP {resp.status_code}")
            continue
        got = resp.json()["category"]
        want = case["expected_category"]
        if got == want:
            passed += 1
        else:
            failures.append(f"{case['name']}: expected '{want}', got '{got}'")

    total = len(CASES)
    print(f"\nEval: {passed}/{total} on category  |  prompt {PROMPT_VERSION}  |  {date.today()}")
    if failures:
        print("Failed:")
        for f in failures:
            print(f"  - {f}")
    else:
        print("All cases passed.")


if __name__ == "__main__":
    main()
