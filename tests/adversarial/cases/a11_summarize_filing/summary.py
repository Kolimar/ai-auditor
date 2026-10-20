from pathlib import Path
from openai import OpenAI

client = OpenAI()


def summarize_filing(path: str, audience: str) -> str:
    full_text = Path(path).read_text(encoding="utf-8")
    r = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": f"Summarize the following annual report for {audience} in under 400 words. Highlight changes in risk factors versus typical sector disclosures."},
            {"role": "user", "content": full_text},
        ],
    )
    return r.choices[0].message.content
