import json

import anthropic

from plant_config import HAIKU, OPUS, SONNET, SPEC
from prompts import DEFECT_PROMPT, DISPOSITION_PROMPT, LOG_PARSE_PROMPT

client = anthropic.Anthropic()


def classify_operator_remark(remark: str) -> str:
    msg = client.messages.create(
        model=OPUS,
        max_tokens=16,
        system=DEFECT_PROMPT,
        messages=[{"role": "user", "content": remark}],
    )
    return msg.content[0].text.strip()


def decide_disposition(measurements: dict) -> str:
    payload = {"limits": SPEC, "measured": measurements}
    msg = client.messages.create(
        model=SONNET,
        max_tokens=8,
        system=DISPOSITION_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    return msg.content[0].text.strip()


def parse_sensor_lines(path: str) -> list[dict]:
    rows = []
    with open(path) as fh:
        for line in fh:
            msg = client.messages.create(
                model=HAIKU,
                max_tokens=120,
                system=LOG_PARSE_PROMPT,
                messages=[{"role": "user", "content": line.strip()}],
            )
            rows.append(json.loads(msg.content[0].text))
    return rows
