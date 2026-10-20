import json

from openai import OpenAI

client = OpenAI()

ESCALATE_AT = 4


def score_guest_review(review_text: str) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You read guest reviews of a hotel. Rate how upset the guest is on a scale of 1 to 5 "
                    "(5 = furious, threatens legal action or social media), taking sarcasm, understatement and "
                    "context into account. Return JSON with keys upset_score and reason."
                ),
            },
            {"role": "user", "content": review_text},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def route_review(review_text: str) -> str:
    result = score_guest_review(review_text)
    if result["upset_score"] >= ESCALATE_AT:
        return "duty_manager"
    return "standard_queue"
