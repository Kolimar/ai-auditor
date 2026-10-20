import json
from collections import defaultdict
from decimal import Decimal

import chromadb
from openai import OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from config import MODELS, SYSTEM_ADVISOR

oai = OpenAI()
store = chromadb.PersistentClient(path="./ledger_index").get_or_create_collection("statements")


def monthly_totals(transactions: list[dict], eur_rate: float) -> str:
    r = oai.chat.completions.create(
        model=MODELS.big,
        messages=[
            {
                "role": "user",
                "content": "Add up the amounts per category for this month and also give the grand "
                f"total in EUR using a rate of {eur_rate} per USD. Return a JSON object keyed by category.\n"
                + json.dumps(transactions),
            }
        ],
    )
    return r.choices[0].message.content


def explain_variance(transactions: list[dict], budget: dict[str, str]) -> str:
    spent: dict[str, Decimal] = defaultdict(Decimal)
    for t in transactions:
        spent[t["category"]] += Decimal(str(t["amount"]))
    lines = []
    for cat, limit in budget.items():
        diff = spent[cat] - Decimal(limit)
        lines.append(f"{cat}: spent {spent[cat]}, budget {limit}, difference {diff}")
    r = oai.chat.completions.create(
        model=MODELS.big,
        messages=[
            {
                "role": "system",
                "content": "The figures below are already computed and correct. Explain in plain language "
                "to the household which categories drove the gap and what is likely behind it.",
            },
            {"role": "user", "content": "\n".join(lines)},
        ],
    )
    return r.choices[0].message.content


@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(5),
)
def budget_advice(profile: str, goals: str) -> str:
    r = oai.chat.completions.create(
        model=MODELS.big,
        temperature=0.5,
        messages=[
            {"role": "system", "content": SYSTEM_ADVISOR},
            {"role": "user", "content": f"Profile:\n{profile}\n\nGoals:\n{goals}"},
        ],
    )
    return r.choices[0].message.content


def ask_my_finances(question: str) -> str:
    hits = store.query(query_texts=[question], n_results=3)
    context = "\n".join(hits["documents"][0])
    r = oai.chat.completions.create(
        model=MODELS.big,
        messages=[
            {"role": "system", "content": "Answer from the statement excerpts only; say so if they do not cover it."},
            {"role": "user", "content": f"{context}\n\nQuestion: {question}"},
        ],
    )
    return r.choices[0].message.content


def tax_notes_summary(notes: str) -> str:
    r = oai.chat.completions.create(
        model=MODELS.small,
        messages=[
            {"role": "system", "content": "Summarise these free-form notes the user kept about deductible expenses, grouped by theme."},
            {"role": "user", "content": notes},
        ],
    )
    return r.choices[0].message.content
