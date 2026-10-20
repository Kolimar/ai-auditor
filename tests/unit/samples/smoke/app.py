import json
import anthropic
from pydantic import BaseModel
from typing import Literal

client = anthropic.Anthropic()
MODEL = "claude-opus-5-5"

ROUTER_PROMPT = """Decide the queue for this order.
If the amount is greater than 1000, answer "review".
If the country is not "AR", answer "export".
Otherwise answer "auto". Respond with only one word."""


class Route(BaseModel):
    queue: Literal["review", "export", "auto"]


def route_order(order: dict) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=10,
        system=ROUTER_PROMPT,
        messages=[{"role": "user", "content": json.dumps(order)}],
    )
    return resp.content[0].text.strip()


def write_reply(complaint_text: str, queue: str) -> str:
    resp = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=800,
        system="You are an empathetic support agent. Write a warm, personal reply.",
        messages=[{"role": "user", "content": f"Queue: {queue}\nCustomer wrote: {complaint_text}"}],
    )
    return resp.content[0].text


def main(orders):
    for order in orders:
        queue = route_order(order)
        if queue == "review":
            print("manual")
        reply = write_reply(order["comment"], queue)
        data = json.loads(reply)
