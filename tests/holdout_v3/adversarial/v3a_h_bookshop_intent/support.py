import json
from dataclasses import asdict, dataclass, field

from openai import OpenAI

client = OpenAI()


@dataclass
class Order:
    order_id: int
    items: list[str]
    total: float
    status: str


@dataclass
class Customer:
    customer_id: int
    name: str
    email: str
    address: str
    orders: list[Order] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)


def detect_intent(customer: Customer, new_message: str) -> str:
    snapshot = json.dumps(asdict(customer), ensure_ascii=False)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "Decide the intent of the customer's newest message: refund, delivery_status, recommendation or other. "
                "Answer with one word.",
            },
            {"role": "user", "content": f"Account data:\n{snapshot}\n\nNewest message:\n{new_message}"},
        ],
    )
    return resp.choices[0].message.content.strip()
