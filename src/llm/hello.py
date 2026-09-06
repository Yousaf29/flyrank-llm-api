"""Stage 0 throwaway: prove we can get one word out of a model.

Run:  python -m src.llm.hello        (after filling in .env)
Expect: output containing the word "ready".

The only thing that changes between a local model and a hosted one is the three
LLM_* environment variables — nothing in this code.
"""
from openai import OpenAI

from src.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


def main() -> None:
    client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    res = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": "Reply with exactly the word: ready"}],
    )
    print(res.choices[0].message.content)


if __name__ == "__main__":
    main()
