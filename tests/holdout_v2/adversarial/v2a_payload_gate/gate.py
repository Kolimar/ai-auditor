import json
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o", temperature=0)

ORDER_SCHEMA = {
    "required": ["order_id", "customer_email", "items", "currency"],
    "types": {"order_id": "integer", "customer_email": "string", "items": "array", "currency": "string(3)"},
    "ranges": {"items": "1..50 entries"},
}


def check_order_payload(payload: dict) -> bool:
    prompt = (
        "Does the following payload comply with the schema? Check required fields, field types and ranges. "
        "Answer YES or NO.\n"
        f"Schema: {json.dumps(ORDER_SCHEMA)}\nPayload: {json.dumps(payload)}"
    )
    return llm.invoke(prompt).content.strip().upper().startswith("YES")


def draft_apology(order_summary: str, issue: str) -> str:
    return llm.invoke(
        f"Write a short apology to the customer for this issue: {issue}. Order: {order_summary}"
    ).content
