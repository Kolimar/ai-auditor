"""Tutorial: calling the model from a script."""
from openai import OpenAI

client = OpenAI()


def demo_parse_csv_row(row: str) -> str:
    r = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Extract the name and age columns from this CSV row: {row}"}],
    )
    return r.choices[0].message.content
