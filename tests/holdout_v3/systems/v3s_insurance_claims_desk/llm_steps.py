import json
from decimal import Decimal

import anthropic

from prompts import (
    CATEGORY_LABELS,
    CATEGORY_SYSTEM,
    COVERAGE_SYSTEM,
    EXTRACT_SYSTEM,
    NOTES_SYSTEM,
    SETTLEMENT_TEMPLATE,
    STATEMENT_SYSTEM,
    denial_prompt,
)
from settings import SETTINGS

client = anthropic.Anthropic()


def _text(resp) -> str:
    return "".join(b.text for b in resp.content if b.type == "text")


def extract_claim_fields(payload: dict) -> dict:
    resp = client.messages.create(
        model=SETTINGS.models.standard,
        max_tokens=SETTINGS.max_tokens,
        system=EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    return json.loads(_text(resp))


def tag_claim_category(description: str) -> str:
    resp = client.messages.create(
        model=SETTINGS.models.heavy,
        max_tokens=10,
        system=CATEGORY_SYSTEM.format(labels=", ".join(CATEGORY_LABELS)),
        messages=[{"role": "user", "content": description}],
    )
    label = _text(resp).strip().lower()
    return label if label in CATEGORY_LABELS else "other"


def check_coverage(claim: dict, policy: dict) -> str:
    facts = {
        "policy_status": policy["status"],
        "loss_date": claim["loss_date"],
        "peril": claim["peril"],
        "covered_perils": policy["covered_perils"],
        "claimed_amount": claim["claimed_amount"],
        "deductible": policy["deductible"],
    }
    resp = client.messages.create(
        model=SETTINGS.models.standard,
        max_tokens=200,
        system=COVERAGE_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(facts)}],
    )
    return _text(resp)


def compute_settlement(claim: dict, policy: dict) -> str:
    prompt = SETTLEMENT_TEMPLATE.format(
        claimed=claim["claimed_amount"],
        deductible=policy["deductible"],
        share=policy["coinsurance_share"],
        tax=policy.get("repair_tax", 0),
    )
    resp = client.messages.create(
        model=SETTINGS.models.standard,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return _text(resp)


def summarize_adjuster_notes(notes: list[str]) -> str:
    resp = client.messages.create(
        model=SETTINGS.models.standard,
        max_tokens=300,
        system=NOTES_SYSTEM,
        messages=[{"role": "user", "content": "\n---\n".join(notes)}],
    )
    return _text(resp)


def assess_statement_consistency(statement: str, police_excerpt: str) -> str:
    resp = client.messages.create(
        model=SETTINGS.models.heavy,
        max_tokens=1500,
        system=STATEMENT_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"CLAIMANT STATEMENT:\n{statement}\n\nPOLICE REPORT:\n{police_excerpt}",
            }
        ],
    )
    return _text(resp)


def draft_denial_letter(claim_ref: str, reason: str) -> str:
    resp = client.messages.create(
        model=SETTINGS.models.heavy,
        max_tokens=700,
        messages=[{"role": "user", "content": denial_prompt(claim_ref, reason)}],
    )
    return _text(resp)
