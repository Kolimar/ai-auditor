import json
import logging
import os

import anthropic
from pydantic import BaseModel, Field, ValidationError

from prompts import (
    ESCALATION_PROMPT,
    EXTRACT_PROMPT,
    POLICY_PROMPT,
    PRIORITY_PROMPT,
    REPLY_PROMPT,
    SCHEMA_CHECK_PROMPT,
)

log = logging.getLogger("triage")

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-sonnet-5-5"

REFUND_POLICY = open(os.path.join(os.path.dirname(__file__), "refund_policy.txt")).read()


class ReplyDraft(BaseModel):
    subject: str = Field(max_length=120)
    body: str
    tone: str = Field(pattern="^(warm|neutral|formal)$")


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


def extract_ticket_fields(payload: dict) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=EXTRACT_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    return json.loads(_text(response))


def assign_priority(account: dict) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=5,
        temperature=0,
        system=PRIORITY_PROMPT,
        messages=[{"role": "user", "content": json.dumps(account)}],
    )
    label = _text(response)
    return label if label in {"P1", "P2", "P3"} else "P3"


def detect_escalation_risk(text: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=ESCALATION_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    return json.loads(_text(response))


def draft_reply(name: str, priority: str, risk: str, text: str) -> ReplyDraft:
    prompt = REPLY_PROMPT.format(name=name, priority=priority, risk=risk, text=text)
    response = client.messages.create(
        model=MODEL,
        max_tokens=900,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    body = _text(response)
    return ReplyDraft(subject=f"Re: your request ({priority})", body=body, tone="warm")


def confirm_reply_document(draft: ReplyDraft) -> bool:
    document = draft.model_dump_json()
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": SCHEMA_CHECK_PROMPT.format(document=document)}],
    )
    verdict = json.loads(_text(response))
    return bool(verdict["valid"])


def review_reply_against_policy(draft: ReplyDraft, order_record: dict) -> str:
    prompt = POLICY_PROMPT.format(
        policy=REFUND_POLICY,
        reply=draft.body,
        order_record=json.dumps(order_record, indent=2),
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return _text(response)


def handle_ticket(payload: dict, account: dict, order_record: dict) -> dict:
    fields = extract_ticket_fields(payload)
    priority = assign_priority(account)
    risk = detect_escalation_risk(payload["message"])

    if risk["escalation_risk"] == "high" and priority == "P3":
        priority = "P2"

    try:
        draft = draft_reply(fields["customer_name"], priority, risk["escalation_risk"], payload["message"])
    except ValidationError:
        log.exception("reply draft failed validation")
        return {"status": "manual_review", "priority": priority}

    if not confirm_reply_document(draft):
        return {"status": "manual_review", "priority": priority}

    issues = review_reply_against_policy(draft, order_record)
    if issues != "OK":
        return {"status": "needs_edit", "priority": priority, "issues": issues}

    return {"status": "ready", "priority": priority, "reply": draft.model_dump()}


if __name__ == "__main__":
    sample = json.load(open("sample_ticket.json"))
    print(handle_ticket(sample["payload"], sample["account"], sample["order"]))
