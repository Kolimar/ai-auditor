from decimal import Decimal

from openai import OpenAI

from config import LIGHT_MODEL, PRIMARY_MODEL
from tariffs import charge_in_code

client = OpenAI()

BILL_VOICE = (
    "You write the 'what changed on my bill' paragraph for a municipal electric and water "
    "utility. Friendly, plain English, no more than 120 words. Never invent figures; use only the ones given."
)


def explain_bill_to_customer(customer_name: str, kwh: float, prior_kwh: float, weather_note: str) -> str:
    total = charge_in_code(kwh)
    prior_total = charge_in_code(prior_kwh)
    delta = total - prior_total
    facts = (
        f"Customer: {customer_name}\n"
        f"This month: {kwh} kWh, charge ${total}\n"
        f"Last month: {prior_kwh} kWh, charge ${prior_total}\n"
        f"Difference: ${delta}\n"
        f"Local weather: {weather_note}"
    )
    resp = client.chat.completions.create(
        model=LIGHT_MODEL,
        messages=[
            {"role": "system", "content": BILL_VOICE},
            {"role": "user", "content": facts},
        ],
    )
    return resp.choices[0].message.content


def draft_dispute_reply(dispute_text: str, findings: str, agent_name: str) -> str:
    resp = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Reply to a billing dispute on behalf of the utility. Acknowledge the "
                "customer's frustration, explain what the review found, and offer a clear next step.",
            },
            {
                "role": "user",
                "content": f"Customer wrote:\n{dispute_text}\n\nReview findings:\n{findings}\n\nSign as {agent_name}.",
            },
        ],
        temperature=0.5,
    )
    return resp.choices[0].message.content


def summarize_rate_case_filing(filing_text: str) -> str:
    resp = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": "Summarize regulatory filings for the customer-care floor."},
            {"role": "user", "content": "Summarize this rate case filing, highlighting what changes for "
             "residential and small business customers and when:\n\n" + filing_text},
        ],
    )
    return resp.choices[0].message.content
