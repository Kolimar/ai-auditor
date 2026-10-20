import json
import time

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from config import LIGHT_MODEL, PRIMARY_MODEL

client = OpenAI()


class Reading(BaseModel):
    meter_id: str
    ts: str
    kwh: float
    status: str


READING_INSTRUCTIONS = """Convert the raw AMR gateway line into JSON with the keys
meter_id, ts, kwh and status. Example line:
MTR=00482113;TS=2026-03-02T04:00:00Z;KWH=12873.4;STATUS=OK
Output only the JSON object."""


def normalize_meter_reading(raw_line: str) -> Reading:
    last_error = None
    for attempt in range(5):
        resp = client.chat.completions.create(
            model=LIGHT_MODEL,
            messages=[
                {"role": "system", "content": READING_INSTRUCTIONS},
                {"role": "user", "content": raw_line},
            ],
        )
        text = resp.choices[0].message.content
        try:
            return Reading(**json.loads(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"could not normalize reading: {last_error}")


def verify_reading_payload(reading: Reading) -> bool:
    prompt = (
        "Here is a meter reading as JSON:\n"
        + reading.model_dump_json()
        + "\nConfirm that meter_id, ts, kwh and status are all present, that kwh is a "
        "number greater than or equal to zero and that ts is an ISO-8601 timestamp. "
        "Answer YES or NO."
    )
    resp = client.chat.completions.create(
        model=LIGHT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3,
    )
    return resp.choices[0].message.content.strip().upper().startswith("YES")


def review_high_usage_complaint(complaint: str, usage_summary: dict) -> str:
    lines = [f"{month}: {kwh} kWh" for month, kwh in usage_summary.items()]
    prompt = (
        "A residential customer says their bill is far higher than usual.\n\n"
        "Their message:\n" + complaint + "\n\nMetered usage (computed from validated reads):\n"
        + "\n".join(lines)
        + "\n\nDecide which explanation is most plausible (seasonal load, a new appliance, "
        "a possible leak or fault, estimated read, something else) and say what the agent "
        "should check next. Weigh what the customer wrote against the numbers."
    )
    resp = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return resp.choices[0].message.content
