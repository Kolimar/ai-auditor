from openai import OpenAI

client = OpenAI()

READING_LEVELS = {
    "patient": "a 12 year old reader, no jargon, warm and reassuring, second person",
    "caregiver": "an adult without medical training, practical, with clear warning signs to watch for",
    "gp": "a general practitioner, concise clinical register, standard abbreviations allowed",
}


def adapt_discharge_note(note: str, audience: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        messages=[
            {
                "role": "system",
                "content": (
                    "Rewrite the hospital discharge note for "
                    + READING_LEVELS[audience]
                    + ". Keep every medication, dose and follow-up date exactly as written. "
                    "Explain what the findings mean for the reader."
                ),
            },
            {"role": "user", "content": note},
        ],
    )
    return resp.choices[0].message.content
