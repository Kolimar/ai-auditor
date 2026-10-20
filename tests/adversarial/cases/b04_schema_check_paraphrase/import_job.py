import json
import anthropic

client = anthropic.Anthropic()


def check_records(records: list[dict]) -> list[str]:
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[
            {
                "role": "user",
                "content": (
                    "Make sure every record has id, email and created_at as an ISO date, and that id is "
                    "an integer. List the index of each record that does not comply, as a JSON array of "
                    "integers.\n\n" + json.dumps(records)
                ),
            }
        ],
    )
    return json.loads(msg.content[0].text)
