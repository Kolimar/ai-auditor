import time
import anthropic

client = anthropic.Anthropic()

MAX_STEPS = 6
DEADLINE_S = 90


def run_research(question: str, tools: list[dict], dispatch) -> str:
    messages = [{"role": "user", "content": question}]
    started = time.monotonic()
    steps = 0
    while True:
        steps += 1
        if steps > MAX_STEPS or time.monotonic() - started > DEADLINE_S:
            messages.append({"role": "user", "content": "Budget exhausted. Give your best final answer now."})
            tools = []
        resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1500,
            tools=tools,
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")
        messages.append({"role": "assistant", "content": resp.content})
        results = [
            {"type": "tool_result", "tool_use_id": b.id, "content": dispatch(b.name, b.input)}
            for b in resp.content
            if b.type == "tool_use"
        ]
        messages.append({"role": "user", "content": results})
