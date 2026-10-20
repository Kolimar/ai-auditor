import json
from openai import OpenAI

client = OpenAI()


def validate_article_claims(article: str, sources: list[dict]) -> dict:
    evidence = "\n\n".join(f"[{s['id']}] {s['text']}" for s in sources)
    r = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Validate the article. For each factual claim, verify it against the numbered sources. "
                    "Return JSON {claims: [{claim, verdict: supported|contradicted|unverifiable, source_ids}]}."
                ),
            },
            {"role": "user", "content": f"ARTICLE:\n{article}\n\nSOURCES:\n{evidence}"},
        ],
    )
    return json.loads(r.choices[0].message.content)
