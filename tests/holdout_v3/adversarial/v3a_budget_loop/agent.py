import time

import anthropic

from tools import TOOL_SCHEMAS, dispatch

client = anthropic.Anthropic()

SYSTEM = (
    "You are a legal research assistant. Search the case-law index, read the "
    "relevant opinions and build a memo answering the question. Cite every case."
)


def research_until_budget(question: str, token_budget: int = 60000, deadline_s: float = 120.0) -> str:
    started = time.monotonic()
    spent = 0
    messages = [{"role": "user", "content": question}]
    last_text = ""
    while spent < token_budget and time.monotonic() - started < deadline_s:
        resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=SYSTEM,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        spent += resp.usage.input_tokens + resp.usage.output_tokens
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "text":
                last_text = block.text
            elif block.type == "tool_use":
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": dispatch(block.name, block.input)}
                )
        if not results:
            break
        messages.append({"role": "user", "content": results})
    return last_text
