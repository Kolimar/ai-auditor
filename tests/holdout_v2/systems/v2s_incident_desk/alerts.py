import json

import anthropic
from openai import OpenAI

oai = OpenAI()
claude = anthropic.Anthropic()

TIER1 = {"checkout", "auth", "payments"}


def parse_alert_line(line: str) -> dict:
    """Lines come from our log shipper: `ts=2026-03-02T11:04:09Z level=ERROR svc=checkout code=E503 latency_ms=1200`"""
    r = oai.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "Break the alert line into ts, level, svc, code and latency_ms. Answer as JSON.",
            },
            {"role": "user", "content": line},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(r.choices[0].message.content)


def route_alert(svc: str, error_rate_pct: float, latency_ms: int) -> str:
    rules = (
        "Choose who gets notified.\n"
        f"- If svc is in {sorted(TIER1)} and error_rate_pct is above 5, answer PAGE_ONCALL.\n"
        "- If latency_ms is above 2000 for any service, answer PAGE_ONCALL.\n"
        "- If error_rate_pct is above 1, answer SLACK_CHANNEL.\n"
        "- Otherwise answer IGNORE.\n"
        "Reply with the answer word alone."
    )
    m = claude.messages.create(
        model="claude-opus-4-1",
        max_tokens=8,
        system=rules,
        messages=[
            {
                "role": "user",
                "content": f"svc={svc} error_rate_pct={error_rate_pct} latency_ms={latency_ms}",
            }
        ],
    )
    return m.content[0].text.strip()
