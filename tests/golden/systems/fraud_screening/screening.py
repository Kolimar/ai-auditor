from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent


class AmountDecision(BaseModel):
    action: Literal["approve", "review", "block"]


class VelocityVerdict(BaseModel):
    exceeded: bool


class DisputeAssessment(BaseModel):
    plausibility: Literal["low", "medium", "high"]
    inconsistencies: list[str]
    summary: str


class RingAnalysis(BaseModel):
    linked_accounts: list[str]
    likelihood: Literal["low", "medium", "high"]
    reasoning: str


class CaseCard(BaseModel):
    text: str


@dataclass
class Txn:
    txn_id: str
    account_id: str
    amount: float
    currency: str
    merchant_category: str
    txns_last_hour: int


amount_decision_agent = Agent(
    "openai:gpt-5.5",
    output_type=AmountDecision,
    system_prompt=(
        "Decide the action for a card transaction from its amount in USD. "
        "If amount is below 250, approve. If amount is from 250 up to 2500 inclusive, review. "
        "If amount is above 2500, block. Respond with the action only."
    ),
)

velocity_check_agent = Agent(
    "openai:gpt-5.5",
    output_type=VelocityVerdict,
    system_prompt=(
        "The input has txns_last_hour and the account's tier. The limit is 5 for tier 'standard' and 12 for tier "
        "'premium'. Return exceeded=true if txns_last_hour is greater than the limit."
    ),
)

dispute_narrative_agent = Agent(
    "openai:gpt-5.5",
    output_type=DisputeAssessment,
    system_prompt=(
        "You analyse the cardholder's written narrative of a disputed charge. Assess how plausible the claim of "
        "unauthorised use is, point out inconsistencies in the story (timing, location, who had the card), and "
        "summarise for a fraud analyst. Do not decide the dispute; an analyst will."
    ),
)

ring_reasoner_agent = Agent(
    "anthropic:claude-opus-5-5",
    output_type=RingAnalysis,
    system_prompt=(
        "Given the shared devices, addresses and beneficiary accounts across these accounts, reason about whether "
        "they form a coordinated fraud ring. Consider innocent explanations such as households and shared offices "
        "before concluding."
    ),
)

risk_explainer_agent = Agent(
    "openai:gpt-5.5",
    system_prompt=(
        "Explain to a fraud analyst, in plain language, why the case was routed the way it was. "
        "Mention the strongest signals and what a reviewer should check first."
    ),
)

case_card_agent = Agent(
    "openai:gpt-5.5",
    output_type=CaseCard,
    system_prompt=(
        "Fill the template exactly: 'Case {txn_id} | Account {account_id} | {amount} {currency} | Action: {action}'. "
        "Use the values given in the input."
    ),
)


def screen(txn: Txn, tier: str, narrative: str | None, related_accounts: list[dict]) -> dict:
    decision = amount_decision_agent.run_sync(f"amount={txn.amount}").output
    velocity = velocity_check_agent.run_sync(
        f"txns_last_hour={txn.txns_last_hour}, tier={tier}"
    ).output

    action = decision.action
    if velocity.exceeded and action == "approve":
        action = "review"

    case = {"txn_id": txn.txn_id, "action": action}

    if narrative:
        assessment = dispute_narrative_agent.run_sync(narrative).output
        case["dispute"] = assessment.model_dump()
        if assessment.plausibility == "low" and action == "review":
            action = "block"
            case["action"] = action

    if related_accounts and action != "approve":
        ring = ring_reasoner_agent.run_sync(str(related_accounts)).output
        case["ring"] = ring.model_dump()

    card = case_card_agent.run_sync(
        f"txn_id={txn.txn_id}, account_id={txn.account_id}, amount={txn.amount}, "
        f"currency={txn.currency}, action={action}"
    ).output
    case["card"] = card.text
    if action != "approve":
        case["explanation"] = risk_explainer_agent.run_sync(str(case)).output
    return case
