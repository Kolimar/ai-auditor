ROUTING_PROMPT = """You are the escalation desk for our customer success team.
Choose the queue that should own the account below.

Account snapshot
- tier: {tier}
- arr_usd: {arr_usd}
- open_p1_tickets: {open_p1}
- days_to_renewal: {days_to_renewal}

Apply these rules in order and stop at the first one that matches:
1. open_p1_tickets > 0 -> support_eng
2. tier == "enterprise" and arr_usd >= 50000 -> csm_lead
3. days_to_renewal <= 45 -> renewals
4. anything else -> pooled

Reply with the queue name and nothing else."""

USAGE_PARSE_PROMPT = (
    "Pull the fields out of this usage export line. The columns are "
    "account_id,period,seat_count,active_seats,api_calls.\n"
    "Return JSON with those five keys.\n\nLine: {line}"
)

EXPANSION_PROMPT = (
    "A customer is moving from {old_seats} to {new_seats} seats at "
    "${price:.2f} per seat per month, and {months_left} months remain in the "
    "current term. Work out the prorated expansion ARR in dollars. "
    "Answer with the number only."
)

NPS_SYSTEM = (
    "Label the NPS survey comment with the single theme it is mostly about: "
    "onboarding, pricing, reliability, support, missing_feature or other."
)

QBR_SYSTEM = """You are a senior customer success manager at a B2B analytics vendor.
Write the narrative section of a quarterly business review for an executive sponsor.
Tie usage trends to the outcomes the customer told us they care about, be candid about
what has not gone well, and close with two or three proposals for next quarter.
Keep it under 450 words and avoid jargon."""

RENEWAL_EMAIL_PROMPT = (
    "Draft a renewal outreach email from {csm_name} to {contact_name} at {company}.\n"
    "Renewal date: {renewal_date}\n"
    "Sentiment signal from recent calls: {sentiment}\n"
    "Highlights to mention:\n{highlights}\n"
    "Start with a line 'Subject: ...' and then the body."
)

CHURN_PROMPT = """This step reads a support or call transcript and decides whether
the customer is hinting at leaving (mentions of competitors, budget freezes, 'evaluating
options', frustration with the contract). Answer RISK or NO_RISK, then one short quote
from the transcript that justifies it.

Transcript:
{transcript}"""
