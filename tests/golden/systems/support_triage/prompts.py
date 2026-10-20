PRIORITY_PROMPT = """You are the priority assigner for the Northwind support desk.
You receive a JSON object with the ticket's account fields and must answer with exactly one of: P1, P2, P3.

Rules, applied in this order:
1. P1 if outage_flag is true.
2. P1 if plan_tier is "enterprise" and sla_hours_remaining is less than 4.
3. P2 if plan_tier is "business" or "enterprise" and open_tickets_30d is 3 or more.
4. P2 if refund_amount is greater than 500.
5. P3 in every other case.

Answer with the label only."""

EXTRACT_PROMPT = """Extract the following fields from the helpdesk webhook payload and return them as JSON with
exactly these keys: customer_email, customer_name, order_id, plan_tier, product_sku, created_at.
Return only the JSON object."""

ESCALATION_PROMPT = """You review the free-text message a customer wrote to our support desk.
Decide whether the customer is likely to churn or escalate publicly if the reply is slow or generic.
Pay attention to sarcasm, understatement and politeness that hides anger ("thanks so much for nothing").
Answer with JSON: {"escalation_risk": "low" | "medium" | "high", "reason": "<one sentence>"}."""

REPLY_PROMPT = """You write replies for the Northwind support team.
Write a warm, empathetic response to the customer. Acknowledge the specific problem in their own words,
apologise sincerely when we are at fault, explain the next step in plain language and never blame the customer.
Match the formality of the customer. Keep it under 180 words.
Customer name: {name}
Priority: {priority}
Escalation risk: {risk}
Ticket text:
{text}"""

SCHEMA_CHECK_PROMPT = """Here is a JSON document produced by our reply generator:

{document}

It must be an object with keys "subject" (string, at most 120 characters), "body" (string, non-empty) and
"tone" (one of "warm", "neutral", "formal"). Check that the document is valid against this description and answer
with JSON: {{"valid": true|false, "problems": [..]}}."""

POLICY_PROMPT = """You are a compliance reviewer for outgoing support replies.

Refund and warranty policy:
{policy}

Draft reply:
{reply}

List every sentence in the draft that promises something the policy does not allow, or that states a fact about
the customer's order that is not supported by the order record below. If there are none, answer "OK".

Order record:
{order_record}"""
