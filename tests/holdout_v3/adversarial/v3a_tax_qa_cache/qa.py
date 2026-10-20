import functools
from pathlib import Path

import anthropic

client = anthropic.Anthropic()

CODE_TEXT = Path("data/tax_code_2025.txt").read_text()


@functools.lru_cache(maxsize=2048)
def answer_question(question: str) -> str:
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        temperature=0,
        system=[
            {"type": "text", "text": "You answer questions on the national tax code and cite section numbers."},
            {"type": "text", "text": CODE_TEXT, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": question}],
    )
    return resp.content[0].text


def answer_batch(questions):
    return [answer_question(q) for q in questions]
