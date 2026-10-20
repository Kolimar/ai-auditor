from openai import OpenAI

client = OpenAI()


def classify_clause_intent(clause: str, jurisdiction: str) -> str:
    completion = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify the clause as one of: indemnification, limitation_of_liability, "
                    "waiver, other. Decide by the legal EFFECT intended under the given jurisdiction, "
                    "not by the heading. A clause titled 'General' may in fact waive statutory rights."
                ),
            },
            {"role": "user", "content": f"Jurisdiction: {jurisdiction}\n\nClause:\n{clause}"},
        ],
    )
    return completion.choices[0].message.content.strip()
