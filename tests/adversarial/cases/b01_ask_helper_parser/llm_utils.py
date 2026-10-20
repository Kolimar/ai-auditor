from openai import OpenAI

_client = OpenAI()


def ask(prompt: str, model: str = "gpt-4o") -> str:
    r = _client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content
