import json
from openai import OpenAI

client = OpenAI()


def route_complaint(payload: str) -> str:
    data = json.loads(payload)
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You receive a JSON object with fields customer_id, channel and complaint. "
                    "Read the complaint text and decide the department: billing, logistics, product_quality "
                    "or fraud. Complaints are written by customers in their own words and often mix topics; "
                    "pick the root cause."
                ),
            },
            {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
        ],
    )
    return r.choices[0].message.content.strip()
