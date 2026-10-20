import json

import anthropic

from prompts import EXPANSION_PROMPT, USAGE_PARSE_PROMPT
from settings import SETTINGS

client = anthropic.Anthropic()


def parse_usage_export(line: str) -> dict:
    msg = client.messages.create(
        model=SETTINGS.fast_model,
        max_tokens=200,
        messages=[{"role": "user", "content": USAGE_PARSE_PROMPT.format(line=line)}],
    )
    return json.loads(msg.content[0].text)


def estimate_expansion_arr(old_seats: int, new_seats: int, price: float, months_left: int) -> float:
    msg = client.messages.create(
        model=SETTINGS.fast_model,
        max_tokens=30,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": EXPANSION_PROMPT.format(
                    old_seats=old_seats,
                    new_seats=new_seats,
                    price=price,
                    months_left=months_left,
                ),
            }
        ],
    )
    return float(msg.content[0].text.strip().replace(",", ""))
