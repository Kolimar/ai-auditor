import json

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

client = anthropic.Anthropic()

KINDS = ["capacity", "bad_deploy", "dependency_outage", "data_corruption", "security", "unknown"]


def classify_incident_type(report_text: str) -> dict:
    last = None
    for attempt in range(5):
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": "Read the on-call engineer's incident report and classify it. Return a "
                    f'JSON object like {{"kind": <one of {KINDS}>, "confidence": <0-1>}}. '
                    "Return JSON only.\n\n" + report_text,
                }
            ],
        )
        try:
            return json.loads(msg.content[0].text)
        except json.JSONDecodeError as exc:
            last = exc
            continue
    raise RuntimeError(f"model never produced valid JSON: {last}")


@retry(
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIConnectionError)),
    wait=wait_exponential(multiplier=2, max=60),
    stop=stop_after_attempt(6),
)
def compose_status_update(summary: str, audience: str) -> str:
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        system=f"Write a status page update for {audience}. Be calm and factual, no jargon, say what we know and what we do not.",
        messages=[{"role": "user", "content": summary}],
    )
    return msg.content[0].text
