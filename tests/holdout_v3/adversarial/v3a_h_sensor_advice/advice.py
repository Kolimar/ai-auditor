import json

from openai import OpenAI

client = OpenAI()


def _context_block(field_id: str, readings: dict) -> str:
    return f"Field {field_id}. Latest readings: {json.dumps(readings)}."


def _task_block() -> str:
    return (
        "Recommend irrigation action. Reply as a JSON object with the keys action "
        "(one of irrigate, hold, drain) and litres_per_ha (number)."
    )


def recommend_irrigation(field_id: str, readings: dict, attempts: int = 5) -> dict:
    prompt = _context_block(field_id, readings) + "\n" + _task_block()
    last_error = None
    for _ in range(attempts):
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content
        try:
            data = json.loads(text[text.index("{") : text.rindex("}") + 1])
            if data["action"] not in {"irrigate", "hold", "drain"}:
                raise ValueError("bad action")
            return data
        except (ValueError, KeyError) as exc:
            last_error = exc
            prompt += "\nYour previous reply was not valid. Return only the JSON object."
    raise RuntimeError(f"no valid advice: {last_error}")
