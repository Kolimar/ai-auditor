import json

import anthropic

from prompts import routing_prompt
from settings import SETTINGS

client = anthropic.Anthropic()


class ClaimsDesk:
    def __init__(self, tools=None):
        self.tools = tools or []

    def route(self, claim: dict) -> str:
        record = {
            "claim_amount": claim["amount"],
            "policy_active": claim["policy_status"] == "active",
            "fraud_flag": bool(claim.get("fraud_flag")),
        }
        resp = client.messages.create(
            model=SETTINGS.routing_model,
            max_tokens=SETTINGS.max_tokens,
            messages=[{"role": "user", "content": routing_prompt(json.dumps(record))}],
        )
        return resp.content[0].text.strip()

    def answer_with_policy(self, question: str, policy_id: str) -> str:
        resp = client.messages.create(
            model=SETTINGS.routing_model,
            max_tokens=600,
            tools=[
                {
                    "name": "lookup_policy",
                    "description": "Fetch the policy document by id",
                    "input_schema": {"type": "object", "properties": {"policy_id": {"type": "string"}}},
                }
            ],
            tool_choice={"type": "tool", "name": "lookup_policy"},
            messages=[{"role": "user", "content": f"Policy {policy_id}. Customer asks: {question}"}],
        )
        return json.dumps(resp.content[0].input)
