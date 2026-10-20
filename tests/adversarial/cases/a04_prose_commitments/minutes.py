from openai import OpenAI

client = OpenAI()


def extract_commitments(transcript: str) -> str:
    r = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract every action item from the meeting transcript: owner, task and deadline. "
                    "People speak informally ('yeah I'll try to get that over to Marta, maybe before the "
                    "offsite?'). Resolve pronouns and vague dates relative to the meeting date, and skip "
                    "tentative remarks that were not actually accepted."
                ),
            },
            {"role": "user", "content": transcript},
        ],
    )
    return r.choices[0].message.content
