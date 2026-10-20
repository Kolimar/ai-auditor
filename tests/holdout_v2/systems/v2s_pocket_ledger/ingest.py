import json

from openai import OpenAI
from pydantic_ai import Agent

from config import CATEGORIES, MODELS, SYSTEM_CATEGORIZER

oai = OpenAI()

categorizer = Agent(
    f"openai:{MODELS.big}",
    system_prompt=SYSTEM_CATEGORIZER + " Allowed: " + ", ".join(CATEGORIES),
)


def categorize_transaction(memo: str) -> str:
    result = categorizer.run_sync(memo)
    return result.output.strip().lower()


def import_csv_row(line: str) -> dict:
    """Bank export rows look like: 2026-02-14,-42.17,"GROCERY OUTLET",USD"""
    r = oai.chat.completions.create(
        model=MODELS.small,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": "Split this CSV line into date, amount, description and currency and "
                'answer with JSON {"date","amount","description","currency"}.\n' + line,
            }
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(r.choices[0].message.content)


def normalize_statement_dates(rows: list[dict]) -> list[dict]:
    r = oai.chat.completions.create(
        model=MODELS.small,
        messages=[
            {
                "role": "system",
                "content": "Rewrite each row's 'date' from DD/MM/YYYY to ISO 8601 (YYYY-MM-DD) and put "
                "the 'merchant' value in upper case. Do not touch any other field. Return the JSON list.",
            },
            {"role": "user", "content": json.dumps(rows)},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(r.choices[0].message.content)["rows"]
