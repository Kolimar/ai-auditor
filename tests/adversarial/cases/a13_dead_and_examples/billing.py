import json
from openai import OpenAI

client = OpenAI()

USE_LEGACY_EXTRACTION = False


def load_invoice(raw: str) -> dict:
    if USE_LEGACY_EXTRACTION:
        return legacy_extract(raw)
    return json.loads(raw)


def legacy_extract(raw: str) -> dict:
    if False:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Extract total and date as JSON from: " + raw}],
        )
        return json.loads(r.choices[0].message.content)
    return {}
