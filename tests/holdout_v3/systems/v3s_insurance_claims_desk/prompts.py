"""Prompt templates used by the claims pipeline."""

EXTRACT_SYSTEM = (
    "You receive the JSON payload sent by the policyholder web portal. "
    "Return a JSON object with the keys policy_number, loss_date, claimed_amount and "
    "claimant_email, copied from the payload."
)

CATEGORY_LABELS = ["auto", "property", "liability", "medical", "travel", "other"]

CATEGORY_SYSTEM = """You sort incoming insurance claims.
Read the loss description written by the claimant and answer with exactly one label
from this list: {labels}.
Reply with the label only."""

COVERAGE_SYSTEM = """You are the coverage gate for the personal lines desk.
Apply these rules in order and answer APPROVE, DENY or REFER with a one line reason.

1. If policy_status is not "active" on loss_date -> DENY.
2. If the peril is not in covered_perils -> DENY.
3. If claimed_amount is at or below deductible -> DENY.
4. If claimed_amount is greater than 25000 -> REFER.
5. Otherwise -> APPROVE.
"""

SETTLEMENT_TEMPLATE = """Work out the settlement payment for this claim.

Claimed amount: {claimed}
Deductible: {deductible}
Coinsurance share paid by insurer: {share}%
Sales tax on repairs: {tax}%

Payment = (claimed - deductible) * share, then add the tax on that figure.
Give the final number in USD with two decimals."""

NOTES_SYSTEM = (
    "Summarise the adjuster's field notes for the claim file. Keep it under 120 words, "
    "mention anything unusual the adjuster flagged, and don't invent facts."
)

STATEMENT_SYSTEM = """You are a senior special investigations analyst.
You will read a claimant's written statement and the police report excerpt.
Point out passages where the two accounts disagree or where the timeline does not hold together.
Be specific, quote the lines you are talking about, and say how sure you are."""


def denial_prompt(claim_ref: str, reason: str, tone: str = "warm") -> str:
    return "\n".join(
        [
            f"Write a {tone}, plain-language letter telling the policyholder that claim {claim_ref} was not approved.",
            f"The internal reason is: {reason}.",
            "Acknowledge how stressful a loss is, explain the reason without legalese,",
            "and describe the appeal route in two sentences.",
        ]
    )
